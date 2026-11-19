import {el, oct, download} from './util.js';

// Abstract controller-transfer images. See device-specs/magnetic-tape.md §§4–5:
// TX-2 block marks are preformatted; IBM data are binary halfword records.
export class MagTapePanel {
  constructor(root, {machine, toast}) {
    this.machine = machine; this.toast = toast; this.readouts = [];
    root.append(el('h2', {}, 'Magnetic tape storage'), el('p', {}, '046: TX-2 addressed tape, four drives, 9-bit transfers. 045: IBM tape, 18-bit record transfers. Images preserve raw data and checksum words written by programs. Before loading, ejecting or rewinding, disconnect 046 and stop motion on 045. Images can be saved at any time.'));
    for (const [name, count, title] of [['magtape', 4, 'TX-2 addressed tape · 046'], ['ibmtape', 1, 'IBM tape · 045']]) {
      const section = el('section', {class: 'card'});
      section.append(el('h3', {}, title));
      for (let drive = 0; drive < count; drive++) {
        const suffix = name === 'magtape' ? ` ${drive}` : '';
        const status = el('pre', {}, 'No tape mounted');
        const button = (label, fn) => el('button', {onclick: async () => {
          try { await fn(); } catch (e) { toast(e.message); }
        }}, label);
        const send = async (op, args = '') => {
          const r = await machine.cmd(`dev ${name} ${op}${suffix}${args ? ' ' + args : ''}`);
          if (r.error) throw Error(r.error);
          const s = await machine.cmd(`dev ${name} status`);
          this.paint(name, s);
          return r;
        };
        const file = el('input', {type: 'file', accept: '.tx2mt,.tx2ibm,.txt', hidden: true});
        file.onchange = async () => {
          try {
            if (!file.files[0]) return;
            const text = await file.files[0].text();
            await send('import', text.replace(/\s+/g, ' ').trim());
            toast('Tape image loaded');
          } catch (e) { toast(e.message); }
          file.value = '';
        };
        const protect = el('input', {type: 'checkbox'});
        protect.onchange = async () => { try { await send('protect', protect.checked ? '1' : '0'); } catch (e) { protect.checked = !protect.checked; toast(e.message); } };
        section.append(el('div', {class: 'row'}, el('strong', {}, name === 'magtape' ? `Drive ${drive}` : 'Drive'),
          button('New blank tape', () => send('create')),
          button('Load image', () => file.click()),
          button('Save image', async () => {
            const {image} = await send('export');
            download(`${name}-${drive}.${name === 'magtape' ? 'tx2mt' : 'tx2ibm'}`, image, 'text/plain');
          }),
          button('Rewind', () => send('rewind')),
          button('Eject', () => send('eject')),
          el('label', {}, protect, ' Write protect'), file), status);
        this.readouts.push({name, drive, status, protect});
      }
      root.append(section);
    }
    root.append(el('p', {}, 'Source limitations: complete primary descriptions remain unavailable for 046 drive-selection encoding, speed-code mappings to inches per second, IBM character track ordering and hardware parity format. The simulator uses reversible block/record images that preserve program-visible word widths, block boundaries and interrecord gaps. The default transfer period is 125 μs.'));
  }
  paint(name, s) {
    if (!s) return;
    for (const row of this.readouts.filter(r => r.name === name)) {
      const d = name === 'magtape' ? s.drives[row.drive] : s;
      row.protect.checked = !!d.protect;
      const motion = name === 'magtape' ? `Mode ${oct(s.mode, 4)} · ${s.input ? 'Read' : 'Write'} · speed code ${s.speed} · ${s.assembly ? 'Assembly' : 'Normal'} · selected drive ${s.selected}` : `${['Rewind', 'Sense tape mark', 'Forward read', 'Stop read', 'Forward', 'Forward write', 'Reverse read', 'Check stop'][s.operation]} · record position ${s.record} · halfword position ${s.offset}${s.gap ? ' · interrecord gap' : ''}`;
      row.status.textContent = `${d.mounted ? 'Mounted' : 'No tape mounted'} · ${d.protect ? 'Write protected' : 'Writable'}\n${name === 'magtape' ? `${d.blocks} blocks · ${d.written} written blocks · physical line position ${d.position}` : `${d.records} records · ${s.pending} pending halfwords`}\n${motion} · ${s.connected ? 'Connected' : 'Disconnected'}\n${s.transfers} transfers · period ${s.periodUs} μs · MIS ${s.mis} · EIA ${s.eia}`;
    }
  }
  update(s) { this.paint('magtape', s.units?.magtape); this.paint('ibmtape', s.units?.ibmtape); }
}
