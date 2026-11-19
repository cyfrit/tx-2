// Shared helpers: DOM, octal formatting, persisted settings.
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) if (c != null) e.append(c);
  return e;
}

export const oct = (v, width = 0) => Number(v).toString(8).padStart(width, '0');
export const parseOct = (s, max = 2 ** 36 - 1) => {
  const t = String(s).trim();
  if (!/^[0-7]+$/.test(t)) return null;
  const v = parseInt(t, 8);
  return v <= max ? v : null;
};
// TX-2 bit numbering: quarter.bit, quarter 1 lowest; bit 1.1 has value 1.
export const bitName = i => `${Math.floor(i / 9) + 1}.${(i % 9) + 1}`;
// 36-bit words fit exactly in JS doubles; split for bitwise work.
export const bit36 = (v, i) => Math.floor(v / 2 ** i) % 2;
export const setBit36 = (v, i, on) => (bit36(v, i) === (on ? 1 : 0) ? v : v + (on ? 1 : -1) * 2 ** i);

const KEY = 'tx2-settings-v1';
export const DEFAULTS = {
  crt: {scope: 'both', phosphor: 'P7', persistence: 2, glow: 0.6, dot: 2, brightness: 1, zoom: 1.6, effects: true, penMarker: true},
  pen: {limit: true, speed: 2, radius: 12},
  timing: {profile: 'interactive', writer: true, punch: true, reader: false, batchMs: 12},
  console: {tsp: 0o377750, toggles: Array(16).fill(0), tmeta: 0, fixed: Array(8).fill(0), suppress: 0, hold: false},
  inputs: {knobs: [0, 0, 0, 0], kmeta: false, latch: false},
};
export function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
    const out = structuredClone(DEFAULTS);
    for (const k of Object.keys(out)) Object.assign(out[k], saved[k] || {});
    return out;
  } catch { return structuredClone(DEFAULTS); }
}
export const saveSettings = s => localStorage.setItem(KEY, JSON.stringify(s));

export function download(name, data, type = 'application/octet-stream') {
  const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], {type}));
  const a = el('a', {href: url, download: name}); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
