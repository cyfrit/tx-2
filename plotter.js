import {el, download} from './util.js';

// TR296:4383–4385: EAI 29 × 29 inch paper. Strokes are host-decoded
// geometry; see web/devices/plotter.h for the explicitly inferred analog model.
export class PlotterPanel {
  constructor(page, {machine, toast, punched}) {
    Object.assign(this, {machine, toast, punched});
    this.paths = {direct: [], offline: []};
    this.source = el('select', {}, el('option', {value: 'direct'}, 'Online plotting · 74'), el('option', {value: 'offline'}, 'Offline paper tape plotting'));
    this.source.onchange = () => this.redraw();
    this.canvas = el('canvas', {width: 1200, height: 1200, style: 'width:100%;max-width:740px;height:auto;display:block;background:#fff;'});
    this.readout = el('div', {class: 'hint'});
    const upload = el('input', {type: 'file', accept: '.tape', style: 'display:none'});
    upload.onchange = async () => { const f=upload.files[0]; if(f) await this.readTape(new Uint8Array(await f.arrayBuffer())); upload.value=''; };
    page.append(el('fieldset', {}, el('legend', {}, 'EAI pen-and-ink plotter · 74'),
      el('div', {class: 'row'}, this.source,
        el('button', {class: 'key dark', onclick: () => this.readTape(Uint8Array.from(this.punched()))}, 'Read punch output'),
        el('button', {class: 'key dark', onclick: () => upload.click()}, 'Upload plotter tape'), upload,
        el('button', {class: 'key dark', onclick: () => this.canvas.toBlob(b => b && download('tx2-plotter.png', b), 'image/png')}, 'Export PNG'),
        el('button', {class: 'key dark', onclick: async () => { const k=this.source.value; this.paths[k]=[]; await machine.cmd(`dev plotter paper ${k}`); this.redraw(); }}, 'New paper')),
      this.canvas, this.readout,
      el('div', {class: 'hint'}, '29 × 29 inch paper. Sketchpad 4.8 PLOT draws online; 4.7 PUNCH generates offline tape. Tape contains control words with seventh holes, six-line assembled data words and a trailing tally line.'),
      el('div', {class: 'hint'}, '[INFERENCE] The missing unit 74 hardware chapter leaves DAC wiring, filtering and pen-transition delays unresolved. Paper output uses ideal geometric reconstruction. Raw tally values are preserved; error-checking circuitry is unspecified.')));
    this.redraw();
  }
  async readTape(bytes) {
    if(!bytes.length) { this.toast('No plotter tape data.'); return; }
    this.paths.offline=[];
    await this.machine.cmd('dev plotter paper offline');
    let hex=''; for(const b of bytes) hex+=b.toString(16).padStart(2,'0');
    const r=await this.machine.cmd('dev plotter tape '+hex);
    this.source.value='offline';
    // Consume the decoder event through the same update path, also when paused.
    this.update(await this.machine.cmd('state'));
    this.toast(`Offline tape: ${r.records || 0} plotting blocks`);
  }
  update(s) {
    const e=s.dev?.plotter;
    if(e) for(const k of ['direct','offline']) if(e[k]?.length) this.paths[k].push(...e[k]);
    if(e?.[this.source.value]?.length) this.redraw();
  }
  redraw() {
    if(!this.canvas.offsetParent) return;
    const g=this.canvas.getContext('2d'), n=this.canvas.width, margin=25, scale=(n-2*margin)/32766;
    g.fillStyle='#fffef8'; g.fillRect(0,0,n,n);
    g.strokeStyle='#c9c3b4'; g.lineWidth=1; g.strokeRect(margin,margin,n-2*margin,n-2*margin);
    g.save();g.beginPath();g.rect(margin,margin,n-2*margin,n-2*margin);g.clip();
    g.strokeStyle='#172735';g.lineWidth=1.6;g.lineCap='round';g.beginPath();
    const paths=this.paths[this.source.value];
    for(const [x0,y0,x1,y1] of paths) {g.moveTo(n/2+x0*scale,n/2-y0*scale);g.lineTo(n/2+x1*scale,n/2-y1*scale);}
    g.stroke();g.restore();
    this.readout.textContent=`${this.source.value==='direct'?'Online':'Offline'} · ${paths.length.toLocaleString()} stroke segments`;
  }
}
