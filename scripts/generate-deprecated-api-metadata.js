import fs from "fs";
import path from "path";

const inputPath = path.resolve("scripts/usage-in-plugins-output/usage-by-plugin.json");
const outputDir = path.resolve("generated");
const outputPath = path.join(outputDir, "deprecated-api-usage.json");

const raw = fs.readFileSync(inputPath, "utf-8");
const parsed = JSON.parse(raw);

// Handle both array and object input shapes safely
const entries = Array.isArray(parsed) ? parsed : Object.values(parsed);

const result = {};

for (const entry of entries) {
  const pluginId =
    entry.plugin?.split(":")[0] ||
    entry.name ||
    entry.id;

  if (!pluginId) continue;

  const methods = Array.isArray(entry.methods) ? entry.methods : [];
  const classes = Array.isArray(entry.classes) ? entry.classes : [];
  const fields = Array.isArray(entry.fields) ? entry.fields : [];

  result[pluginId] = {
    plugin: entry.plugin || pluginId,
    deprecatedApiUsage: {
      methods,
      classes,
      fields,
      hasDeprecatedUsage:
        methods.length > 0 || classes.length > 0 || fields.length > 0
    }
  };
}

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + "\n");

const totalPlugins = Object.keys(result).length;
const deprecatedCount = Object.values(result).filter(
  (entry) => entry.deprecatedApiUsage.hasDeprecatedUsage
).length;
const safeCount = totalPlugins - deprecatedCount;

console.log(`Generated ${outputPath}`);
console.log(`Total plugins: ${totalPlugins}`);
console.log(`Deprecated usage: ${deprecatedCount}`);
console.log(`No deprecated usage: ${safeCount}`);
