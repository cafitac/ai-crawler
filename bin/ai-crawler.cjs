#!/usr/bin/env node
const { runCli } = require('../lib/wrapper.cjs');
process.exitCode = runCli(process.argv.slice(2));
