// Operator console: registers, action buttons, alarms, TSP and toggle registers. Users Handbook ch. 5.
import {el, oct, parseOct, bitName, bit36, setBit36} from './util.js';

const ALARMS = ['MPAL', 'NPAL', 'XPAL', 'FPAL', 'PSAL', 'QSAL', 'OCSAL', 'IOSAL', 'MISAL'];
const ALARM_HELP = ['M register parity', 'N register parity', 'X memory parity', 'F memory parity', 'P selection', 'Q selection', 'Illegal opcode', 'I/O selection', 'Missed data'];
const UNITS = [[0o41, 'Alarms'], [0o52, 'PETR'], [0o54, 'Timer'], [0o55, 'Light pen'], [0o56, 'Display 56'], [0o60, 'Display 60'],
  [0o61, 'Random numbers'], [0o63, 'Punch'], [0o65, 'LW1 keyboard'], [0o66, 'LW1 printer'], [0o71, 'LW2 keyboard'], [0o72, 'LW2 printer'],
  [0o47, 'Miscellaneous input'], [0o75, 'Relays']];

// Toggle levers for an n-bit word, grouped in octal digits, with bit 1.1 rightmost.
export function toggleRow(n, get, set, {meta} = {}) {
  const root = el('div', {class: 'toggles'});
  const levers = [];
  let group = null;
  if (meta) {
    const m = el('div', {class: 'tg meta', title: 'META'});
    m.onclick = () => meta.set(!meta.get());
    root.append(el('div', {class: 'group'}, m));
    levers.meta = m;
  }
  for (let i = n - 1; i >= 0; i--) {
    if ((i + 1) % 3 === 0 || i === n - 1) { group = el('div', {class: 'group'}); root.append(group); }
    const t = el('div', {class: 'tg', title: bitName(i)});
    t.onclick = () => set(setBit36(get(), i, !bit36(get(), i)));
    levers[i] = t; group.append(t);
  }
  root.refresh = () => {
    const v = get();
    for (let i = 0; i < n; i++) levers[i].classList.toggle('on', !!bit36(v, i));
    if (meta) levers.meta.classList.toggle('on', !!meta.get());
  };
  root.refresh();
  return root;
}

function lampRow(n) {
  const row = el('div', {class: 'lamprow'}), lamps = [];
  for (let q = Math.ceil(n / 9) - 1; q >= 0; q--) {
    const g = el('div', {class: 'q'});
    for (let b = Math.min(8, n - 1 - q * 9); b >= 0; b--) { const l = el('span', {class: 'lamp'}); lamps[q * 9 + b] = l; g.append(l); }
    row.append(g);
  }
  row.lamps = lamps;
  return row;
}

