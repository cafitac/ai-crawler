const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function packageRootFromModuleDir(moduleDir = __dirname) {
  return path.resolve(moduleDir, '..');
}

function localCoreAvailable(packageRoot) {
  return fs.existsSync(path.join(packageRoot, 'pyproject.toml'));
}

function readPackageMetadata(packageRoot = packageRootFromModuleDir()) {
  const packageJsonPath = path.join(packageRoot, 'package.json');
  if (!fs.existsSync(packageJsonPath)) {
    return {};
  }

  const packageMetadata = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
  const wrapperMetadataPath = path.join(packageRoot, 'lib', 'wrapper-metadata.json');
  if (!fs.existsSync(wrapperMetadataPath)) {
    return packageMetadata;
  }

  const wrapperMetadata = JSON.parse(fs.readFileSync(wrapperMetadataPath, 'utf8'));
  return {...packageMetadata, ...wrapperMetadata};
}

function publishedPythonSpec(env = process.env, packageMetadata = {}) {
  if (env.AI_CRAWLER_PYTHON_SPEC) {
    return env.AI_CRAWLER_PYTHON_SPEC;
  }
  if (packageMetadata.gitHead) {
    return `ai-crawler[all] @ git+https://github.com/cafitac/ai-crawler.git@${packageMetadata.gitHead}`;
  }
  return 'git+https://github.com/cafitac/ai-crawler.git[all]';
}

function uvxPythonVersion(env = process.env) {
  return env.AI_CRAWLER_UVX_PYTHON || '3.11';
}

function buildCoreCommand({
  argv,
  packageRoot = packageRootFromModuleDir(),
  localCoreAvailable: hasLocalCore = localCoreAvailable(packageRoot),
  packageMetadata = readPackageMetadata(packageRoot),
  env = process.env,
}) {
  if (hasLocalCore) {
    return {
      executable: 'uv',
      args: ['run', '--project', packageRoot, 'ai-crawler', ...argv],
    };
  }

  return {
    executable: 'uvx',
    args: [
      '--python',
      uvxPythonVersion(env),
      '--from',
      publishedPythonSpec(env, packageMetadata),
      'ai-crawler',
      ...argv,
    ],
  };
}

function printHelp(packageRoot = packageRootFromModuleDir()) {
  const packageMetadata = readPackageMetadata(packageRoot);
  const version = packageMetadata.version || '0.0.0';

  console.log(`ai-crawler npm wrapper v${version}

Usage:
  ai-crawler <core-cli-args...>

Behavior:
  - In the repo checkout, uses local Python core via 'uv run --project <repo> ai-crawler ...'
  - Outside the repo, uses published Python core via 'uvx --from "${publishedPythonSpec(process.env, packageMetadata)}" ai-crawler ...'

Environment overrides:
  - AI_CRAWLER_PYTHON_SPEC   Override published Python package spec (default: published package gitHead when available, otherwise git+https://github.com/cafitac/ai-crawler.git[all])
  - AI_CRAWLER_UVX_PYTHON    Override uvx Python version (default: 3.11)`);
}

function shouldPrintWrapperHelp(args) {
  return args.length === 0 || (args.length === 1 && (args[0] === '--help' || args[0] === '-h' || args[0] === 'help'));
}

function runCli(argv, options = {}) {
  const args = Array.isArray(argv) ? argv : [];
  if (shouldPrintWrapperHelp(args)) {
    printHelp(options.packageRoot || packageRootFromModuleDir());
    return 0;
  }

  if (args.includes('--version') || args.includes('-V')) {
    const command = buildCoreCommand({
      argv: ['--version'],
      packageRoot: options.packageRoot,
      localCoreAvailable: options.localCoreAvailable,
      env: options.env,
    });
    return executeCommand(command, options);
  }

  const command = buildCoreCommand({
    argv: args,
    packageRoot: options.packageRoot,
    localCoreAvailable: options.localCoreAvailable,
    env: options.env,
  });
  return executeCommand(command, options);
}

function executeCommand(command, options = {}) {
  const spawn = options.spawnSync || spawnSync;
  const result = spawn(command.executable, command.args, {
    stdio: 'inherit',
    env: options.env || process.env,
    cwd: options.cwd || process.cwd(),
  });

  if (typeof result.status === 'number') {
    return result.status;
  }
  return 1;
}

module.exports = {
  buildCoreCommand,
  localCoreAvailable,
  packageRootFromModuleDir,
  printHelp,
  publishedPythonSpec,
  readPackageMetadata,
  runCli,
  shouldPrintWrapperHelp,
};
