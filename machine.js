// Main-thread handle on the WebAssembly TX-2 worker.
export class Machine {
  constructor() {
    this.worker = new Worker('./worker.js', {type: 'module'});
    this.pending = new Map();
    this.nextId = 0;
    this.penVersion = 0;
    this.listeners = new Set();
    this.ready = new Promise((resolve, reject) => {
      this.worker.onerror = e => reject(new Error(e.message || 'worker failed'));
      this.worker.onmessage = ({data}) => {
        if (data.type === 'ready') resolve();
        else if (data.type === 'state') for (const f of this.listeners) f(data);
        else if (data.id !== undefined) { this.pending.get(data.id)?.(data.result); this.pending.delete(data.id); }
      };
    });
  }
  // Send one Machine::command line. See web/tx2_host.h.
  cmd(line) {
    return new Promise(resolve => {
      const id = this.nextId++;
      this.pending.set(id, resolve);
      this.worker.postMessage({id, cmd: line});
    });
  }
  pen(x, y, down) { this.worker.postMessage({type: 'pen', x, y, down, version: ++this.penVersion}); }
  config(config) { this.worker.postMessage({type: 'config', config}); }
  onState(f) { this.listeners.add(f); }
  mountTape(bytes) {
    let hex = '';
    for (const b of bytes) hex += b.toString(16).padStart(2, '0');
    return this.cmd('tape ' + hex);
  }
}
