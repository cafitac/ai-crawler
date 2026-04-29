const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const metadataPath = path.join(repoRoot, 'lib', 'wrapper-metadata.json');

if (fs.existsSync(metadataPath)) {
  fs.unlinkSync(metadataPath);
}
