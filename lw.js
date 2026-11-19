// Lincoln Writer character codes. TX-2 Users Handbook table 7-6, Group Report 51-8.
// Decoding follows the TX-2 Project's MIT-licensed base/src/charset.rs. The lower-case
// keyboard carries capitals and digits; carriage return resets to lower case, normal script.
const LOWER = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '\u0332', '\u20DD', null, null, null, null,
  'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P',
  'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '(', ')', '+', '-', ',', '.'];
const UPPER = ['☛', 'Σ', '|', '‖', '/', '×', '#', '→', '<', '>', '\u0305', '\u20DE', null, null, null, null,
  'n', '⊂', '∨', 'q', 'γ', 't', 'w', 'x', 'i', 'y', 'z', '?', '∪', '∩', 'j', 'k',
  'α', 'Δ', 'p', 'ε', 'h', '⊃', 'β', '∧', 'λ', '~', '{', '}', '≡', '=', "'", '*'];
export const NAMES = {0o14: 'READ IN', 0o15: 'BEGIN', 0o16: 'NO', 0o17: 'YES', 0o60: 'CARRIAGE RETURN', 0o61: 'TAB',
  0o62: 'BACKSPACE', 0o63: 'COLOR BLACK', 0o64: 'SUPER', 0o65: 'NORMAL', 0o66: 'SUB', 0o67: 'COLOR RED', 0o70: 'SPACE',
  0o71: 'WORD EXAM', 0o72: 'LINE FEED DOWN', 0o73: 'LINE FEED UP', 0o74: 'LOWER CASE', 0o75: 'UPPER CASE', 0o76: 'STOP', 0o77: 'NULLIFY'};

export const newState = () => ({script: 'normal', upper: false, red: false});

// Returns {ch, script, red, advance} for printable codes, {newline} / {tab} / {backspace}, or null.
export function decode(code, st) {
  switch (code) {
    case 0o60: {
      const scriptMove = st.script === 'super' ? 1 : st.script === 'sub' ? -1 : 0;
      st.script = 'normal'; st.upper = false; return {newline: true, scriptMove};
    }
    case 0o61: return {tab: true};
    case 0o62: return {backspace: true};
    case 0o63: st.red = false; return null;
    case 0o64: { const from = st.script; st.script = 'super'; return {scriptMove: ['super', 'normal', 'sub'].indexOf(st.script) - ['super', 'normal', 'sub'].indexOf(from)}; }
    case 0o65: { const from = st.script; st.script = 'normal'; return {scriptMove: ['super', 'normal', 'sub'].indexOf(st.script) - ['super', 'normal', 'sub'].indexOf(from)}; }
    case 0o66: { const from = st.script; st.script = 'sub'; return {scriptMove: ['super', 'normal', 'sub'].indexOf(st.script) - ['super', 'normal', 'sub'].indexOf(from)}; }
    case 0o67: st.red = true; return null;
    case 0o70: return {ch: ' ', script: st.script, red: st.red};
    // LW 633-655: platen motion is relative and does not select script.
    case 0o72: return {lineFeed: 1};
    case 0o73: return {lineFeed: -1};
    case 0o74: st.upper = false; return null;
    case 0o75: st.upper = true; return null;
  }
  const ch = code < 0o60 ? (st.upper ? UPPER : LOWER)[code] : null;
  if (ch == null) return null; // H63 p.121: function keys consume time but print nothing.
  return {ch, script: st.script, red: st.red, combining: code === 0o12 || code === 0o13};
}

// Text -> LW codes with automatic case-change codes, as the keyboard generates them.
export function encode(text, st = {upper: false}) {
  const codes = [];
  for (const ch of text) {
    if (ch === '\n' || ch === '\r') { codes.push(0o60); st.upper = false; continue; }
    if (ch === '\t') { codes.push(0o61); continue; }
    if (ch === ' ') { codes.push(0o70); continue; }
    if (ch === '\b') { codes.push(0o62); continue; }
    let code = UPPER.indexOf(ch), upper = true;
    if (code < 0 || code >= 0o60) { code = LOWER.indexOf(ch.toUpperCase()); upper = false; }
    if (code < 0) continue;
    if (st.upper !== upper) { codes.push(upper ? 0o75 : 0o74); st.upper = upper; }
    codes.push(code);
  }
  return codes;
}

// A key's seventh internal wire identifies the keyboard; the host compares
// it against the shared physical case relay and emits 74/75 when required.
export function encodeKeyboard(text) {
  const keys = [];
  for (const ch of text) {
    const codes = encode(ch, {upper: false});
    if (!codes.length) continue;
    keys.push(codes.at(-1) | (codes[0] === 0o75 ? 0o100 : 0));
  }
  return keys;
}
