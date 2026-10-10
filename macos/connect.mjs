// Run by the launcher with T3 Code's own runtime (ELECTRON_RUN_AS_NODE=1):
//   connect.mjs <inspector port> <inject.cjs> <overlay dir>
// T3 Code waits at --inspect-brk for this. It installs inject.cjs, then always lets
// the app continue, customized or stock, and exits non-zero if the customization failed.
const [port, injectPath, overlay] = process.argv.slice(2);
const deadline = Date.now() + 30_000;

let targets = [];
while (!targets.length) {
  if (Date.now() > deadline) fail('T3 Code did not open its startup hook. This version may not allow it.');
  try {
    targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  } catch {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

const socket = new WebSocket(targets[0].webSocketDebuggerUrl);
const pending = new Map();
let nextId = 0;
let onPause;
const paused = new Promise((resolve) => (onPause = resolve));
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) pending.get(message.id)(message);
  if (message.method === 'Debugger.paused') onPause(message.params);
});
const send = (method, params = {}) =>
  new Promise((resolve) => {
    const id = ++nextId;
    pending.set(id, resolve);
    socket.send(JSON.stringify({ id, method, params }));
  });
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve);
  socket.addEventListener('error', () => reject(new Error('Could not connect to T3 Code.')));
}).catch((error) => fail(error.message));

let problem = null;
try {
  await send('Runtime.enable');
  await send('Debugger.enable');
  await send('Runtime.runIfWaitingForDebugger');
  const { callFrames } = await paused;
  const expression = `process.getBuiltinModule('node:module').createRequire(${JSON.stringify(injectPath)})(${JSON.stringify(injectPath)})` +
    `.install(${JSON.stringify(overlay)}, { closeInspector: true })`;
  const reply = await send('Debugger.evaluateOnCallFrame', { callFrameId: callFrames[0].callFrameId, expression });
  const result = reply.result?.result;
  if (reply.error || result?.type !== 'string') {
    problem = reply.error?.message ?? result?.description ?? 'unknown error';
  }
} catch (error) {
  problem = String(error);
} finally {
  await send('Debugger.resume');
  socket.close();
}
if (problem) fail('Could not load the customized build: ' + problem);

function fail(message) {
  console.error(message);
  process.exit(1);
}
