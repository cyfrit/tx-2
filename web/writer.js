// Lincoln Writer pairs 65/66 and 71/72. H63 table 7-6; LW pp.9-19.
import {el, download} from './util.js';
import {decode, encodeKeyboard, newState, NAMES} from './lw.js';

const SPECIAL_KEYS = [[0o14, 'Read in'], [0o15, 'Begin'], [0o16, 'No'], [0o17, 'Yes'], [0o71, 'Word exam'], [0o76, 'Stop'],
  [0o60, 'Carriage return'], [0o62, 'Backspace'], [0o61, 'Tab'], [0o64, 'Superscript'], [0o65, 'Normal'], [0o66, 'Subscript'], [0o67, 'Red'], [0o63, 'Black'],
  [0o72, 'Line feed down'], [0o73, 'Line feed up'], [0o74, 'Lower-case keyboard'], [0o75, 'Upper-case keyboard'], [0o77, 'Nullify']];

export class Writer {
  constructor(page, {machine, toast, inputUnit = 'lw65', outputUnit = 'lw66'}) {
    Object.assign(this, {machine, toast, inputUnit, outputUnit});
    this.state = newState(); this.text = ''; this.count = 0; this.punched = []; this.x = 0; this.y = 0;
    this.paper = el('div', {class: 'paper', tabindex: 0, title: 'Click the paper to type with the keyboard', style: 'position:relative;min-height:16em'});
    this.sheet = el('div', {style: 'position:relative;min-height:12em'});
    this.caret = el('span', {class: 'caret', 'aria-hidden': 'true'});
    this.sheet.append(this.caret);
    this.paper.append(this.sheet);
    this.position(this.caret);
    this.status = el('span', {class: 'hint'}, 'Lower-case keyboard: capitals and digits · black');
    const input = el('input', {type: 'text', placeholder: `Send to keyboard ${inputUnit.slice(2)}`, style: 'flex:1;min-width:8em'});
    input.onkeydown = e => { if (e.key === 'Enter') { this.type(input.value + '\n'); input.value = ''; } };
    page.append(
      el('h3', {}, `Lincoln Writer · ${inputUnit.slice(2)}/${outputUnit.slice(2)}`),
      el('div', {class: 'paper-wrap'}, el('div', {class: 'platen'}), this.paper),
      el('div', {class: 'row'}, this.status, el('span', {class: 'spacer'}),
        el('button', {class: 'key dark small', onclick: () => download(`${outputUnit}.txt`, this.text, 'text/plain')}, 'Save printout'),
        el('button', {class: 'key dark small', onclick: () => this.clear()}, 'New paper')),
      el('fieldset', {}, el('legend', {}, `Dual keyboard · ${inputUnit.slice(2)}`),
        el('div', {class: 'row'}, input, el('button', {class: 'key', onclick: () => { this.type(input.value + '\n'); input.value = ''; }}, 'Send')),
        el('div', {class: 'lw-keys'}, SPECIAL_KEYS.map(([code, name]) => el('button', {class: 'key dark small', onclick: () => this.keys([code])}, name))),
        el('div', {class: 'hint'}, 'TSD receives automatic case-change prefixes and characters separately. The keyboard is interlocked while the tape reader runs.')));
    this.addReader(page);
    this.paper.addEventListener('keydown', e => {
      if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
      const ch = ({Enter: '\n', Tab: '\t', Backspace: '\b'})[e.key] ?? (e.key.length === 1 ? e.key : null);
      if (ch === null) return;
      e.preventDefault(); this.type(ch);
    });
  }
  async command(unit, op) {
    const r = await this.machine.cmd(`dev ${unit} ${op}`);
    if (r.error) this.toast(r.error);
    return r;
  }
  type(text) { const keys = encodeKeyboard(text); if (keys.length) this.command(this.inputUnit, 'key ' + keys.join(' ')); }
  keys(codes) { this.command(this.inputUnit, 'keys ' + codes.join(' ')); }
  addReader(page) {
    const check = (text, checked, change) => {
      const i = el('input', {type: 'checkbox'}); i.checked = checked;
      i.onchange = change; return {i, label: el('label', {class: 'check'}, i, text)};
    };
    const output = [], source = [];
    const sendRoute = (unit, fields) => this.command(unit, 'route ' + fields.map(v => +v.i.checked).join(' '));
    for (const [label, on] of [['Computer → writer', true], ['Computer → punch', false]]) output.push(check(label, on, () => sendRoute(this.outputUnit, output)));
    for (const [label, on] of [['Keyboard/reader → computer', true], ['Keyboard/reader → writer', false], ['Keyboard/reader → punch', false]]) source.push(check(label, on, () => sendRoute(this.inputUnit, source)));
    this.routeOutput = output; this.routeInput = source;
    const upload = el('input', {type: 'file', accept: '.tape', style: 'display:none'});
    upload.onchange = async () => {
      const f = upload.files[0]; if (!f) return;
      const bytes = new Uint8Array(await f.arrayBuffer());
      await this.command(this.inputUnit, 'tape ' + Array.from(bytes, b => b.toString(16).padStart(2, '0')).join(''));
      upload.value = '';
    };
    const button = (label, unit, cmd) => el('button', {class: 'key dark small', onclick: () => this.command(unit, cmd)}, label);
    const rate = el('select', {}, el('option', {value: 190}, '19 lines/s'), el('option', {value: 95}, '9.5 lines/s · writer connected'));
    rate.onchange = () => this.command(this.inputUnit, 'rate ' + rate.value);
    const filters = ['Stop on stop code', 'Ignore nullify code', 'Stop without seventh hole', 'Ignore blanks'].map(label => check(label, true, () => this.command(this.inputUnit, 'filters ' + filters.map(v => +v.i.checked).join(' '))));
    const noTape = check('No-tape contact', false, () => {});
    const single = check('Hold stop · single line', false, () => this.command(this.inputUnit, 'holdstop ' + +single.i.checked));
    this.readerStatus = el('span', {class: 'hint'}); this.punchCount = el('span', {class: 'hint'}, '0 lines');
    page.append(el('fieldset', {}, el('legend', {}, 'Manual routing · Soroban reader · local punch'),
      el('div', {class: 'row'}, output.map(v => v.label)), el('div', {class: 'row'}, source.map(v => v.label)),
      el('div', {class: 'row'}, upload, el('button', {class: 'key dark small', onclick: () => upload.click()}, 'Load .tape'),
        button('Start reader', this.inputUnit, 'start'), button('Stop reader', this.inputUnit, 'stop'), single.label, rate, this.readerStatus),
      el('div', {class: 'row'}, filters.map(v => v.label)),
      el('div', {class: 'row'}, noTape.label, el('button', {class: 'key dark small', onclick: () => this.command(this.inputUnit, 'rewind ' + +noTape.i.checked)}, 'Rewind')),
      el('div', {class: 'row'}, el('button', {class: 'key dark small',
        onpointerdown: e => { e.currentTarget.setPointerCapture(e.pointerId); this.command(this.outputUnit, 'feed 1'); },
        onpointerup: () => this.command(this.outputUnit, 'feed 0'),
        onpointercancel: () => this.command(this.outputUnit, 'feed 0')}, 'Feed blank tape · hold'),
        button('End mark', this.outputUnit, 'endmark'), this.punchCount,
        el('button', {class: 'key dark small', onclick: () => download(`${this.outputUnit}.tape`, Uint8Array.from(this.punched))}, 'Save punched tape')),
      el('div', {class: 'hint'}, 'Disabling a green filter switch selects red pass-through mode. Red mode for lines without a seventh hole copies only to the punch. End mark uses the later PETR code 73; the 1959 Writer report specifies 72.')));
  }
  position(mark) {
    mark.style.left = `${this.x}ch`;
    mark.style.top = `${2 + this.y * 0.6}em`;
  }
  clear() {
    this.sheet.replaceChildren(this.caret);
    this.text = '';
    this.x = this.y = 0;
    this.updateCarriage();
    this.paper.scrollTop = this.paper.scrollLeft = 0;
  }
  updateCarriage() {
    this.position(this.caret);
    this.sheet.style.minHeight = `${Math.max(12, 4 + this.y * 0.6)}em`;
    if (!this.paper.clientHeight) return;
    const paper = this.paper.getBoundingClientRect();
    const caret = this.caret.getBoundingClientRect();
    if (caret.top < paper.top) this.paper.scrollTop += caret.top - paper.top;
    else if (caret.bottom > paper.bottom) this.paper.scrollTop += caret.bottom - paper.bottom;
    if (caret.left < paper.left) this.paper.scrollLeft += caret.left - paper.left;
    else if (caret.right > paper.right) this.paper.scrollLeft += caret.right - paper.right;
  }
  update(s) {
    const event = s.dev?.[this.outputUnit];
    const codes = event?.codes ?? (this.outputUnit === 'lw66' ? s.writer : []) ?? [];
    if (event?.punch) this.punched.push(...event.punch);
    this.punchCount.textContent = `${this.punched.length} lines`;
    const inState = s.units?.[this.inputUnit], outState = s.units?.[this.outputUnit];
    if (inState) {
      this.readerStatus.textContent = `${inState.reader ? 'Running' : 'Stopped'} · ${inState.position}/${inState.size} · keyboard ${inState.locked ? 'locked' : 'unlocked'}`;
      [inState.computer, inState.writer, inState.punch].forEach((v, i) => { this.routeInput[i].i.checked = !!v; });
    }
    if (outState) [outState.writer, outState.punch].forEach((v, i) => { this.routeOutput[i].i.checked = !!v; });
    for (const code of codes) {
      const r = decode(code, this.state); if (!r) continue;
      if (r.newline) { this.x = 0; this.y += 2 + r.scriptMove; this.text += '\n'; continue; }
      // [INFERENCE] UI tab stops are eight cells apart; hardware stops are adjustable.
      if (r.tab) { this.x = (Math.floor(this.x / 8) + 1) * 8; this.text += '\t'; continue; }
      if (r.backspace) { this.x = Math.max(0, this.x - 1); continue; }
      if (r.lineFeed !== undefined) { this.y += r.lineFeed; continue; }
      if (r.scriptMove !== undefined) { this.y += r.scriptMove; continue; }
      // Explicit carriage coordinates preserve backspaces, dead characters and
      // overstrikes. Font metrics are a display approximation of the typeface.
      const ch = r.combining ? ({'\u0332': '_', '\u0305': '‾', '\u20DD': '○', '\u20DE': '□'})[r.ch] : r.ch;
      const mark = el('span', {class: r.red ? 'red' : '', style: 'position:absolute;white-space:pre'}, ch);
      this.position(mark);
      this.sheet.insertBefore(mark, this.caret);
      this.text += r.ch;
      if (!r.combining) this.x++;
    }
    if (outState) { this.state.upper = !!outState.upper; this.state.red = !!outState.red; this.state.script = ['super', 'normal', 'sub'][outState.script + 1]; }
    if (codes.length) this.updateCarriage();
    const st = this.state;
    this.status.textContent = `${st.upper ? 'Upper-case keyboard: symbols and lowercase' : 'Lower-case keyboard: capitals and digits'} · ${st.red ? 'red' : 'black'} · ${st.script === 'normal' ? 'normal' : st.script === 'super' ? 'superscript' : 'subscript'}`;
  }
}
export {NAMES};
