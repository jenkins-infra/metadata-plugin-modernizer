// scripts/fetch_metadata.js (temporary for testing)
const fs = require('fs');

// Dummy metadata to test workflow
const metadata = [{ name: "dummy-plugin", deprecated: false }];

fs.writeFileSync('usage-by-plugins.json', JSON.stringify(metadata, null, 2));
console.log('Updated usage-by-plugins.json (dummy)');
