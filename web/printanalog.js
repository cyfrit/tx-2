// H63 pp99–103,196: operator signal source and positioned Xerox paper.
import {el, oct} from './util.js';

export class PrintAnalogPanel {
  constructor(page, {machine}) {
    this.machine = machine;
    this.marks = 0;
    this.lastCycles = 0;
    this.paper = el('div', {style: 'position:relative;width:760px;min-height:240px;background:#fffdf2;color:#151511;overflow:hidden'});
    this.paperScroll = el('div', {style: 'overflow:auto;max-height:440px;border:1px solid #777'}, this.paper);
    this.xeroxState = el('div', {class: 'readout small'}, 'Disconnected');
    const printerPower = el('input', {type: 'checkbox', checked: true});
    printerPower.onchange = () => machine.cmd(`dev xerox power ${+printerPower.checked}`);
    const lowPaper = el('input', {type: 'checkbox'});
    lowPaper.onchange = () => machine.cmd(`dev xerox paper ${+lowPaper.checked}`);
    page.append(el('fieldset', {}, el('legend', {}, 'Xerox electrostatic printer · 51'),
      el('div', {class: 'row'}, el('label', {}, printerPower, ' Power'), el('label', {}, lowPaper, ' Low paper · EIA'),
        el('button', {class: 'key dark', onclick: () => this.clearPaper()}, 'Remove paper · clear view')),
      this.xeroxState, this.paperScroll,
      el('div', {class: 'hint'}, 'Each character specifies X, Y and size independently. Warmup: 5 s; exposure: 45 ms; reset: 2 ms; character time: 750 μs. Dashed outlines mark uncertain glyphs during initial paper startup.'),
      el('div', {class: 'hint'}, 'The display uses Unicode glyphs. [INFERENCE] Large characters are displayed at twice the small-character size; the handbook gives no exact size ratio for the two fonts.')));

    this.analogState = el('div', {class: 'readout small'});
    this.power = el('input', {type: 'checkbox'});
    this.power.onchange = () => machine.cmd(`dev datrac power ${+this.power.checked}`);
    this.programmed = el('input', {type: 'checkbox', checked: true});
    this.programmed.onchange = () => machine.cmd(`dev datrac route programmed ${+this.programmed.checked}`);
    this.timer = el('input', {type: 'checkbox'});
    this.timer.onchange = () => machine.cmd(`dev datrac route timer ${+this.timer.checked}`);
    this.shape = el('select', {}, ...[['dc', 'DC knob'], ['sine', 'Sine wave'], ['square', 'Square wave'], ['triangle', 'Triangle wave']].map(([value, name]) => el('option', {value}, name)));
    this.range = el('select', {}, ...[1, 10, 100].map(v => el('option', {value: v}, `±${v} V`)));
    this.level = el('input', {type: 'range', min: -1, max: 1, step: .001, value: 0});
    this.levelText = el('span', {class: 'readout small'}, '0 V');
    this.hz = el('input', {type: 'number', min: 0, step: 1, value: 100, style: 'width:100px'});
    this.offset = el('input', {type: 'number', step: .001, value: 0, style: 'width:100px'});
    const source = () => {
      this.levelText.textContent = `${Number(this.level.value).toFixed(3)} V`;
      machine.cmd(`dev datrac source ${this.shape.value} ${this.level.value} ${this.hz.value} ${this.offset.value}`);
      this.drawSignal();
    };
    for (const input of [this.shape, this.hz, this.offset]) input.onchange = source;
    this.level.oninput = source;
    this.range.onchange = async () => {
      const r = Number(this.range.value);
      this.level.min = -r; this.level.max = r; this.level.step = r / 1000;
      await machine.cmd(`dev datrac range ${r}`); source();
    };
    const oscillator = el('input', {type: 'number', min: 0, max: 1000000, value: 0, style: 'width:110px'});
    oscillator.onchange = () => machine.cmd(`dev datrac oscillator ${oscillator.value}`);
    this.signalCanvas = el('canvas', {width: 720, height: 130, style: 'width:100%;height:130px;background:#0c1612'});
    this.samples = el('div', {class: 'mono-out'}, 'No samples');
    page.append(el('fieldset', {}, el('legend', {}, 'DATRAC analog-to-digital converter · 50'),
      el('div', {class: 'row'}, el('label', {}, this.power, ' Power'), el('label', {}, this.programmed, ' IOS/TSD trigger route'), el('label', {}, this.timer, ' Interval timer 54 trigger route')),
      el('div', {class: 'row'}, el('span', {}, 'Signal source'), this.shape, el('span', {}, 'Range'), this.range,
        el('span', {}, 'Amplitude/DC level'), this.level, this.levelText),
      el('div', {class: 'row'}, el('span', {}, 'Frequency Hz'), this.hz, el('span', {}, 'Offset V'), this.offset,
        el('span', {}, 'External trigger oscillator Hz · 0 disconnects'), oscillator),
      el('div', {class: 'row'}, ...[1, 2, 3, 4].map(i => el('button', {class: 'key dark', onclick: () => machine.cmd(`dev datrac trigger ${i}`)}, `Trigger input ${i}`))),
      this.signalCanvas, this.analogState, this.samples,
      el('div', {class: 'hint'}, 'One analog channel; 1–4 are trigger inputs. Conversion takes 22 μs; triggers must be at least 37 μs apart. Output is an 18-bit ones-complement fraction without sign extension. Recommended warmup: 5–30 minutes.'),
      el('div', {class: 'hint'}, 'Simulation uses ideal quantization; hardware guarantees only the highest 8–11 bits. [INFERENCE] Triggers arriving too quickly are counted and rejected; the handbook warns of possible circuit damage.')));
    this.drawSignal();
  }
  clearPaper() { this.paper.replaceChildren(); this.paper.style.height = '240px'; this.paperBase = null; this.marks = 0; }
  drawSignal() {
    const g = this.signalCanvas.getContext('2d'), w = this.signalCanvas.width, h = this.signalCanvas.height;
    const range = Number(this.range.value), level = Number(this.level.value), offset = Number(this.offset.value);
    g.fillStyle = '#0c1612'; g.fillRect(0, 0, w, h);
    g.strokeStyle = '#365044'; g.beginPath(); g.moveTo(0, h / 2); g.lineTo(w, h / 2); g.stroke();
    g.strokeStyle = '#9cdd9d'; g.beginPath();
    for (let x = 0; x <= w; x++) {
      const p = (x / w * 2) % 1;
      const shape = this.shape.value;
      const v = offset + level * (shape === 'dc' ? 1 : shape === 'sine' ? Math.sin(p * Math.PI * 2) : shape === 'square' ? (p < .5 ? 1 : -1) : 1 - 4 * Math.abs(p - .5));
      const y = h / 2 - Math.max(-1.1, Math.min(1.1, v / range)) * h * .42;
      x ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.stroke();
  }
  update(s) {
    if (s.cycles < this.lastCycles) this.clearPaper();
    this.lastCycles = s.cycles;
    for (const m of s.dev?.xerox || []) {
      this.paperBase ??= m.paper;
      this.marks++;
      if (!m.glyph) continue;
      const y = (m.paper - this.paperBase + .625 - m.y * .02) * 144;
      const mark = el('span', {
        title: `X ${m.x} · Y ${m.y} · code ${oct(m.code, 3)} · frame ${m.frame}${m.uncertain ? ' · startup noise: uncertain glyph' : ''}`,
        style: `position:absolute;left:${16 + m.x * 1.44}px;top:${y}px;transform:translateY(-50%);font:${m.large ? 27 : 13.5}px "Times New Roman",serif;white-space:pre;${m.uncertain ? 'outline:1px dashed #c88632;' : ''}`,
      }, m.glyph);
      this.paper.append(mark);
      this.paper.style.height = `${Math.max(240, parseFloat(this.paper.style.height) || 0, y + 70)}px`;
    }
    const x = s.units?.xerox;
    if (x) this.xeroxState.textContent = `${x.power ? 'Power on' : 'Power off'} · ${x.warming ? 'Warming up' : x.ready ? 'Ready' : x.connected ? 'Busy' : 'Disconnected'} · ${x.moving ? 'Paper moving' : 'Paper stopped'} · ${x.characters} characters${x.lowPaper ? ' · Low paper EIA' : ''}`;
    const d = s.units?.datrac;
    if (d) {
      this.power.checked = !!d.power; this.programmed.checked = !!d.programmed; this.timer.checked = !!d.timer;
      this.analogState.textContent = `${d.power ? 'Power on' : 'Power off'} · ${d.converting ? 'Converting' : d.ready ? 'Sample ready' : 'Waiting for trigger'} · ${d.volts.toFixed(4)} V · ${d.samples} samples · warmup ${d.warmupSeconds} s${d.stable ? ' · stable' : ''}${d.missed ? ' · MISAL' : ''} · too-fast triggers ${d.tooFast}`;
    }
    if (s.dev?.datrac?.length) this.samples.textContent = s.dev.datrac.slice(-8).map(v => `Clock ${v.clock} · ${v.volts.toFixed(6)} V → ${oct(v.word, 6)}`).join('\n');
  }
}
