const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const wrapper = require('../lib/wrapper.cjs');

test('buildCoreCommand uses local uv run inside repo checkout', () => {
  const command = wrapper.buildCoreCommand({
    cwd: '/tmp/work',
    packageRoot: '/repo/ai-crawler',
    argv: ['auto', 'evidence.json', '--json'],
    localCoreAvailable: true,
  });

  assert.deepEqual(command, {
    executable: 'uv',
    args: ['run', '--project', '/repo/ai-crawler', 'ai-crawler', 'auto', 'evidence.json', '--json'],
  });
});

test('buildCoreCommand pins published python core to the wrapper gitHead outside repo checkout', () => {
  const command = wrapper.buildCoreCommand({
    cwd: '/tmp/work',
    packageRoot: '/repo/ai-crawler',
    argv: ['mcp'],
    localCoreAvailable: false,
    packageMetadata: {
      version: '0.1.1',
      gitHead: '0b448490d03e136158b3d76bce06d90b2852b0e3',
    },
  });

  assert.deepEqual(command, {
    executable: 'uvx',
    args: [
      '--python',
      '3.11',
      '--from',
      'ai-crawler[all] @ git+https://github.com/cafitac/ai-crawler.git@0b448490d03e136158b3d76bce06d90b2852b0e3',
      'ai-crawler',
      'mcp',
    ],
  });
});

test('buildCoreCommand honors env overrides for published python spec', () => {
  const command = wrapper.buildCoreCommand({
    cwd: '/tmp/work',
    packageRoot: '/repo/ai-crawler',
    argv: ['doctor'],
    localCoreAvailable: false,
    packageMetadata: {
      version: '0.1.1',
      gitHead: '0b448490d03e136158b3d76bce06d90b2852b0e3',
    },
    env: {
      AI_CRAWLER_PYTHON_SPEC: 'ai-crawler[http,mcp]',
      AI_CRAWLER_UVX_PYTHON: '3.13',
    },
  });

  assert.deepEqual(command, {
    executable: 'uvx',
    args: ['--python', '3.13', '--from', 'ai-crawler[http,mcp]', 'ai-crawler', 'doctor'],
  });
});

test('publishedPythonSpec falls back to unpinned git source when package gitHead is unavailable', () => {
  const spec = wrapper.publishedPythonSpec({}, {version: '0.1.1'});
  assert.equal(spec, 'git+https://github.com/cafitac/ai-crawler.git[all]');
});

test('readPackageMetadata loads wrapper metadata gitHead when present', () => {
  const packageRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-crawler-wrapper-'));
  fs.mkdirSync(path.join(packageRoot, 'lib'), {recursive: true});
  fs.writeFileSync(
    path.join(packageRoot, 'package.json'),
    JSON.stringify({version: '0.1.1'}, null, 2),
  );
  fs.writeFileSync(
    path.join(packageRoot, 'lib', 'wrapper-metadata.json'),
    JSON.stringify({gitHead: 'abc123'}, null, 2),
  );

  const metadata = wrapper.readPackageMetadata(packageRoot);

  assert.deepEqual(metadata, {version: '0.1.1', gitHead: 'abc123'});
});

test('runCli prints wrapper help for top-level --help without spawning the core CLI', () => {
  const calls = [];
  const exitCode = wrapper.runCli(['--help'], {
    packageRoot: '/repo/ai-crawler',
    spawnSync: (...args) => {
      calls.push(args);
      return {status: 0};
    },
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(calls, []);
});

test('runCli delegates subcommand --help to the core CLI', () => {
  const calls = [];
  const exitCode = wrapper.runCli(['mcp-config', '--help'], {
    packageRoot: '/repo/ai-crawler',
    localCoreAvailable: true,
    spawnSync: (executable, args) => {
      calls.push({executable, args});
      return {status: 0};
    },
  });

  assert.equal(exitCode, 0);
  assert.deepEqual(calls, [
    {
      executable: 'uv',
      args: ['run', '--project', '/repo/ai-crawler', 'ai-crawler', 'mcp-config', '--help'],
    },
  ]);
});

test('packageRootFromModuleDir resolves package root from lib directory', () => {
  const packageRoot = wrapper.packageRootFromModuleDir(path.join('/repo/ai-crawler', 'lib'));
  assert.equal(packageRoot, '/repo/ai-crawler');
});
