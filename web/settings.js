// Emulator settings: display appearance, light-pen assistance, and device timing.
import {el, DEFAULTS} from './util.js';

const PHOSPHOR_NAMES = {P7: 'P7 blue-white flash + yellow-green persistence', P31: 'P31 green', P4: 'P4 white', amber: 'Amber', P11: 'P11 blue'};

export class Settings {
  constructor(page, {machine, settings, save, scope}) {
    Object.assign(this, {machine, settings, save, scope});
    const s = settings;
    const range = (obj, key, min, max, step, fmt, apply) => {
      const out = el('span', {class: 'readout small'});
      const r = el('input', {type: 'range', min, max, step, value: obj[key]});
      const show = () => { out.textContent = fmt(obj[key]); };
      r.oninput = () => { obj[key] = +r.value; show(); apply?.(); this.save(); };
      show();
      return el('div', {}, el('div', {class: 'row'}, el('span', {class: 'label'}, ''), out), r);
    };
    const field = (label, control) => el('label', {style: 'display:flex;flex-direction:column;gap:3px'}, el('span', {class: 'label'}, label), control);
    const check = (obj, key, label, apply, title = '') => {
      const c = el('input', {type: 'checkbox'}); c.checked = obj[key];
      c.onchange = () => { obj[key] = c.checked; apply?.(); this.save(); };
      return el('label', {class: 'check', title}, c, label);
    };
    const phosphor = el('select', {}, Object.entries(PHOSPHOR_NAMES).map(([k, v]) => el('option', {value: k, selected: s.crt.phosphor === k}, v)));
    phosphor.onchange = () => { s.crt.phosphor = phosphor.value; this.save(); };
    // Scopes 56 and 60; light-pen unit 55 works with scope 60. Users Handbook.
    s.crt.scope ??= 'both';
    const scopeSel = el('select', {}, [['both', 'Overlay 56 and 60'], ['60', '60 only · light pen'], ['56', '56 only']].map(([k, v]) => el('option', {value: k, selected: s.crt.scope === k}, v)));
    scopeSel.onchange = () => { s.crt.scope = scopeSel.value; this.save(); };
    const effects = () => document.getElementById('crt').classList.toggle('effects', s.crt.effects);
    effects();
    page.append(el('fieldset', {}, el('legend', {}, 'Display'), el('div', {class: 'grid2'},
      field('Phosphor', phosphor),
      field('Scope', scopeSel),
      field('Persistence · handbook: about 2 seconds', range(s.crt, 'persistence', 0.05, 4, 0.05, v => `${v.toFixed(2)} s`)),
      field('Glow', range(s.crt, 'glow', 0, 1, 0.05, v => v.toFixed(2))),
      field('Brightness', range(s.crt, 'brightness', 0.3, 2, 0.05, v => v.toFixed(2))),
      field('Spot size', range(s.crt, 'dot', 1, 5, 0.5, v => `${v} px`)),
      field('Display zoom', range(s.crt, 'zoom', 1, 2.5, 0.1, v => `${v.toFixed(1)}×`)),
      check(s.crt, 'effects', 'Scan lines and vignette', effects),
      check(s.crt, 'penMarker', 'Show light-pen marker'))));

    const penLimit = () => this.machine.config({penLimit: s.pen.limit ? s.pen.speed : 0});
    page.append(el('fieldset', {}, el('legend', {}, 'Light pen'), el('div', {class: 'grid2'},
      check(s.pen, 'limit', 'Limit pen speed to maintain tracking', penLimit, 'The original tracking cross has a finite tracking speed; observed line drawing occasionally loses tracking at about 3–4 units per 10,000 clocks'),
      field('Speed limit · units per 10,000 clocks', range(s.pen, 'speed', 0.5, 12, 0.5, v => `${v}`, penLimit)),
      field('Detection radius · display units', range(s.pen, 'radius', 2, 40, 1, v => `${v}`, () => this.machine.cmd(`set radius ${s.pen.radius}`))))));

    const mech = () => this.applyTiming();
    const profile = el('select', {},
      el('option', {value: 'interactive', selected: s.timing.profile === 'interactive'}, 'Interactive: 2 clocks = 1 μs'),
      el('option', {value: 'reference', selected: s.timing.profile === 'reference'}, 'Reference: 50 clocks = 1 μs; device timing closer to CPU timing'));
    profile.onchange = () => { s.timing.profile = profile.value; this.save(); mech(); };
    page.append(el('fieldset', {}, el('legend', {}, 'Timing and mechanical speeds'), el('div', {class: 'grid2'},
      field('Device timebase', profile),
      check(s.timing, 'writer', 'Realistic typewriter speed · about 10 characters/s', mech),
      check(s.timing, 'punch', 'Punch: 180 lines/s per handbook', mech),
      check(s.timing, 'reader', 'Realistic reader speed · 2000 lines/s for reels; fast loading uses 64 μs/line', mech),
      field('Simulation batch duration', range(s.timing, 'batchMs', 4, 40, 1, v => `${v} ms`, () => this.machine.config({batchMs: s.timing.batchMs}))))));

    this.stats = el('div', {class: 'mono-out', style: 'white-space:pre-wrap'});
    page.append(el('fieldset', {}, el('legend', {}, 'Simulation statistics'), this.stats));
    page.append(el('div', {class: 'row'}, el('button', {class: 'key dark small', onclick: () => {
      localStorage.removeItem('tx2-settings-v1'); Object.assign(this.settings, structuredClone(DEFAULTS)); location.reload();
    }}, 'Restore default settings')));
  }
  updateStats(text) { if (this.stats.offsetParent) this.stats.textContent = text; }
  applyTiming() {
    const t = this.settings.timing;
    this.machine.cmd(`set timing ${t.profile === 'reference' ? 50 : 2}`);
    for (const unit of ['lw66', 'lw72']) this.machine.cmd(`dev ${unit} us ${t.writer ? 100000 : 0}`);
    this.machine.cmd(`dev punch us ${t.punch ? 5556 : 0}`);
    this.machine.cmd(`set reader_us ${t.reader ? 0 : 64}`);
  }
  async apply() {
    const s = this.settings;
    this.applyTiming();
    this.machine.config({penLimit: s.pen.limit ? s.pen.speed : 0, batchMs: s.timing.batchMs});
    await this.machine.cmd(`set radius ${s.pen.radius}`);
  }
}
