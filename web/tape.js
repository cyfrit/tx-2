// Paper tape: library, PETR reader unit 52, punch output unit 63, and tape tools.
import {el, oct, parseOct, download} from './util.js';
import * as T from './tapefmt.js';
import {PlotterPanel} from './plotter.js';

// Draw tape lines as a horizontal strip: 7 channels + feed holes; the read head marks `head`.
function drawStrip(canvas, tape, head, {follow = true} = {}) {
  const w = canvas.clientWidth || 300, h = canvas.clientHeight || 74, dpr = devicePixelRatio || 1;
  if (canvas.width !== Math.round(w * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
  const g = canvas.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = '#0c0f0d'; g.fillRect(0, 0, w, h);
  const pitch = 9, cols = Math.floor(w / pitch), top = 6, rowH = (h - 12) / 8;
  const first = follow ? Math.max(0, Math.min(head - Math.floor(cols / 3), tape.length - cols)) : 0;
  g.fillStyle = '#e8ddbd'; g.fillRect(0, top - 3, Math.min(cols, tape.length - first) * pitch, h - 2 * top + 6);
  // Punched channel order across the tape: 7th, 6..4, feed, 3..1.
  const rows = [6, 5, 4, 3, 'feed', 2, 1, 0];
  for (let c = 0; c < cols && first + c < tape.length; c++) {
    const b = tape[first + c], x = c * pitch + pitch / 2;
    rows.forEach((bit, r) => {
      const y = top + r * rowH + rowH / 2;
      const hole = bit === 'feed' ? b & 0x80 : b >> bit & 1;
      if (!hole) return;
      g.fillStyle = '#141814'; g.beginPath(); g.arc(x, y, bit === 'feed' ? 1.6 : 3, 0, 7); g.fill();
    });
  }
  if (head >= first && head < first + cols) {
    const x = (head - first) * pitch;
    g.strokeStyle = '#ff9d1a'; g.lineWidth = 2; g.strokeRect(x, 1, pitch, h - 2);
  }
}

export class TapePanel {
  constructor(page, {machine, toast, onLibraryLoad}) {
    Object.assign(this, {machine, toast, onLibraryLoad});
    this.mounted = new Uint8Array(0); this.mountedName = 'None';
    this.punched = []; this.library = []; this.reference = null;
    const sub = el('div', {class: 'subtabs'});
    const pages = {Reader: el('div', {class: 'sub-page active'}), Punch: el('div', {class: 'sub-page'}), Plotter: el('div', {class: 'sub-page'}), Tools: el('div', {class: 'sub-page'})};
    for (const [name, p] of Object.entries(pages)) {
      const b = el('button', {class: p.classList.contains('active') ? 'active' : ''}, name);
      b.onclick = () => { for (const x of sub.children) x.classList.remove('active'); b.classList.add('active'); for (const q of Object.values(pages)) q.classList.toggle('active', q === p); this.redraw(); };
      sub.append(b);
    }
    page.append(sub, ...Object.values(pages));

    // Reader
    this.readerName = el('span', {class: 'readout small'}, this.mountedName);
    this.readerPos = el('span', {class: 'hint'});
    this.readerBar = el('div', {});
    this.readerStrip = el('canvas', {class: 'strip'});
    const upload = el('input', {type: 'file', accept: '.tape,.hex,application/octet-stream', style: 'display:none'});
    upload.onchange = async () => {
      const f = upload.files[0]; if (!f) return;
      let bytes = new Uint8Array(await f.arrayBuffer());
      if (f.name.endsWith('.hex')) bytes = Uint8Array.from(new TextDecoder().decode(bytes).split(/\s+/).filter(Boolean).map(v => T.FEED | parseInt(v, 16) & 0x3f));
      await this.mount(bytes, f.name); upload.value = '';
    };
    this.libraryBox = el('div', {class: 'library'});
    pages.Reader.append(
      el('fieldset', {}, el('legend', {}, 'Photoelectric tape reader PETR · 52'),
        el('div', {class: 'row'}, el('span', {class: 'label'}, 'Mounted tape'), this.readerName, this.readerPos),
        el('div', {class: 'progress'}, this.readerBar), this.readerStrip,
        el('div', {class: 'row'},
          el('button', {class: 'key dark', onclick: () => upload.click()}, 'Upload .tape'), upload,
          el('button', {class: 'key dark', onclick: () => this.machine.cmd('tape rewind')}, 'Rewind'),
          el('button', {class: 'key dark', onclick: () => { this.machine.cmd('tape eject'); this.mounted = new Uint8Array(0); this.mountedName = 'None'; this.readerName.textContent = this.mountedName; }}, 'Eject'),
          el('button', {class: 'key dark', onclick: () => this.mounted.length && download(this.mountedName.replace(/(\.tape)?$/, '.tape'), this.mounted)}, 'Download'))),
      el('fieldset', {}, el('legend', {}, 'Tape library'), this.libraryBox,
        el('div', {class: 'hint'}, 'Load and start mounts the tape, sets TSP to plugboard 377750 and presses CODABO, following the hardware boot procedure.')));

    // Punch
    this.punchCount = el('span', {class: 'readout small'}, '0 lines');
    this.punchStrip = el('canvas', {class: 'strip'});
    pages.Punch.append(el('fieldset', {}, el('legend', {}, 'High-speed paper tape punch · 63'),
      el('div', {class: 'row'}, el('span', {class: 'label'}, 'Punched'), this.punchCount),
      this.punchStrip,
      el('div', {class: 'row'},
        el('button', {class: 'key dark', onclick: () => this.punched.length && download('punch.tape', Uint8Array.from(this.punched))}, 'Download .tape'),
        el('button', {class: 'key dark', onclick: () => this.punched.length && this.mount(Uint8Array.from(this.punched), 'punch.tape')}, 'Mount in reader'),
        el('button', {class: 'key dark', onclick: () => { this.punched = []; this.punchCount.textContent = '0 lines'; this.redraw(); }}, 'Tear off and clear')),
      el('div', {class: 'hint'}, 'IOS₆₃ 30000/30004 selects normal mode without/with the seventh hole; 30002/30006 selects assembly mode, with six TSD transfers per 36-bit word.')));
    this.punchStatus = el('div', {class: 'hint'});
    const punchControls = el('div', {class: 'row'});
    for (const [op, label] of [['low', 'Low tape'], ['supply', 'Supply fault'], ['end', 'End of tape'], ['maintenance', 'Maintenance'], ['ack', 'Silence ACK'], ['brake', 'Reel-arm brake']]) {
      const input = el('input', {type: 'checkbox'});
      input.onchange = () => machine.cmd(`dev punch ${op} ${input.checked ? 1 : 0}`);
      punchControls.append(el('label', {}, input, label));
    }
    const feed = el('button', {class: 'key dark'}, 'Feed · hold 5 seconds');
    feed.onpointerdown = e => { feed.setPointerCapture(e.pointerId); machine.cmd('dev punch feed 1'); };
    feed.onpointerup = feed.onpointercancel = () => machine.cmd('dev punch feed 0');
    punchControls.append(feed, el('button', {class: 'key dark', onclick: () => machine.cmd('dev punch reset')}, 'Reset alarms'),
      el('button', {class: 'key dark', onclick: async () => { const r=await machine.cmd('dev punch lubricate'); if(r.error) toast('The lubrication timer can only be reset in maintenance mode.'); }}, 'Maintenance: reset lubrication timer'));
    const profile = el('select', {}, el('option', {value: 'handbook'}, '1963 handbook · 180 lines/s · 5-second feed delay'),
      el('option', {value: 'technical'}, '1961 technical manual · 180 lines/s · 1-second feed delay'), el('option', {value: 'sketchpad'}, 'Sketchpad thesis · 300 lines/s'));
    profile.onchange = () => { machine.cmd(`dev punch profile ${profile.value}`); feed.textContent = profile.value === 'technical' ? 'Feed · hold 1 second' : 'Feed · hold 5 seconds'; };
    punchControls.append(profile,
      el('button', {class: 'key dark', onclick: async () => { const r=await machine.cmd('dev punch motor 0'); if(r.error) toast('The motor switch requires maintenance mode.'); }}, 'Maintenance: stop motor'),
      el('button', {class: 'key dark', onclick: async () => { const r=await machine.cmd('dev punch motor 1'); if(r.error) toast('The motor switch requires maintenance mode.'); }}, 'Maintenance: start motor'));
    pages.Punch.append(punchControls, this.punchStatus,
      el('div', {class: 'hint'}, 'Handbook profile: 180 lines/s, approximately 1-second motor startup and 5-second stop delay. The program punches blank leader and END MARK.'));
    this.plotter = new PlotterPanel(pages.Plotter, {machine, toast, punched: () => this.punched});

    // Tools
    this.toolOut = el('div', {class: 'mono-out'}, 'Select a tape and an operation.');
    this.toolResult = null;
    const source = el('select', {}, el('option', {value: 'mounted'}, 'Mounted tape'), el('option', {value: 'punched'}, 'Punch output'), el('option', {value: 'file'}, 'Upload file…'));
    const toolFile = el('input', {type: 'file', style: 'display:none'});
    let fileBytes = null;
    source.onchange = () => { if (source.value === 'file') toolFile.click(); };
    toolFile.onchange = async () => { fileBytes = toolFile.files[0] ? new Uint8Array(await toolFile.files[0].arrayBuffer()) : null; };
    const pick = () => source.value === 'punched' ? Uint8Array.from(this.punched) : source.value === 'file' ? fileBytes : this.mounted;
    const resultRow = el('div', {class: 'row'},
      el('button', {class: 'key dark', onclick: () => this.toolResult && download(this.toolResult.name, this.toolResult.bytes)}, 'Download result'),
      el('button', {class: 'key dark', onclick: () => this.toolResult && this.mount(this.toolResult.bytes, this.toolResult.name)}, 'Mount result in reader'));
    const text = el('textarea', {placeholder: 'HELLO, WORLD'});
    const addr = el('input', {type: 'text', class: 'octal', value: '1000'}), body = el('textarea', {placeholder: 'One octal word per line, for example\n040011000005'});
    pages.Tools.append(
      el('fieldset', {}, el('legend', {}, 'Analysis and repair'),
        el('div', {class: 'row'}, el('span', {class: 'label'}, 'Source'), source, toolFile),
        el('div', {class: 'row'},
          el('button', {class: 'key', onclick: () => this.info(pick())}, 'Blocks and checksums'),
          el('button', {class: 'key', onclick: () => this.dump(pick())}, 'Line dump'),
          el('button', {class: 'key', onclick: () => this.words(pick())}, 'Assemble 36-bit words'),
          el('button', {class: 'key', onclick: () => this.fix(pick())}, 'Repair upstream tape')),
        this.toolOut, resultRow),
      el('fieldset', {}, el('legend', {}, 'Text → Lincoln Writer tape'), text,
        el('div', {class: 'row'}, el('button', {class: 'key', onclick: () => this.setResult(T.textTape(text.value), 'text.tape', `Encoded ${text.value.length} characters in offline LW punch format, with a seventh hole on every line.`)}, 'Generate tape'))),
      el('fieldset', {}, el('legend', {}, 'Machine words → loadable tape · standard leader and checksum blocks'),
        el('div', {class: 'row'}, el('span', {class: 'label'}, 'Start address'), addr),
        body, el('div', {class: 'row'}, el('button', {class: 'key', onclick: () => this.program(addr.value, body.value)}, 'Generate tape'))));
    addEventListener('resize', () => this.redraw());
  }
  async loadLibrary() {
    this.library = await (await fetch('tapes/index.json')).json();
    this.libraryBox.replaceChildren(...this.library.map(t => el('div', {class: 'tape-card'},
      el('div', {class: 'kind'}, `${t.kind} · ${t.lines.toLocaleString()} lines`), el('h4', {}, t.title), el('p', {}, t.note),
      t.reference && el('p', {}, el('a', {href: t.reference}, 'Original program listing')),
      el('div', {class: 'row'},
        el('button', {class: 'key small', onclick: () => this.loadEntry(t, false)}, 'Load'),
        el('button', {class: 'key small', onclick: () => this.loadEntry(t, true)}, 'Load and start')))));
  }
  async fetchTape(entry) { return new Uint8Array(await (await fetch(entry.file)).arrayBuffer()); }
  async loadEntry(entry, boot) {
    const bytes = await this.fetchTape(entry);
    await this.mount(bytes, entry.title);
    this.onLibraryLoad?.(entry, boot);
  }
  async referenceLeader() {
    if (!this.reference) this.reference = await this.fetchTape(this.library.find(t => t.id === 'hello'));
    return this.reference;
  }
  async mount(bytes, name) {
    await this.onLibraryLoad?.({}, false);
    this.mounted = bytes; this.mountedName = name;
    this.readerName.textContent = name;
    await this.machine.mountTape(bytes);
    this.toast(`Mounted tape: ${name} · ${bytes.length.toLocaleString()} lines`);
    this.redraw();
  }
  update(s) {
    this.plotter.update(s);
    const p = s.units?.punch;
    if (p) this.punchStatus.textContent = `${p.motor ? 'Motor running' : 'Motor stopped'} · ${p.ready ? 'Buffer ready' : 'Buffer busy'} · ${p.lamp ? 'Red lamp on' : 'Red lamp off'} · ${p.eia ? 'EIA' : ''}`;
    const punch = s.dev.punch || [];
    if (punch.length) { this.punched.push(...punch); this.punchCount.textContent = `${this.punched.length.toLocaleString()} lines`; }
    this.pos = s.tape.pos;
    const pct = s.tape.size ? 100 * s.tape.pos / s.tape.size : 0;
    this.readerBar.style.width = pct + '%';
    this.readerPos.textContent = s.tape.size ? `${s.tape.pos.toLocaleString()} / ${s.tape.size.toLocaleString()} lines · ${s.tape.rewinds} rewinds` : '';
    const now = performance.now();
    if (punch.length || !this.lastDraw || now - this.lastDraw > 120) { this.lastDraw = now; this.redraw(); }
  }
  redraw() {
    if (this.readerStrip.offsetParent) drawStrip(this.readerStrip, this.mounted, this.pos || 0);
    if (this.punchStrip.offsetParent) drawStrip(this.punchStrip, this.punched, this.punched.length - 1);
    this.plotter?.redraw();
  }
  need(bytes) { if (!bytes || !bytes.length) { this.toolOut.textContent = 'No tape data.'; return false; } return true; }
  setResult(bytes, name, text) { this.toolResult = {bytes, name}; this.toolOut.textContent = `${text}\nResult: ${bytes.length} lines. Download or mount in the reader.`; }
  info(t) {
    if (!this.need(t)) return;
    const seventh = t.filter(b => b & T.SEVENTH).length, punched = t.filter(b => b & T.FEED).length;
    const bl = T.blocks(t);
    const lines = [`${t.length} lines, ${punched} punched lines, ${seventh} lines with a seventh hole`, 'Blocks after the 20-word leader:', ' No.  Start   Words   Next     Checksum'];
    bl.forEach((b, i) => lines.push(b.error ? ` ${i}  ${b.error}` : ` ${String(i).padStart(2)}  ${oct(b.start, 6)}  ${String(b.count).padStart(5)}   ${oct(b.next, 6)}   ${b.ok ? 'OK' : 'ERROR'}`));
    if (bl.some(b => b.ok === false || b.next === 0o27 && b !== bl.at(-1))) lines.push('', 'Checksums or block links do not match the plugboard leader. Use Repair upstream tape.');
    this.toolOut.textContent = lines.join('\n');
  }
  dump(t) {
    if (!this.need(t)) return;
    const n = Math.min(t.length, 2000), out = [];
    for (let i = 0; i < n; i++) {
      const b = t[i], holes = [5, 4, 3].map(k => b >> k & 1 ? '●' : '·').join('') + '∘' + [2, 1, 0].map(k => b >> k & 1 ? '●' : '·').join('');
      out.push(`${String(i).padStart(6)}  ${oct(b & 63, 2)}  ${b & 64 ? '7' : ' '}  ${holes}${b & 128 ? '' : '  no feed hole'}`);
    }
    if (t.length > n) out.push(`… ${t.length - n} more lines. Download and use tools/tx2tape.py dump to view all lines.`);
    this.toolOut.textContent = out.join('\n');
  }
  words(t) {
    if (!this.need(t)) return;
    const ws = T.words(t).slice(0, 2000);
    this.toolOut.textContent = ws.map((w, i) => `${String(i).padStart(5)}  ${oct(Math.floor(w / 2 ** 18), 6)} ${oct(w % 2 ** 18, 6)}`).join('\n');
  }
  fix(t) {
    if (!this.need(t)) return;
    try { this.setResult(T.relink(t), 'fixed.tape', 'Set non-final block links to leader loop address 3 and recomputed all checksums with 18-bit ones-complement end-around addition.'); }
    catch (e) { this.toolOut.textContent = 'Repair failed: ' + e.message; }
  }
  async program(addrText, bodyText) {
    const a = parseOct(addrText, 0o377777);
    const body = bodyText.split(/\s+/).filter(Boolean).map(v => parseOct(v));
    if (a === null || !body.length || body.some(v => v === null)) { this.toolOut.textContent = 'Address and words must be octal.'; return; }
    this.setResult(T.programTape(await this.referenceLeader(), a, body), 'program.tape', `${body.length} words starting at ${oct(a)}; jump to ${oct(a)} after loading.`);
  }
}