export class Console {
  constructor(page, {machine, settings, save, toast}) {
    Object.assign(this, {machine, settings, save, toast});
    const c = settings.console;
    const sub = el('div', {class: 'subtabs'});
    const run = el('div', {class: 'sub-page active'}), sw = el('div', {class: 'sub-page'});
    for (const [name, p] of [['Run', run], ['Switches', sw]]) {
      const b = el('button', {class: p === run ? 'active' : ''}, name);
      b.onclick = () => { for (const x of sub.children) x.classList.remove('active'); b.classList.add('active'); run.classList.toggle('active', p === run); sw.classList.toggle('active', p === sw); };
      sub.append(b);
    }
    page.append(sub, run, sw);

    // Registers
    this.regs = {};
    const regs = el('div', {class: 'regs'});
    for (const [name, bits] of [['A', 36], ['B', 36], ['C', 36], ['D', 36], ['E', 36], ['N', 36], ['P', 17], ['Q', 17], ['K', 6]]) {
      const row = lampRow(bits), val = el('span', {class: 'val'});
      this.regs[name] = {row, val, bits, last: null};
      regs.append(el('span', {class: 'name'}, name), row, val);
    }
    run.append(el('fieldset', {}, el('legend', {}, 'Registers'), regs));

    // Action buttons
    const act = (label, cmd, cls = '', title = '') => {
      const b = el('button', {class: `key ${cls}`, title}, label);
      b.onclick = () => { this.machine.cmd(cmd()); };
      return b;
    };
    this.hold = el('input', {type: 'checkbox'});
    this.hold.checked = c.hold;
    this.hold.onchange = () => { c.hold = this.hold.checked; this.save(); this.machine.cmd(`set hold ${c.hold ? 1 : 0}`); };
    run.append(el('fieldset', {}, el('legend', {}, 'Action buttons'), el('div', {class: 'row'},
      act('CODABO', () => `press codabo ${c.tsp}`, 'red', 'Clear flags, preset controls and start at TSP'),
      act('STARTOVER', () => `press startover ${c.tsp}`, '', 'Set sequence 0 flag and resume at TSP'),
      act('STOP', () => 'press stop', 'dark', 'Stop after the current instruction'),
      act('CALACO', () => 'press calaco', '', 'Clear alarms and continue'),
      act('PRESET', () => 'press preset', 'dark', 'Preset control flip-flops while stopped'),
      act('RESET', () => `press resetstart ${c.tsp}`, 'dark', 'Set the starting-point register to TSP'),
      act('CLR ALARMS', () => 'press clearalarms', 'dark'),
      act('CLR CLOCK', () => 'press clearclock', 'dark', 'Clear real-time clock 377630'),
      el('label', {class: 'check', title: 'Treat every instruction as a hold instruction'}, this.hold, 'HOLD'))));

    // Alarms with suppression
    this.alarmTiles = ALARMS.map((name, i) => {
      const lamp = el('span', {class: 'lamp red'}), sup = el('span', {class: 'sup'}, 'SUPP');
      const tile = el('div', {class: 'alarm', title: `${ALARM_HELP[i]}; click to toggle suppression`}, lamp, name, sup);
      tile.onclick = () => { c.suppress ^= 1 << i; this.save(); this.machine.cmd(`set suppress ${c.suppress}`); this.paintSuppress(); };
      return {tile, lamp};
    });
    run.append(el('fieldset', {}, el('legend', {}, 'Alarms · top lamp signals alarm, SUPP signals suppression'), el('div', {class: 'alarms'}, this.alarmTiles.map(a => a.tile))));
    this.paintSuppress();

    this.unitLamps = UNITS.map(([u, name]) => { const l = el('span', {class: 'lamp small green'}); return {u, l, e: el('span', {}, l, `${oct(u, 2)} ${name}`)}; });
    run.append(el('fieldset', {}, el('legend', {}, 'Connected devices'), el('div', {class: 'units'}, this.unitLamps.map(x => x.e))));

    // Switches page: TSP, toggle registers, fixed start registers.
    const tspInput = el('input', {type: 'text', class: 'octal', value: oct(c.tsp, 6)});
    const tsp = toggleRow(17, () => c.tsp, v => { c.tsp = v; this.applyTsp(); });
    this.applyTsp = () => { tsp.refresh(); tspInput.value = oct(c.tsp, 6); this.save(); this.machine.cmd(`set tsp ${c.tsp}`); };
    tspInput.onchange = () => { const v = parseOct(tspInput.value, 0o377777); if (v === null) return this.toast('TSP must be octal, at most 377777'); c.tsp = v; this.applyTsp(); };
    sw.append(el('fieldset', {}, el('legend', {}, 'TSP toggle switches · sequence 0 starting point'),
      el('div', {class: 'row'}, tsp), el('div', {class: 'row'}, el('span', {class: 'label'}, 'Octal'), tspInput,
        act('CODABO', () => `press codabo ${c.tsp}`, 'red'),
        el('button', {class: 'key dark', onclick: () => { c.tsp = 0o377750; this.applyTsp(); }}, 'Plugboard 377750'))));

    let word = 4;
    const sel = el('select', {}, Array.from({length: 16}, (_, i) => el('option', {value: i, selected: i === word}, `${oct(0o377720 + i)}`)));
    const wInput = el('input', {type: 'text', class: 'octal'});
    const wrow = toggleRow(36, () => c.toggles[word], v => { c.toggles[word] = v; this.applyToggle(word); },
      {meta: {get: () => c.tmeta >> word & 1, set: on => { c.tmeta = on ? c.tmeta | 1 << word : c.tmeta & ~(1 << word); this.applyToggle(word); }}});
    this.applyToggle = i => {
      this.save(); this.machine.cmd(`set toggle ${i} ${c.toggles[i]}`); this.machine.cmd(`set tmeta ${i} ${c.tmeta >> i & 1}`);
      if (i === word) { wrow.refresh(); wInput.value = oct(c.toggles[i], 12); }
    };
    sel.onchange = () => { word = +sel.value; wrow.refresh(); wInput.value = oct(c.toggles[word], 12); };
    wInput.value = oct(c.toggles[word], 12);
    wInput.onchange = () => { const v = parseOct(wInput.value); if (v === null) return this.toast('Enter at most 12 octal digits'); c.toggles[word] = v; this.applyToggle(word); };
    sw.append(el('fieldset', {}, el('legend', {}, 'Program-readable toggle registers 377720–377737'),
      el('div', {class: 'row'}, el('span', {class: 'label'}, 'Register'), sel, wInput),
      el('div', {class: 'row', style: 'overflow-x:auto'}, wrow),
      el('div', {class: 'hint'}, 'The leftmost red lever is the meta bit. Sketchpad INTERLACE reads bit 4.10 of 377724.')));
    this.toggleRows = {refresh: () => wrow.refresh()};

    const fixedRows = c.fixed.map((v, i) => {
      const inp = el('input', {type: 'text', class: 'octal', value: oct(v, 12)});
      inp.onchange = () => { const x = parseOct(inp.value); if (x === null) return this.toast('Enter an octal value'); c.fixed[i] = x; this.save(); this.machine.cmd(`set fixed ${i} ${x}`); };
      return el('div', {class: 'row'}, el('span', {class: 'label'}, oct(0o377710 + i)), inp,
        act('CODABO', () => `press codabo ${0o377710 + i}`, 'small'));
    });
    sw.append(el('fieldset', {}, el('legend', {}, 'Fixed starting points 377710–377717 · eight CODABO buttons'), fixedRows));
  }
  paintSuppress() { this.alarmTiles.forEach((a, i) => a.tile.classList.toggle('suppressed', !!(this.settings.console.suppress >> i & 1))); }
  // Apply console settings after power-on.
  async apply() {
    const c = this.settings.console;
    await this.machine.cmd(`set tsp ${c.tsp}`);
    await this.machine.cmd(`set suppress ${c.suppress}`);
    await this.machine.cmd(`set hold ${c.hold ? 1 : 0}`);
    for (let i = 0; i < 16; i++) { await this.machine.cmd(`set toggle ${i} ${c.toggles[i]}`); await this.machine.cmd(`set tmeta ${i} ${c.tmeta >> i & 1}`); }
    for (let i = 0; i < 8; i++) await this.machine.cmd(`set fixed ${i} ${c.fixed[i]}`);
  }
  update(s) {
    const vals = {A: s.a, B: s.b, C: s.c, D: s.d, E: s.e, N: s.n, P: oct(s.pc), Q: oct(s.q), K: oct(s.k)};
    for (const [name, r] of Object.entries(this.regs)) {
      const v = vals[name];
      if (v === r.last) continue;
      r.last = v;
      const n = parseInt(v, 8);
      r.val.textContent = String(v).padStart(Math.ceil(r.bits / 3), '0');
      for (let i = 0; i < r.bits; i++) r.row.lamps[i].classList.toggle('on', !!bit36(n, i));
    }
    this.alarmTiles.forEach((a, i) => a.lamp.classList.toggle('on', !!(s.alarms >> i & 1)));
    const conn = BigInt('0o' + s.connected);
    for (const u of this.unitLamps) u.l.classList.toggle('on', !!(conn >> BigInt(u.u) & 1n));
  }
}
