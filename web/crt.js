// Point-plotting scope: phosphor model, glow, light pen and camera.
// Spots come from the RTL display unit: 10-bit ones-complement X/Y and four intensities.
const PHOSPHORS = {
  // [fresh flash colour, long-persistence colour]
  P7: ['#d8e8ff', '#c8ff7a'], P31: ['#d6ffe0', '#5cff8a'], P4: ['#ffffff', '#e8eef8'],
  amber: ['#fff0c8', '#ffb340'], P11: ['#e0f0ff', '#58a8ff'],
};
const hex = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));

export class Scope {
  constructor({beam, glow, overlay, settings, onPen, onTap}) {
    Object.assign(this, {beam, glow, overlay, settings, onPen, onTap});
    this.ctx = beam.getContext('2d');
    this.gctx = glow.getContext('2d');
    this.octx = overlay.getContext('2d');
    this.spots = new Map();      // key -> {x, y, c, i}; c is the cycle, i the intensity.
    this.cycles = 0; this.ticksPerUs = 2;
    this.pen = {active: false, x: 0, y: 0, cursorX: 0, cursorY: 0, lag: 0};
    this.attachPointer();
    requestAnimationFrame(t => this.frame(t));
  }
  get zoom() { return this.program?.zoom ?? this.settings.crt.zoom; }
  get penRadius() { return this.program?.radius ?? this.settings.pen.radius; }
  toPixel(x, y) { return [512 + x * this.zoom, 512 - y * this.zoom]; }
  fromEvent(e) {
    const r = this.overlay.getBoundingClientRect();
    const px = (e.clientX - r.left) * 1024 / r.width, py = (e.clientY - r.top) * 1024 / r.height;
    const clamp = v => Math.max(-511, Math.min(511, Math.round(v)));
    return {x: clamp((px - 512) / this.zoom), y: clamp((512 - py) / this.zoom)};
  }
  // Events are [x, y, intensity, unit]; octal units 056 and 060 are separate scopes, decimal 46 and 48.
  addSpots(points, cycles, ticksPerUs) {
    this.cycles = cycles; this.ticksPerUs = ticksPerUs;
    const want = this.program?.output ?? this.settings.crt.scope ?? 'both';
    for (const [x, y, i, unit] of points) {
      if (want !== 'both' && unit !== (want === '60' ? 0o60 : 0o56)) continue;
      this.spots.set((x + 512) * 1024 + y + 512, {x, y, c: cycles, i});
    }
  }
  clear() { this.spots.clear(); }
  setPen(active, x = this.pen.x, y = this.pen.y) {
    Object.assign(this.pen, {active, x, y});
    this.onPen(x, y, active);
  }
  attachPointer() {
    const o = this.overlay;
    let down = null;
    o.addEventListener('pointerdown', e => {
      if (down || e.button !== 0) return;
      e.preventDefault(); o.setPointerCapture(e.pointerId);
      const p = this.fromEvent(e);
      down = {id: e.pointerId, x: e.clientX, y: e.clientY, moved: false, wasActive: this.pen.active};
      if (this.program?.contactOnly || !this.pen.active || e.pointerType !== 'mouse') this.setPen(true, p.x, p.y);
    });
    o.addEventListener('pointermove', e => {
      if (down && down.id !== e.pointerId) return;
      if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6) down.moved = true;
      // Digit entry follows held contacts; Sketchpad retains its hovering tracking pen.
      if (this.pen.active && (down || (!this.program?.contactOnly && e.pointerType === 'mouse'))) {
        const events = e.getCoalescedEvents?.() || [];
        for (const point of events.length ? events : [e]) {
          const p = this.fromEvent(point); this.setPen(true, p.x, p.y);
        }
      }
    });
    o.addEventListener('pointerup', e => {
      if (!down || down.id !== e.pointerId) return;
      if (this.program?.contactOnly) {
        const p = this.fromEvent(e);
        this.setPen(true, p.x, p.y);
        this.setPen(false);
      } else if (!down.moved && down.wasActive) this.onTap?.(this.fromEvent(e));
      down = null;
    });
    const cancel = e => {
      if (!down || (e.pointerId !== undefined && down.id !== e.pointerId)) return;
      down = null; this.setPen(false); this.cancelPen?.();
    };
    o.addEventListener('pointercancel', cancel);
    o.addEventListener('lostpointercapture', cancel);
    addEventListener('blur', cancel);
    o.addEventListener('contextmenu', e => e.preventDefault());
  }
  frame() {
    const s = this.settings.crt, ctx = this.ctx;
    const [fresh, slow] = (PHOSPHORS[s.phosphor] || PHOSPHORS.P7).map(hex);
    const persistUs = Math.max(0.02, s.persistence) * 1e6;
    const tau = persistUs / 3, flashTau = Math.min(20000, persistUs / 20);
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = '#030604'; ctx.fillRect(0, 0, 1024, 1024);
    ctx.globalCompositeOperation = 'lighter';
    for (const [key, p] of this.spots) {
      const age = (this.cycles - p.c) / this.ticksPerUs;
      if (age > persistUs) { this.spots.delete(key); continue; }
      const slowA = Math.exp(-age / tau), flashA = Math.exp(-age / flashTau);
      const level = (0.55 + p.i * 0.15) * s.brightness;
      const r = Math.round(slow[0] * (1 - flashA) + fresh[0] * flashA);
      const g = Math.round(slow[1] * (1 - flashA) + fresh[1] * flashA);
      const b = Math.round(slow[2] * (1 - flashA) + fresh[2] * flashA);
      ctx.fillStyle = `rgba(${r},${g},${b},${Math.min(1, level * slowA)})`;
      const [x, y] = this.toPixel(p.x, p.y);
      const size = s.dot * (this.program?.spotScale?.[p.i] ?? 1), half = size / 2;
      ctx.fillRect(x - half, y - half, size, size);
    }
    // Bloom: the glow canvas is blurred by CSS; drawing is a plain copy.
    this.glow.style.opacity = s.glow;
    if (s.glow > 0) { this.gctx.clearRect(0, 0, 1024, 1024); this.gctx.drawImage(this.beam, 0, 0); }
    this.drawOverlay();
    requestAnimationFrame(t => this.frame(t));
  }
  drawOverlay() {
    const o = this.octx, p = this.pen;
    o.clearRect(0, 0, 1024, 1024);
    if (!p.active || !this.settings.crt.penMarker) return;
    const [x, y] = this.toPixel(p.x, p.y), r = this.penRadius * this.zoom;
    o.strokeStyle = 'rgba(255,214,140,.55)'; o.lineWidth = 1.5;
    o.beginPath(); o.arc(x, y, r, 0, Math.PI * 2);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { o.moveTo(x + dx * r, y + dy * r); o.lineTo(x + dx * (r + 9), y + dy * (r + 9)); }
    o.stroke();
    if (p.lag > 2) {
      const [cx, cy] = this.toPixel(p.cursorX, p.cursorY);
      o.fillStyle = 'rgba(255,214,140,.8)'; o.fillRect(cx - 3, cy - 3, 6, 6);
      o.setLineDash([4, 5]); o.beginPath(); o.moveTo(cx, cy); o.lineTo(x, y); o.stroke(); o.setLineDash([]);
    }
  }
  // Camera records the beam image.
  snapshot() { return this.beam.toDataURL('image/png'); }
}
