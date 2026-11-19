// H63 pp.97,116,122-123: external pulse inputs, relay register, RNG controls.
import {el, oct} from './util.js';
import {toggleRow} from './console.js';

export class MiscPanel {
  constructor(page, {machine}) {
    this.machine = machine; this.enabled = 0o777; this.reset = 0;
    const cmd = (unit, op) => machine.cmd(`dev ${unit} ${op}`);
    const button = (text, unit, op) => el('button', {class: 'key dark small', onclick: () => cmd(unit, op)}, text);
    this.enables = toggleRow(9, () => this.enabled, value => { this.enabled = value; this.enables.refresh(); cmd('misc47', 'enable ' + value); });
    this.inputs = Array.from({length: 9}, (_, i) => {
      const lamp = el('span', {class: 'lamp small green'});
      return {lamp, node: el('button', {class: 'key dark small', onclick: () => cmd('misc47', 'pulse ' + (1 << i))}, lamp, `Pulse ${i + 1}`)};
    });
    this.relays = Array.from({length: 9}, (_, i) => el('span', {}, el('span', {class: 'lamp small green'}), ` ${i + 1} `));
    this.mom = el('span', {class: 'hint'});
    this.resetRow = toggleRow(9, () => this.reset, value => { this.reset = value; this.resetRow.refresh(); cmd('misc75', 'resetreg ' + value); });
    const shift = el('select', {}, el('option', {value: 3}, 'No shift'), el('option', {value: 1}, 'Rotate left'), el('option', {value: 2}, 'Open-end shift left'));
    shift.onchange = () => cmd('misc75', 'shiftmode ' + shift.value);
    this.rng = el('span', {class: 'readout small'});
    page.append(el('fieldset', {}, el('legend', {}, 'Miscellaneous input · 47'),
      el('div', {class: 'hint'}, 'Nine manually enabled channels. Input pulses set latch bits, cleared after TSD. Buttons generate standard TX-2 pulses.'), this.enables,
      el('div', {class: 'row'}, this.inputs.map(v => v.node))),
    el('fieldset', {}, el('legend', {}, 'Miscellaneous output · 75'), el('div', {class: 'row'}, this.relays, this.mom),
      el('div', {class: 'row'}, shift, button('External shift pulse', 'misc75', 'shift')),
      el('div', {class: 'hint'}, 'Manual reset register, loaded by TEST. Contacts have a 2 ms delay; MOM-9 changes immediately.'), this.resetRow,
      button('TEST', 'misc75', 'test')),
    el('fieldset', {}, el('legend', {}, 'Random number generator · 61'), el('div', {class: 'row'}, this.rng,
      button('Power on · 60-second warmup', 'rng', 'power 1'), button('Power off', 'rng', 'power 0')),
      el('div', {class: 'hint'}, 'Nine-bit buffer; IOS/TSD starts the next generation. [INFERENCE] Simulation uses a reproducible pseudorandom source and a fixed 57.6 μs generation time.')));
  }
  update(s) {
    const input = s.units?.misc47, output = s.units?.misc75, rng = s.units?.rng;
    if (input) { this.enabled = input.enabled; this.enables.refresh(); this.inputs.forEach((v, i) => v.lamp.classList.toggle('on', !!(input.latch & (1 << i)))); }
    if (output) {
      this.relays.forEach((v, i) => v.firstChild.classList.toggle('on', !!(output.relays & (1 << i))));
      this.mom.textContent = `Register ${oct(output.register, 3)} · MOM-9 ${output.mom9 ? '−3 V' : 'Ground'}`;
    }
    if (rng) this.rng.textContent = `${rng.power ? (s.cycles < rng.warmUntil ? 'Warming up' : rng.ready ? 'Buffer ready' : 'Waiting for generation') : 'Off'} · ${oct(rng.value, 3)}`;
  }
}
