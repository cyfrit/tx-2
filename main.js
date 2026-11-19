// TX-2 in the browser: WebAssembly RTL in a worker, with console, scope and peripherals.
import {$, el, oct, loadSettings, saveSettings, download} from './util.js';
import {Machine} from './machine.js';
import {Scope} from './crt.js';
import {Console} from './console.js';
import {TapePanel} from './tape.js';
import {Writer} from './writer.js';
import {Inputs} from './inputs.js';
import {Settings} from './settings.js';
import {MagTapePanel} from './magtape.js';
import {PrintAnalogPanel} from './printanalog.js';
import {MiscPanel} from './misc.js';

const settings = loadSettings();
let saveTimer = 0;
const save = () => { clearTimeout(saveTimer); saveTimer = setTimeout(() => saveSettings(settings), 300); };
const toast = msg => { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(t.timer); t.timer = setTimeout(() => t.classList.remove('show'), 2600); };

// Tabs
const tabs = {}, pages = $('#pages'), nav = $('#tabs');
for (const [id, name] of [['console', 'Console'], ['tape', 'Paper tape'], ['magtape', 'Magnetic tape'], ['writer', 'Typewriters'], ['printanalog', 'Print and analog'], ['inputs', 'Inputs'], ['settings', 'Settings']]) {
  const page = el('div', {class: 'page', id: `page-${id}`});
  const btn = el('button', {}, name);
  btn.onclick = () => show(id);
  nav.append(btn); pages.append(page);
  tabs[id] = {page, btn};
}
function show(id) {
  for (const [k, t] of Object.entries(tabs)) { t.page.classList.toggle('active', k === id); t.btn.classList.toggle('active', k === id); }
  if (id === 'writer') tabs.writer.btn.textContent = 'Typewriters';
  tape?.redraw();
}

const machine = new Machine();
const boot = $('#boot');
let state = null, inputs = null, tape = null, running = false, paused = false;
const scope = new Scope({
  beam: $('#beam'), glow: $('#glow'), overlay: $('#overlay'), settings,
  onPen: (x, y, down) => { machine.pen(x, y, down); $('#pen-toggle').textContent = down ? 'Light pen ▼' : 'Light pen ▲'; $('#pen-toggle').classList.toggle('lit', down); },
  onTap: () => { if (inputs?.template) inputs.whenPenArrives(() => inputs.tap(7, 80000, 80000)); },
});
const con = new Console(tabs.console.page, {machine, settings, save, toast});
tape = new TapePanel(tabs.tape.page, {machine, toast, onLibraryLoad: async (entry, start) => {
  inputs.setTemplate(entry.template);
  // Console setup the program expects, e.g. suppressing IOSAL for units this machine lacks.
  if (entry.suppress) {
    settings.console.suppress |= parseInt(entry.suppress, 8); con.paintSuppress(); save();
    await machine.cmd(`set suppress ${settings.console.suppress}`);
  }
  if (start) {
    settings.console.tsp = parseInt(entry.tsp, 8); con.applyTsp();
    scope.clear(); scope.setPen(false);
    await machine.cmd(`press codabo ${settings.console.tsp}`);
    toast(`CODABO ${entry.tsp}: plugboard loading the leader and reading tape`);
  }
}});
const writer = new Writer(tabs.writer.page, {machine, toast});
const secondWriter = new Writer(tabs.writer.page, {machine, toast, inputUnit: 'lw71', outputUnit: 'lw72'});
const misc = new MiscPanel(tabs.console.page, {machine});
const magtape = new MagTapePanel(tabs.magtape.page, {machine, toast});
const printanalog = new PrintAnalogPanel(tabs.printanalog.page, {machine});
inputs = new Inputs(tabs.inputs.page, {machine, settings, save, console: con, scope, toast});
const prefs = new Settings(tabs.settings.page, {machine, settings, save, scope});
show('tape');

// Header controls
$('#pause').onclick = () => { paused = !paused; machine.config({paused}); $('#pause').textContent = paused ? '▶' : '❚❚'; $('#pause').classList.toggle('lit', paused); };
$('#step').onclick = async () => {
  if (!paused) $('#pause').click();
  const s = await machine.cmd(`run 1000000 ${Math.round(scope.pen.x)} ${Math.round(scope.pen.y)} ${scope.pen.active ? 1 : 0} 1`);
  dispatch({s, cursor: {x: scope.pen.x, y: scope.pen.y, lag: 0}});
};
$('#power').onclick = async () => {
  await machine.cmd('power');
  await applyAll(); scope.clear();
  for (const w of [writer, secondWriter]) w.state = {script: 'normal', upper: false, red: false};
  toast('Power-on reset: memory cleared and console settings reloaded');
};
$('#pen-toggle').onclick = () => scope.setPen(!scope.pen.active);
$('#camera').onclick = () => download(`tx2-${Date.now()}.png`, dataURLToBlob(scope.snapshot()));
function dataURLToBlob(url) { const b = atob(url.split(',')[1]); return new Blob([Uint8Array.from(b, c => c.charCodeAt(0))], {type: 'image/png'}); }

