// Runs the WebAssembly TX-2 from web/tx2_host.h via tx2_wasm.cpp in a free-running loop.
// Main thread messages:
//   {id, cmd}                       one Machine::command line; replied as {id, result}
//   {type:'pen', x, y, down}        light-pen target in display units and contact
//   {type:'config', ...}            penLimit; penTrace for clocked held strokes; penReset cancels a stroke; batchMs; paused
// Worker -> main: {type:'state', s, cursor, perf} after every batch.
import create from './tx2.js';

const machine = await create();
const call = line => {
  const text = machine.stringToNewUTF8(line);
  const out = machine.UTF8ToString(machine._tx2_command(text));
  machine._free(text);
  return out;
};

const config = {penLimit: 2, penTrace: false, batchMs: 12, paused: false};
const target = {x: 0, y: 0, down: false};
const cursor = {x: 0, y: 0, down: false};
const trace = [];
let traceHead = 0, dwell = 0, clocks = 20000, penVersion = 0, traceReady = false;
// Dwell for a raster scan, including the longer spot times in reference mode.
// Small spatial steps retain the path of a fast pointer gesture.
const TRACE_CLOCKS = 40000, TRACE_STEP = 10;
let traceClocks = TRACE_CLOCKS;

self.onmessage = ({data}) => {
  if (data.type === 'pen') {
    penVersion = data.version;
    if (config.penTrace) {
      const last = trace.length > traceHead ? trace[trace.length - 1] : cursor;
      if (last.x !== data.x || last.y !== data.y || last.down !== data.down) trace.push({x: data.x, y: data.y, down: data.down});
    }
    target.x = data.x; target.y = data.y;
    // Lowering the pen starts it at the target; raised pens follow freely.
    if (!config.penTrace && ((data.down && !target.down) || !data.down)) { cursor.x = data.x; cursor.y = data.y; }
    target.down = data.down;
  } else if (data.type === 'config') {
    const {penReset, ...next} = data.config;
    if (penReset || next.penTrace !== undefined) {
      trace.length = 0; traceHead = 0; dwell = 0;
      traceReady = false;
      cursor.down = false; target.down = false;
      cursor.x = target.x; cursor.y = target.y;
    }
    Object.assign(config, next);
  } else if (data.id !== undefined) {
    let result;
    if (config.penTrace && data.cmd.startsWith('press codabo ')) traceReady = false;
    try { result = JSON.parse(call(data.cmd)); } catch (e) { result = {error: String(e)}; }
    self.postMessage({id: data.id, result});
  }
};

const channel = new MessageChannel();
channel.port1.onmessage = tick;
const schedule = () => channel.port2.postMessage(0);

function tick() {
  if (config.paused) { setTimeout(schedule, 30); return; }
  let n = clocks;
  if (config.penTrace && !traceReady) {
    cursor.down = false;
    n = Math.min(n, TRACE_CLOCKS);
  } else if (config.penTrace) {
    if (!dwell && traceHead < trace.length) {
      const point = trace[traceHead];
      const dx = point.x - cursor.x, dy = point.y - cursor.y, len = Math.hypot(dx, dy);
      if (!point.down || !cursor.down || len <= TRACE_STEP) {
        cursor.x = point.x; cursor.y = point.y; cursor.down = point.down;
        traceHead++;
      } else {
        cursor.x += dx / len * TRACE_STEP; cursor.y += dy / len * TRACE_STEP;
      }
      dwell = cursor.down ? traceClocks : 0;
      if (traceHead === trace.length) { trace.length = 0; traceHead = 0; }
    }
    n = Math.min(n, dwell || TRACE_CLOCKS);
  } else {
    // Sketchpad's tracking cross follows the aim at the configured maximum speed.
    const dx = target.x - cursor.x, dy = target.y - cursor.y, len = Math.hypot(dx, dy);
    const step = config.penLimit > 0 && target.down ? Math.min(len, n * config.penLimit / 10000) : len;
    if (len) { cursor.x += dx / len * step; cursor.y += dy / len * step; }
    cursor.down = target.down;
  }
  const start = performance.now();
  const s = JSON.parse(call(`run ${n} ${Math.round(cursor.x)} ${Math.round(cursor.y)} ${cursor.down ? 1 : 0}`));
  dwell = Math.max(0, dwell - n);
  traceClocks = Math.max(TRACE_CLOCKS, s.ticksPerUs * 20000);
  // Native display events mark readiness; input stays in the machine's light-pen path.
  if (config.penTrace && !traceReady) traceReady = s.display.some(([x, y, , unit]) => x === -255 && y === 225 && unit === 0o60);
  const ms = performance.now() - start;
  // Size the next batch to the frame budget.
  if (ms > 0.5 && s.running) clocks = Math.round(Math.max(2000, Math.min(2000000, clocks * config.batchMs / ms)));
  self.postMessage({type: 'state', s, cursor: {...cursor, version: penVersion, ready: traceReady, lag: Math.hypot(target.x - cursor.x, target.y - cursor.y), pending: trace.length - traceHead + (dwell ? 1 : 0)}, perf: {ms, clocks: n}});
  // A stopped machine only needs polling for console input.
  if (s.running) schedule(); else setTimeout(schedule, 30);
}

self.postMessage({type: 'ready'});
schedule();
