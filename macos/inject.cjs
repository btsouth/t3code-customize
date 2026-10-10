// Loads a t3code-customize build into the stock, still-signed T3 Code on macOS.
//
// The launcher evaluates this in the main process while it waits at --inspect-brk,
// before any app code runs. From then on, every bundle file the app loads from
// app.asar is served from the overlay when the overlay has it, under its original
// path, so __dirname, `electron` and the app's native modules resolve as in stock.
// The main process hands this file to its backend with --require, which does the same.
'use strict';
const childProcess = require('node:child_process');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const { fileURLToPath, pathToFileURL } = require('node:url');

const OVERLAY_ENV = 'T3CODE_CUSTOMIZE_OVERLAY';
// Rebuilt bundles, by their path inside app.asar. The web client is read with fs, not loaded.
const BUNDLES = ['apps/desktop/dist-electron/', 'apps/server/dist/'];
const CLIENT = 'apps/server/dist/client';
const FORMATS = { '.cjs': 'commonjs', '.mjs': 'module' };

let installed = false;

function install(overlay, { closeInspector = false } = {}) {
  if (installed) return 'already installed';
  installed = true;
  overlay = path.resolve(overlay);
  const asar = path.resolve(process.execPath, '../../Resources/app.asar');
  const stockClient = path.join(asar, CLIENT);
  const overlayClient = path.join(overlay, CLIENT);
  if (!fs.existsSync(path.join(overlay, BUNDLES[0], 'main.cjs'))) {
    throw new Error('No customized build at ' + overlay);
  }

  // The overlay copy of an app.asar bundle file, or null to load the stock one.
  const replacement = (file) => {
    if (!file.startsWith(asar + path.sep) || !FORMATS[path.extname(file)]) return null;
    const relative = file.slice(asar.length + 1);
    if (relative.startsWith(CLIENT + '/') || !BUNDLES.some((prefix) => relative.startsWith(prefix))) return null;
    const candidate = path.join(overlay, relative);
    return fs.existsSync(candidate) ? candidate : null;
  };

  const target = (specifier, parentURL) => {
    if (specifier.startsWith('file:')) return fileURLToPath(specifier);
    if (path.isAbsolute(specifier)) return specifier;
    if ((specifier.startsWith('./') || specifier.startsWith('../')) && parentURL?.startsWith('file:')) {
      return path.resolve(path.dirname(fileURLToPath(parentURL)), specifier);
    }
    return null;
  };

  let started = false;
  const start = () => {
    // Late, so these wrap Electron's own asar-aware fs rather than being wrapped by it.
    if (started) return;
    started = true;
    redirectClient(stockClient, overlayClient);
    passToChildren(asar, overlay);
    if (closeInspector) setImmediate(() => require('node:inspector').close());
  };

  Module.registerHooks({
    resolve(specifier, context, next) {
      const file = target(specifier, context.parentURL);
      // Chunks new in this build do not exist in app.asar; resolve them by name.
      if (file && replacement(file)) {
        return { url: pathToFileURL(file).href, format: FORMATS[path.extname(file)], shortCircuit: true };
      }
      return next(specifier, context);
    },
    load(url, context, next) {
      const file = url.startsWith('file:') ? fileURLToPath(url) : null;
      const source = file && replacement(file);
      if (!source) return next(url, context);
      start();
      return { format: FORMATS[path.extname(file)], source: fs.readFileSync(source), shortCircuit: true };
    },
  });
  return 'customized build loaded from ' + overlay;
}

// Serve the web client from the overlay wherever the app reads it with fs.
function redirectClient(stock, overlay) {
  const map = (value) => {
    if (typeof value === 'string' && (value === stock || value.startsWith(stock + path.sep))) {
      return overlay + value.slice(stock.length);
    }
    if (value instanceof URL && value.protocol === 'file:') {
      const mapped = map(fileURLToPath(value));
      return typeof mapped === 'string' && mapped.startsWith(overlay) ? pathToFileURL(mapped) : value;
    }
    return value;
  };
  const wrap = (object, names) => {
    for (const name of names) {
      const original = object[name];
      if (typeof original !== 'function') continue;
      const wrapped = function (first, ...rest) {
        return original.call(this, map(first), ...rest);
      };
      Object.defineProperties(wrapped, Object.getOwnPropertyDescriptors(original));
      object[name] = wrapped;
    }
  };
  const names = ['access', 'createReadStream', 'exists', 'lstat', 'open', 'opendir', 'readFile', 'readdir', 'realpath', 'stat'];
  wrap(fs, [...names, ...names.map((name) => name + 'Sync')]);
  wrap(fs.promises, names);
}

// Child processes that run a bundle from app.asar (the backend and its workers) get this file too.
function passToChildren(asar, overlay) {
  const runsBundle = (command, args) =>
    command === process.execPath && Array.isArray(args) &&
    args.some((arg) => typeof arg === 'string' && arg.startsWith(asar + path.sep) &&
      BUNDLES.some((prefix) => arg.slice(asar.length + 1).startsWith(prefix)));
  const withOverlay = (options) => ({ ...options, env: { ...(options?.env ?? process.env), [OVERLAY_ENV]: overlay } });
  for (const name of ['spawn', 'execFile']) {
    const original = childProcess[name];
    childProcess[name] = function (command, args, options, ...rest) {
      if (runsBundle(command, args) && !args.includes(__filename)) {
        // execFile(file, args, callback): keep the callback.
        if (typeof options === 'function') [options, rest] = [undefined, [options, ...rest]];
        args = ['--require', __filename, ...args];
        options = withOverlay(options);
      }
      return original.call(this, command, args, options, ...rest);
    };
  }
  const fork = childProcess.fork;
  childProcess.fork = function (modulePath, args, options) {
    if (!Array.isArray(args)) [args, options] = [[], args];
    const file = typeof modulePath === 'string' ? modulePath : modulePath instanceof URL ? fileURLToPath(modulePath) : '';
    if (runsBundle(process.execPath, [file])) {
      const execArgv = options?.execArgv ?? process.execArgv;
      options = withOverlay({ ...options, execArgv: execArgv.includes(__filename) ? execArgv : ['--require', __filename, ...execArgv] });
    }
    return fork.call(this, modulePath, args, options);
  };
}

module.exports = { install };

// Loaded with --require in a child of the customized app.
if (process.env[OVERLAY_ENV] && require.main !== module) install(process.env[OVERLAY_ENV]);
