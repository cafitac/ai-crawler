const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');
const metadataPath = path.join(repoRoot, 'lib', 'wrapper-metadata.json');
const gitHead = execFileSync('git', ['rev-parse', 'HEAD'], {
  cwd: repoRoot,
  encoding: 'utf8',
}).trim();

fs.mkdirSync(path.dirname(metadataPath), {recursive: true});
fs.writeFileSync(metadataPath, `${JSON.stringify({gitHead}, null, 2)}\n`);
