// Runs the WebAssembly TX-2 from web/tx2_host.h via tx2_wasm.cpp in a free-running loop.
// Main thread messages:
//   {id, cmd}                       one Machine::command line; replied as {id, result}
//   {type:'pen', x, y, down}        light-pen target in display units and contact
//   {type:'config', ...}            penLimit in units per 10,000 clocks, 0 disables; batchMs; paused
// Worker -> main: {type:'state', s, cursor, perf} after every batch.
import create from './tx2.js';

const machine = await create();
const call = line => {
  const text = machine.stringToNewUTF8(line);
  const out = machine.UTF8ToString(machine._tx2_command(text));
  machine._free(text);
  return out;
};

const config = {penLimit: 2, batchMs: 12, paused: false};
const target = {x: 0, y: 0, down: false};
const cursor = {x: 0, y: 0};
let clocks = 20000, busy = false;

self.onmessage = ({data}) => {
  if (data.type === 'pen') {
    target.x = data.x; target.y = data.y;
    // Lowering the pen starts it at the target; raised pens follow freely.
    if (data.down && !target.down || !data.down) { cursor.x = data.x; cursor.y = data.y; }
    target.down = data.down;
  } else if (data.type === 'config') {
    Object.assign(config, data.config);
  } else if (data.id !== undefined) {
    let result;
    try { result = JSON.parse(call(data.cmd)); } catch (e) { result = {error: String(e)}; }
    self.postMessage({id: data.id, result});
  }
};

const channel = new MessageChannel();
channel.port1.onmessage = tick;
const schedule = () => channel.port2.postMessage(0);

function tick() {
  if (config.paused) { setTimeout(schedule, 30); return; }
  const n = clocks;
  // The original tracking program loses a pen that moves too far between looks;
  // the optional limit moves the simulated pen toward the user's finger at a fixed rate.
  const dx = target.x - cursor.x, dy = target.y - cursor.y, len = Math.hypot(dx, dy);
  const step = config.penLimit > 0 && target.down ? Math.min(len, n * config.penLimit / 10000) : len;
  if (len) { cursor.x += dx / len * step; cursor.y += dy / len * step; }
  const start = performance.now();
  const s = JSON.parse(call(`run ${n} ${Math.round(cursor.x)} ${Math.round(cursor.y)} ${target.down ? 1 : 0}`));
  const ms = performance.now() - start;
  // Size the next batch to the frame budget.
  if (ms > 0.5 && s.running) clocks = Math.round(Math.max(2000, Math.min(2000000, clocks * config.batchMs / ms)));
  self.postMessage({type: 'state', s, cursor: {...cursor, lag: Math.hypot(target.x - cursor.x, target.y - cursor.y)}, perf: {ms, clocks: n}});
  // A stopped machine only needs polling for console input.
  if (s.running) schedule(); else setTimeout(schedule, 30);
}

self.postMessage({type: 'ready'});
schedule();
