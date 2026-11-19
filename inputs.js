// External register 377621 with a 37-key pushbutton box, knob register 377620, and program templates.
import {el, oct, bitName, bit36, setBit36} from './util.js';

// Program templates label the keys a known program reads and provide shortcuts.
// Sketchpad: Sutherland, TR-296, 1963, Appendix B "Push button controls"; bit q.b -> index 9(q-1)+(b-1).
// TEXT is 3.2 in the listing dispatch, part 1 PDF25: "SKZ 3.2 76BUT / hJPQ MAKETEXT".
// The thesis OCR gives 4.3, which the listing uses for the IBM tape record.
const QB = (q, b) => 9 * (q - 1) + (b - 1);
export const TEMPLATES = {
  sketchpad: {
    name: 'Sketchpad',
    keys: {
      [QB(1, 8)]: 'DRAW', [QB(1, 7)]: 'CIRCLE', [QB(2, 1)]: 'MOVE', [QB(1, 3)]: 'DELETE', [QB(1, 6)]: 'STOP',
      [QB(2, 4)]: 'INST', [QB(3, 6)]: 'COPY20', [QB(3, 1)]: 'COPY21', [QB(2, 5)]: 'COPY22', [QB(1, 9)]: 'COPY23',
      [QB(3, 2)]: 'TEXT', [QB(4, 3)]: 'IBM', [QB(3, 7)]: 'NUMBER', [QB(4, 9)]: 'HOLD', [QB(1, 1)]: 'GARBAGE', [QB(2, 8)]: 'CONSTR',
      [QB(2, 9)]: 'HORV', [QB(2, 2)]: 'DESIG', [QB(2, 6)]: 'TIE', [QB(3, 3)]: 'FIX', [QB(2, 7)]: 'UNFIX',
      [QB(3, 9)]: 'LIBRARY', [QB(2, 3)]: 'CHANGE', [QB(4, 4)]: 'DISMEM', [QB(4, 6)]: 'ORDER', [QB(4, 5)]: 'DISORD',
      [QB(4, 7)]: 'PUNCH', [QB(4, 8)]: 'PLOT', [QB(1, 2)]: 'M:DELCON', [QB(1, 4)]: 'M:DELPTS', [QB(1, 5)]: 'M:DELPIC',
    },
    ink: {x: -128, y: 110},
    // Toggle register 377724: INTERLACE = meta bit 4.10, TWINKLE = bit 4.9. Thesis ch. V; listing SQ60A.
    word: 4,
  },
};

