import { useEffect, useRef } from "react";

/** Slow contour lines drifting behind the sign-in wordmark. */
export default function WaveCanvas({ className = "" }) {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    const ctx = c.getContext("2d");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const size = () => { c.width = c.clientWidth * devicePixelRatio; c.height = c.clientHeight * devicePixelRatio; };
    size();
    window.addEventListener("resize", size);
    const frame = (t) => {
      const w = c.width, h = c.height, dpr = devicePixelRatio;
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < 16; i++) {
        ctx.beginPath();
        const base = h * (0.18 + i * 0.05), amp = h * 0.035 * (1 + (i % 4) * 0.4), ph = t / 5200 + i * 0.55;
        for (let x = 0; x <= w; x += 8 * dpr) {
          const y = base + Math.sin(x / (w / 2.6) + ph) * amp + Math.sin(x / (w / 7.3) - ph * 1.7) * amp * 0.35;
          if (x) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        }
        ctx.strokeStyle = `rgba(255,255,255,${0.035 + (i % 5) * 0.012})`;
        ctx.lineWidth = dpr;
        ctx.stroke();
      }
      if (!still) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", size); };
  }, []);
  return <canvas ref={ref} className={className} aria-hidden />;
}
