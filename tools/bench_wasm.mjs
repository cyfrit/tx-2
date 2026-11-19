// WebAssembly throughput, same scenario and fingerprint as tools/bench_sim.py:
// Usage: node tools/bench_wasm.mjs [clocks] [tracking|boot|transport|halted]
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const moduleURL = process.env.TX2_WASM_JS ? pathToFileURL(resolve(process.env.TX2_WASM_JS))
                                        : new URL('../build/wasm/tx2.js', import.meta.url);
const {default: create} = await import(moduleURL);

const m = await create();
const cmd = line => {
  const p = m.stringToNewUTF8(line);
  const out = JSON.parse(m.UTF8ToString(m._tx2_command(p)));
  m._free(p);
  return out;
};
const n = Number(process.argv[2] ?? 10_000_000), workload = process.argv[3] ?? 'tracking';
if (!Number.isSafeInteger(n) || n <= 0) throw Error('expected a positive integer clock count');
let s;
if (workload === 'tracking' || workload === 'boot') {
  cmd(`tape ${readFileSync(new URL('../programs/sketchpad/sketchpad.tape', import.meta.url)).toString('hex')}`);
  cmd(`set suppress ${0o200}`); cmd('set reader_us 64'); cmd(`press codabo ${0o377750}`);
  if (workload === 'tracking') {
    for (let i = 0; i < 120; i++) {
      s = cmd('run 1000000 0 0 0');
      if (s.tape.pos === s.tape.size && s.points) break;
    }
    if (!s.points || s.tape.pos !== s.tape.size) throw Error('Sketchpad warm-up failed');
    s = cmd('run 800000 -128 110 1');
  }
} else if (workload === 'transport') {
  // CPU stopped, PETR winding manually, one line every 2000 board clocks.
  cmd(`tape ${'c1'.repeat(Math.ceil(n / 2000) + 2)}`);
  cmd('set reader_us 1000'); cmd('dev petr wind');
} else if (workload !== 'halted') throw Error(`unknown workload: ${workload}`);
s ??= cmd('state');
const pen = workload === 'tracking' ? '-128 110 1' : '0 0 0';
const c0 = s.cycles, r0 = s.retired, trail = createHash('sha256'), t = performance.now();
for (let i = 0; i < n; i += 200_000) {
  s = cmd(`run ${Math.min(n - i, 200_000)} ${pen}`);
  trail.update(JSON.stringify(s));
}
const dt = (performance.now() - t) / 1000;
console.log(JSON.stringify({workload, clocks: s.cycles - c0, clocks_per_s: Math.round((s.cycles - c0) / dt), instr_per_s: Math.round((s.retired - r0) / dt),
                            fault: s.fault, seconds: +dt.toFixed(2), retired: s.retired, fingerprint: trail.digest('hex').slice(0, 16)}));