export class Inputs {
  constructor(page, {machine, settings, save, console: con, scope, toast}) {
    Object.assign(this, {machine, settings, save, con, scope, toast});
    this.ext = 0; this.meta = false; this.template = null; this.pending = []; this.taps = [];
    const st = settings.inputs;

    this.templateBox = el('fieldset', {style: 'display:none'});
    page.append(this.templateBox);

    // Pushbutton box
    this.buttons = [];
    const box = el('div', {class: 'pushbox'});
    for (let q = 3; q >= 0; q--) for (let b = 8; b >= 0; b--) {
      const i = q * 9 + b, btn = el('button', {class: 'pb', title: bitName(i)}, bitName(i));
      this.bindButton(btn, on => this.setBit(i, on));
      this.buttons[i] = btn; box.append(btn);
    }
    const metaBtn = el('button', {class: 'key dark small'}, 'META');
    this.bindButton(metaBtn, on => { this.meta = on; metaBtn.classList.toggle('held', on); this.machine.cmd(`set emeta ${on ? 1 : 0}`); });
    const latch = el('input', {type: 'checkbox'}); latch.checked = st.latch;
    latch.onchange = () => { st.latch = latch.checked; this.save(); };
    this.extReadout = el('span', {class: 'readout small'}, '000000000000');
    page.append(el('fieldset', {}, el('legend', {}, 'External register 377621 · pushbutton box'), box,
      el('div', {class: 'row', style: 'margin-top:6px'}, metaBtn, this.extReadout, el('span', {class: 'spacer'}),
        el('label', {class: 'check', title: 'Emulator feature: press to latch, press again to release'}, latch, 'Latch buttons')),
      el('div', {class: 'hint'}, 'Hardware buttons read as 1 while held, per handbook 5-20. Hold the on-screen buttons to operate them. Latch buttons provides an emulator shortcut.')));

    // Knobs
    const knobs = st.knobs.map((v, q) => {
      const dial = el('div', {class: 'dial'}), val = el('span', {class: 'readout small'});
      const paint = () => { dial.style.setProperty('--angle', `${st.knobs[q] / 512 * 360 * 8 % 360}deg`); val.textContent = oct(st.knobs[q], 3); };
      let drag = null;
      dial.addEventListener('pointerdown', e => { dial.setPointerCapture(e.pointerId); drag = {y: e.clientY, v: st.knobs[q]}; });
      dial.addEventListener('pointermove', e => { if (!drag) return; st.knobs[q] = Math.max(0, Math.min(511, Math.round(drag.v + (drag.y - e.clientY) / 2))); paint(); this.sendKnobs(); });
      dial.addEventListener('pointerup', () => { drag = null; this.save(); });
      dial.addEventListener('wheel', e => { e.preventDefault(); st.knobs[q] = Math.max(0, Math.min(511, st.knobs[q] - Math.sign(e.deltaY))); paint(); this.sendKnobs(); this.save(); }, {passive: false});
      paint();
      return el('div', {class: 'knob'}, dial, el('span', {class: 'label'}, `Q${q + 1}`), val);
    }).reverse();
    const kmeta = el('input', {type: 'checkbox'}); kmeta.checked = st.kmeta;
    kmeta.onchange = () => { st.kmeta = kmeta.checked; this.save(); this.machine.cmd(`set kmeta ${st.kmeta ? 1 : 0}`); };
    page.append(el('fieldset', {}, el('legend', {}, 'Knob register 377620 · one knob per quarter'), el('div', {class: 'knobs'}, knobs),
      el('div', {class: 'row'}, el('label', {class: 'check'}, kmeta, 'META button lamp'), el('span', {class: 'hint'}, 'Drag vertically or use the mouse wheel; eight turns span 000–777.'))));
  }
  bindButton(btn, set) {
    btn.addEventListener('pointerdown', e => {
      e.preventDefault(); btn.setPointerCapture(e.pointerId);
      if (this.settings.inputs.latch) { btn.latched = !btn.latched; set(btn.latched); } else set(true);
    });
    const up = () => { if (!this.settings.inputs.latch) set(false); };
    btn.addEventListener('pointerup', up); btn.addEventListener('pointercancel', up);
  }
  setBit(i, on) {
    this.ext = setBit36(this.ext, i, on);
    this.buttons[i].classList.toggle('on', on);
    this.extReadout.textContent = oct(this.ext, 12);
    this.machine.cmd(`set ext ${this.ext}`);
  }
  async apply() {
    const st = this.settings.inputs;
    this.sendKnobs(); await this.machine.cmd(`set kmeta ${st.kmeta ? 1 : 0}`);
    await this.machine.cmd(`set ext ${this.ext}`);
  }
  sendKnobs() {
    const k = this.settings.inputs.knobs;
    this.machine.cmd(`set knob ${k[0] + k[1] * 2 ** 9 + k[2] * 2 ** 18 + k[3] * 2 ** 27}`);
  }
  // Hold a key for a duration in machine clocks for a keyboard shortcut or template action.
  tap(bit, clocks, delay = 0) { this.taps.push({bit, clocks, delay, start: null, up: null}); }
  // Queue an action to happen once the simulated pen has reached the user's aim.
  whenPenArrives(f) { this.pending.push(f); }