// Keyboard: template keys and pen, unless typing into a field or the typewriter paper.
addEventListener('keydown', e => {
  if (e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.target.closest('input,textarea,select,.paper')) return;
  if (e.key === 'Escape') scope.setPen(false);
  const keys = {d: 7, m: 5, c: 6};
  if (inputs.template && keys[e.key.toLowerCase()] !== undefined) inputs.tap(keys[e.key.toLowerCase()], 80000);
});

// Machine state from the worker
let lastHits = 0, films = 0;
let perf = {t: performance.now(), cycles: 0, retired: 0};
const LIMBO_DELAY_MS = 300;
let limboSince = null;
function dispatch({s, cursor}) {
  state = s;
  scope.pen.cursorX = cursor.x; scope.pen.cursorY = cursor.y; scope.pen.lag = cursor.lag;
  con.update(s); tape.update(s); writer.update(s); inputs.update(s, cursor);
  secondWriter.update(s); misc.update(s);
  magtape.update(s);
  printanalog.update(s);
  if (s.writer.length && !tabs.writer.page.classList.contains('active')) tabs.writer.btn.textContent = 'Typewriters ●';
  if (s.camera) { films++; download(`tx2-film-${films}.png`, dataURLToBlob(scope.snapshot())); toast('Camera: saved the program-requested frame'); }
  if (s.display.length) scope.addSpots(s.display, s.cycles, s.ticksPerUs);
  else scope.cycles = s.cycles;
  if (s.running || s.display.length) boot.classList.add('hidden');
  $('#pen-lamp').classList.toggle('on', s.hits !== lastHits); lastHits = s.hits;
  const sign = v => `${v >= 0 ? '+' : ''}${Math.round(v)}`;
  $('#pen-pos').textContent = `X ${sign(scope.pen.x)} Y ${sign(scope.pen.y)}${cursor.lag > 2 ? ` · lag ${Math.round(cursor.lag)}` : ''}`;
  // Report stop causes using fault codes from rtl/tx2_core.v and RTL-STATUS.md.
  if (running && !s.running && s.fault > 1) {
    const why = {2: 'undefined OPR mode', 3: 'selection address error: PSAL/QSAL', 4: 'write to read-only memory', 5: 'internal state', 6: 'unsupported operation', 7: 'parity alarm', 8: 'IOSAL: selected device is not connected'}[s.fault] || '';
    toast(`Stopped · fault ${s.fault} ${why}. Suppress the corresponding alarm on the console and press CALACO to continue.`);
  }
  running = !!s.running;
  $('#run-lamp').classList.toggle('on', running);
  const now = performance.now();
  // Short sequence waits during tape I/O do not change the header status.
  limboSince = !paused && running && s.limbo ? (limboSince ?? now) : null;
  const waiting = limboSince !== null && now - limboSince >= LIMBO_DELAY_MS;
  const runText = $('#run-text');
  const status = paused ? 'PAUSED' : running ? (waiting ? 'LIMBO' : 'RUN') : s.fault ? `STOP·${s.fault}` : 'STOP';
  if (runText.textContent !== status) runText.textContent = status;
  $('#where').textContent = `K ${oct(s.k, 2)} · P ${oct(s.pc, 6)}`;
  if (now - perf.t >= 1000) {
    const seconds = (now - perf.t) / 1000;
    const clocksPerSecond = (s.cycles - perf.cycles) / seconds;
    const instructionsPerSecond = (s.retired - perf.retired) / seconds;
    perf = {t: now, cycles: s.cycles, retired: s.retired};
    prefs.updateStats([
      `Simulation   ${(clocksPerSecond / 1e6).toFixed(2)} Mclocks/s, ${Math.round(instructionsPerSecond).toLocaleString()} instructions/s`,
      `Device time  ${(clocksPerSecond / s.ticksPerUs / 1e6).toFixed(2)} × real time; ${s.ticksPerUs} clocks = 1 μs`,
      `Totals       ${s.cycles.toLocaleString()} clocks, ${s.retired.toLocaleString()} instructions, ${s.points.toLocaleString()} spots`,
      `Light pen    lag ${cursor.lag.toFixed(1)} units, ${s.hits} hits`,
    ].join('\n'));
  }
}
machine.onState(dispatch);

async function applyAll() { await con.apply(); await inputs.apply(); await prefs.apply(); }

machine.ready.then(async () => {
  await applyAll();
  await tape.loadLibrary();
  boot.textContent = 'Power on.\nSelect a tape on the Paper tape tab, then choose Load and start.';
}).catch(e => { boot.textContent = `Unable to start WebAssembly: ${e.message}`; });

// Test and debugging hook.
window.tx2 = {machine, settings, scope, inputs, tape, magtape, writer, get state() { return state; }, show};
