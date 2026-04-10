import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, "..");

const folders = fs.readdirSync(ROOT_DIR);

const pluginFolders = folders.filter((folder) => {
  const fullPath = path.join(ROOT_DIR, folder);
  return fs.statSync(fullPath).isDirectory() && folder !== "utils";
});

for (const plugin of pluginFolders) {
  const filePath = path.join(
    ROOT_DIR,
    plugin,
    "reports",
    "aggregated_migrations.json"
  );

  if (!fs.existsSync(filePath)) continue;

  const raw = fs.readFileSync(filePath, "utf8");
  const data = JSON.parse(raw);

  console.log("Plugin:", plugin);
  console.log("Type:", typeof data);
  console.log("Keys:", Object.keys(data));
  break; // only inspect first plugin
}