  setTemplate(id) {
    const t = TEMPLATES[id] || null;
    this.template = t;
    this.buttons.forEach((b, i) => { b.querySelector('.tag')?.remove(); if (t?.keys[i]) b.append(el('span', {class: 'tag'}, t.keys[i])); });
    this.templateBox.style.display = t ? '' : 'none';
    if (!t) return;
    const c = this.settings.console, w = t.word;
    const interlace = el('input', {type: 'checkbox'}), twinkle = el('input', {type: 'checkbox'});
    const sync = () => { interlace.checked = !!(c.tmeta >> w & 1); twinkle.checked = !!bit36(c.toggles[w], 35); };
    interlace.onchange = () => { c.tmeta = interlace.checked ? c.tmeta | 1 << w : c.tmeta & ~(1 << w); this.con.applyToggle(w); };
    twinkle.onchange = () => { c.toggles[w] = setBit36(c.toggles[w], 35, twinkle.checked); this.con.applyToggle(w); };
    sync();
    this.model = el('span', {class: 'readout small'}, '— / —');
    const key = (name, bit) => el('button', {class: 'key', onclick: () => this.tap(bit, 80000)}, name);
    this.templateBox.replaceChildren(el('legend', {}, `Program template · ${t.name}`),
      el('div', {class: 'row'},
        el('button', {class: 'key red', onclick: () => this.scope.setPen(true, t.ink.x, t.ink.y)}, 'Aim at INK'),
        key('DRAW · D', QB(1, 8)), key('CIRCLE · C', QB(1, 7)), key('STOP · M', QB(1, 6)), key('DELETE', QB(1, 3)),
        el('button', {class: 'key dark', onclick: () => this.scope.setPen(false)}, 'Lift pen · Esc')),
      el('div', {class: 'row'},
        el('label', {class: 'check', title: 'Meta bit 4.10 of 377724'}, interlace, 'INTERLACE · interlaced display'),
        el('label', {class: 'check', title: 'Bit 4.9 of 377724'}, twinkle, 'TWINKLE · random display'),
        el('span', {class: 'spacer'}), el('span', {class: 'label'}, 'Model points/lines'), this.model),
      el('div', {class: 'hint'}, 'With the pen down, clicking the screen presses DRAW when the pen reaches the target. Switch meanings follow Sutherland thesis chapter V and listing SQ60A. Determine the active switch polarity from the display.'));
  }
  // Read Sketchpad model rings for point and line lists from core for the status display.
  async modelCounts() {
    const peek = async (a, n = 1) => this.machine.cmd(`peek ${a} ${n}`);
    const members = async header => {
      const head = header - 0o24000 + 3, seen = new Set();
      let node = (await peek(header + 3))[0] % 2 ** 18;
      while (node !== head && node > 0 && node < 0o154000 && seen.size < 1024 && !seen.has(node)) {
        seen.add(node); node = (await peek(0o24000 + node))[0] % 2 ** 18;
      }
      return seen.size;
    };
    return [await members(0o24275), await members(0o24201)];
  }
  update(s, cursor) {
    // Template key presses, one at a time: wait `delay`, hold `clocks`, then a gap before the next.
    const t = this.taps[0];
    if (t) {
      if (t.start === null) t.start = s.cycles + t.delay;
      if (!t.down && t.up === null && s.cycles >= t.start) { this.setBit(t.bit, true); t.down = true; }
      else if (t.down && s.cycles >= t.start + t.clocks) { this.setBit(t.bit, false); t.down = false; t.up = s.cycles; }
      else if (t.up !== null && s.cycles >= t.up + 40000) this.taps.shift();
    }
    if (this.pending.length && cursor.lag < 1) this.pending.shift()();
    if (this.template && this.model && (!this.lastModel || performance.now() - this.lastModel > 1000)) {
      this.lastModel = performance.now();
      this.modelCounts().then(([p, l]) => { this.model.textContent = `${p} / ${l}`; this.counts = {points: p, lines: l}; });
    }
  }
}
