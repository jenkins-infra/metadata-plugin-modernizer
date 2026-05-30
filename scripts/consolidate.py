#!/usr/bin/env python3

# This script consolidates all plugin modernization metadata into a single _plugin-modernizer-stats-report/report.json file.
import csv
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

EXCLUDED_DIRS = {".github", "reports", ".git", "scripts"}
UPSTREAM_REPO = "jenkins-infra/metadata-plugin-modernizer"
SCHEMA_VERSION = "1.0.0"

REQUIRED_SUMMARY_FIELDS = [
    "generatedOn",
    "totalMigrations",
    "failedMigrations",
    "successRate",
    "pullRequestStats",
    "timeline",
    "tags",
]


# Compute SHA-256 hex digest of a file for integrity tracking.
def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# Safely parse a JSON file, returning None on failure.
def read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Skipping malformed JSON %s: %s", path, exc)
        return None


# Parse a CSV file into a list of row dicts using the header as keys.
def read_csv_as_dicts(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    except OSError as exc:
        log.warning("Could not read CSV %s: %s", path, exc)
    return rows


# List plugin directory names at the repo root, excluding non-plugin dirs.
def discover_plugins(root: Path) -> list[str]:
    plugins = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in EXCLUDED_DIRS or entry.name.startswith("."):
            continue
        if entry.name == "_plugin-modernizer-stats-report":
            continue
        plugins.append(entry.name)
    return plugins


# Load and validate reports/summary.json; exits on missing or invalid data.
def load_summary(root: Path) -> dict:
    path = root / "reports" / "summary.json"
    data = read_json(path)
    if data is None:
        log.error("Cannot read reports/summary.json – aborting")
        sys.exit(1)
    missing = [f for f in REQUIRED_SUMMARY_FIELDS if f not in data]
    if missing:
        log.error("summary.json missing required fields: %s", missing)
        sys.exit(1)
    return data


# Load all reports/recipes/*.json into a dict keyed by recipeId.
def load_recipes(root: Path) -> dict:
    recipes_dir = root / "reports" / "recipes"
    recipes: dict = {}
    if not recipes_dir.is_dir():
        log.warning("No reports/recipes/ directory found")
        return recipes
    for path in sorted(recipes_dir.glob("*.json")):
        data = read_json(path)
        if data is None:
            continue
        rid = data.get("recipeId", path.stem)
        recipes[rid] = data
    return recipes


# Load a single plugin's aggregated migrations, failures CSV and raw metadata.
def load_plugin(root: Path, plugin_id: str) -> dict | None:
    plugin_dir = root / plugin_id
    result: dict = {"sourceUrls": {}}

    agg_path = plugin_dir / "reports" / "aggregated_migrations.json"
    agg = read_json(agg_path)
    if agg is None:
        log.warning("Plugin %s: no aggregated_migrations.json, skipping", plugin_id)
        return None

    repo_url = agg.get("pluginRepository", "")
    if repo_url:
        result["sourceUrls"]["repository"] = repo_url
        result["sourceUrls"]["upstreamMetadata"] = (
            f"https://github.com/{UPSTREAM_REPO}/tree/main/{plugin_id}"
        )

    result["aggregatedMigrations"] = agg.get("migrations", [])

    fail_path = plugin_dir / "reports" / "failed_migrations.csv"
    if fail_path.exists():
        result["failedMigrations"] = read_csv_as_dicts(fail_path)
    else:
        result["failedMigrations"] = []

    meta_dir = plugin_dir / "modernization-metadata"
    metadata_records: list[dict] = []
    if meta_dir.is_dir():
        for mpath in sorted(meta_dir.glob("*.json")):
            rec = read_json(mpath)
            if rec is not None:
                metadata_records.append(rec)
    result["modernizationMetadata"] = metadata_records

    return result


# Assemble the full consolidated report from summary, recipes and all plugins.
def build_report(root: Path, summary: dict) -> dict:
    recipes = load_recipes(root)
    plugin_ids = discover_plugins(root)

    log.info("Found %d plugin directories", len(plugin_ids))
    log.info("Found %d recipe files", len(recipes))

    plugins: dict = {}
    errors = 0
    for pid in plugin_ids:
        pdata = load_plugin(root, pid)
        if pdata is None:
            errors += 1
            continue
        plugins[pid] = pdata

    log.info("Loaded %d plugins (%d skipped)", len(plugins), errors)

    pr_stats = summary.get("pullRequestStats", {})

    total_migrations = summary.get("totalMigrations", 0)
    failed_migrations = summary.get("failedMigrations", 0)
    successful = total_migrations - failed_migrations
    success_rate = summary.get("successRate", 0.0)

    timeline = summary["timeline"]
    tags = summary["tags"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    summary_hash = sha256_of_file(root / "reports" / "summary.json")

    report = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now,
        "dataSource": f"https://github.com/{UPSTREAM_REPO}",
        "meta": {
            "source_sha256": summary_hash,
            "parsed_at": now,
        },
        "overview": {
            "totalPlugins": len(plugins),
            "totalMigrations": total_migrations,
            "successfulMigrations": successful,
            "failedMigrations": failed_migrations,
            "successRate": success_rate,
        },
        "pullRequests": {
            "totalPRs": pr_stats.get("total", 0),
            "openPRs": pr_stats.get("open", 0),
            "closedPRs": pr_stats.get("closed", 0),
            "mergedPRs": pr_stats.get("merged", 0),
            "mergeRate": pr_stats.get("mergeRate", 0.0),
        },
        "failuresByRecipe": summary.get("failuresByRecipe", []),
        "pluginsWithFailedMigrations": summary.get("pluginsWithFailures", []),
        "timeline": timeline,
        "tags": tags,
        "recipes": recipes,
        "plugins": plugins,
    }

    return report


# Cross-validate the generated report against summary.json to catch data mismatches.
def validate_report(report: dict, summary: dict) -> bool:
    required_top = [
        "schemaVersion", "generatedAt", "dataSource", "meta",
        "overview", "pullRequests", "recipes", "plugins",
    ]
    ok = True
    for key in required_top:
        if key not in report:
            log.error("Report missing required key: %s", key)
            ok = False

    overview = report.get("overview", {})
    for field in ["totalPlugins", "totalMigrations", "failedMigrations", "successRate"]:
        if field not in overview:
            log.error("overview missing field: %s", field)
            ok = False

    checks = [
        ("totalMigrations", overview.get("totalMigrations"), summary.get("totalMigrations")),
        ("failedMigrations", overview.get("failedMigrations"), summary.get("failedMigrations")),
        ("successRate", overview.get("successRate"), summary.get("successRate")),
    ]
    for name, report_val, summary_val in checks:
        if report_val != summary_val:
            log.error(
                "Mismatch for %s: report has %s, summary.json has %s",
                name, report_val, summary_val,
            )
            ok = False

    pr_report = report.get("pullRequests", {})
    pr_summary = summary.get("pullRequestStats", {})
    pr_checks = [
        ("totalPRs", pr_report.get("totalPRs"), pr_summary.get("total")),
        ("openPRs", pr_report.get("openPRs"), pr_summary.get("open")),
        ("closedPRs", pr_report.get("closedPRs"), pr_summary.get("closed")),
        ("mergedPRs", pr_report.get("mergedPRs"), pr_summary.get("merged")),
        ("mergeRate", pr_report.get("mergeRate"), pr_summary.get("mergeRate")),
    ]
    for name, report_val, summary_val in pr_checks:
        if report_val != summary_val:
            log.error(
                "PR mismatch for %s: report has %s, summary.json has %s",
                name, report_val, summary_val,
            )
            ok = False

    report_failure_count = len(report.get("failuresByRecipe", []))
    summary_failure_count = len(summary.get("failuresByRecipe", []))
    if report_failure_count != summary_failure_count:
        log.error(
            "failuresByRecipe count mismatch: report has %d, summary.json has %d",
            report_failure_count, summary_failure_count,
        )
        ok = False

    report_failed_plugins = len(report.get("pluginsWithFailedMigrations", []))
    summary_failed_plugins = len(summary.get("pluginsWithFailures", []))
    if report_failed_plugins != summary_failed_plugins:
        log.error(
            "pluginsWithFailedMigrations count mismatch: report has %d, summary.json has %d",
            report_failed_plugins, summary_failed_plugins,
        )
        ok = False

    return ok


# Entry point: resolve dirs, build report, validate and write to output.
def main() -> None:
    input_dir = Path(os.environ.get("INPUT_DIR", ".")).resolve()
    output_dir = Path(os.environ.get("OUTPUT_DIR", "_plugin-modernizer-stats-report")).resolve()

    log.info("Input directory: %s", input_dir)
    log.info("Output directory: %s", output_dir)

    if not (input_dir / "reports" / "summary.json").exists():
        log.error("No reports/summary.json found in %s", input_dir)
        sys.exit(1)

    summary = load_summary(input_dir)
    report = build_report(input_dir, summary)

    if not validate_report(report, summary):
        log.error("Report validation failed")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    log.info("Wrote %s (%.2f MB)", out_path, size_mb)
    log.info("Top-level keys: %s", list(report.keys()))
    log.info("Plugins: %d, Recipes: %d", len(report["plugins"]), len(report["recipes"]))


if __name__ == "__main__":
    main()
