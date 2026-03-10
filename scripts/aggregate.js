import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Paths
const repoRoot = path.join(__dirname, "..");
const pluginsDir = repoRoot;
const usageFile = path.join(
  __dirname,
  "usage-in-plugins-output",
  "usage-by-plugin.json"
);

// Load usage data
const usageData = JSON.parse(fs.readFileSync(usageFile, "utf-8"));

// Build set of plugins using deprecated APIs
const deprecatedPlugins = new Set(
  Object.entries(usageData)
    .filter(([plugin, data]) =>
      (data.methods && data.methods.length > 0) ||
      (data.classes && data.classes.length > 0) ||
      (data.fields && data.fields.length > 0)
    )
    .map(([plugin]) => plugin)
);

// Read plugin folders
const pluginFolders = fs.readdirSync(pluginsDir).filter((name) => {
  const fullPath = path.join(pluginsDir, name);
  return (
    fs.statSync(fullPath).isDirectory() &&
    name !== "deprecated-apis-chart-app" &&
    name !== "scripts" &&
    !name.startsWith(".")
  );
});

const result = [];

for (const plugin of pluginFolders) {
  result.push({
    plugin_name: plugin,
    deprecated_apis_used: deprecatedPlugins.has(plugin),
  });
}

// Write output
const outputPath = path.join(
  repoRoot,
  "deprecated-apis-chart-app",
  "src",
  "data",
  "pluginsAggregated.json"
);

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));

console.log(`Generated pluginsAggregated.json with ${result.length} plugins`);