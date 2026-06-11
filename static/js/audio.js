/** 音效模块 — fail-safe，静默降级，lazy init */
let ctx = null;

function getCtx() {
  if (ctx) return ctx;
  try {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    ctx = new Ctor();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  } catch (e) {
    ctx = null;
    return null;
  }
}

export function playTick(i) {
  try {
    const c = getCtx();
    if (!c) return;
    if (c.state === 'suspended') c.resume();

    const osc = c.createOscillator();
    const gain = c.createGain();

    gain.gain.setValueAtTime(0, c.currentTime);
    gain.gain.linearRampToValueAtTime(0.07, c.currentTime + 0.005);
    gain.gain.linearRampToValueAtTime(0, c.currentTime + 0.12);

    osc.type = 'sine';
    osc.frequency.setValueAtTime(i < 6 ? 600 + i * 80 : 300, c.currentTime);
    osc.connect(gain);
    gain.connect(c.destination);

    osc.start(c.currentTime);
    osc.stop(c.currentTime + 0.15);
  } catch (e) {
    // Audio unavailable — silent degradation
  }
}
