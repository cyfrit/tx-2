// .tape format: one byte per line; bit 7 feed hole, bit 6 seventh hole, bits 5-0 data. See tools/tx2tape.py.
import {encode} from './lw.js';
export const FEED = 0x80, SEVENTH = 0x40, DATA = 0x3f;
const M18 = 2 ** 18 - 1;
const hi = w => Math.floor(w / 2 ** 18), lo = w => w % 2 ** 18;
// -sum mod (2^18 - 1): the one's-complement ring checksum used by the reader leader.
const negmod = sum => (M18 - sum % M18) % M18;

export const dataLines = tape => [...tape].filter(b => b & FEED).map(b => b & DATA);
export function splay(word) {
  const lines = [];
  for (let col = 5; col >= 0; col--) {
    let line = 0;
    for (let bit = 0; bit < 6; bit++) line |= (Math.floor(word / 2 ** (6 * bit + col)) % 2) << bit;
    lines.push(line);
  }
  return lines;
}
export function unsplay(lines) {
  let word = 0;
  lines.forEach((line, col) => { for (let bit = 0; bit < 6; bit++) if (line >> bit & 1) word += 2 ** (6 * bit + 5 - col); });
  return word;
}
export function words(tape) {
  const lines = dataLines(tape), out = [];
  for (let i = 0; i + 6 <= lines.length; i += 6) out.push(unsplay(lines.slice(i, i + 6)));
  return out;
}
const count = header => { const f = hi(header); return 1 - (f < 2 ** 17 ? f : -(M18 - f)); };

// Reader-leader blocks after the 20-word leader: header (-(n-1), end), n words, trailer (checksum, next).
export function blocks(tape, leader = 20) {
  const ws = words(tape), out = [];
  for (let pos = leader; pos < ws.length;) {
    const n = count(ws[pos]);
    if (n <= 0 || pos + n + 1 >= ws.length) { out.push({word: pos, error: 'Invalid block length or truncated tape'}); break; }
    const t = ws[pos + n + 1];
    let sum = hi(t) + lo(t);
    for (const w of ws.slice(pos, pos + n + 1)) sum += hi(w) + lo(w);
    out.push({word: pos, start: lo(ws[pos]) - n + 1, count: n, next: lo(t), ok: sum % M18 === 0});
    pos += n + 2;
  }
  return out;
}
export function buildBlock(start, body, next) {
  const header = ((1 - body.length + M18 * 4) % M18) * 2 ** 18 + start + body.length - 1;
  let sum = next;
  for (const w of [header, ...body]) sum += hi(w) + lo(w);
  return [header, ...body, negmod(sum) * 2 ** 18 + next];
}
export const fromWords = ws => Uint8Array.from(ws.flatMap(w => splay(w).map(l => FEED | l)));

// Upstream tx2m4as tapes: relink non-final blocks to leader loop address 3 and recompute checksums.
export function relink(tape, leader = 20) {
  const ws = words(tape);
  for (let pos = leader; pos < ws.length;) {
    const n = count(ws[pos]), t = pos + n + 1;
    if (n <= 0 || t >= ws.length) throw new Error(`Invalid block at word ${pos}`);
    const next = t + 1 < ws.length ? 3 : lo(ws[t]);
    let sum = next;
    for (const w of ws.slice(pos, t)) sum += hi(w) + lo(w);
    ws[t] = negmod(sum) * 2 ** 18 + next;
    pos = t + 1;
  }
  return fromWords(ws);
}

// Loadable tape: standard reader leader from a reference tape, start block at 27, one program block.
export function programTape(leaderTape, address, body, start = address) {
  const leader = words(leaderTape).slice(0, 20);
  return fromWords([...leader, ...buildBlock(0o27, [0o010452020000, 0o140500000000 + start], 3), ...buildBlock(address, body, 0o27)]);
}
// Off-line Lincoln Writer tape: LW codes, seventh hole on every line.
export const textTape = (text, seventh = true) => Uint8Array.from(encode(text).map(c => FEED | (seventh ? SEVENTH : 0) | c));
