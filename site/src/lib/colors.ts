// Anchors are tuned so that every interpolated color keeps white text at
// ≥4.5:1 (WCAG AA) — the ramp's worst case is ~5.25:1 at the midpoint.
// Verified by the contrast sweep in tests/colors.test.ts.
const LOW: [number, number, number] = [0x35, 0x66, 0xcc];
const MID: [number, number, number] = [0x5f, 0x6d, 0x83];
const HIGH: [number, number, number] = [0xc5, 0x30, 0x22];

function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  const ch = a.map((av, i) => Math.round(av + (b[i] - av) * t));
  return `#${ch.map((c) => c.toString(16).padStart(2, '0')).join('')}`;
}

/** Percentile (0-100) → hex color on the blue→gray→red scale. Red = good. */
export function percentileColor(p: number): string {
  const c = Math.max(0, Math.min(100, p));
  return c <= 50 ? mix(LOW, MID, c / 50) : mix(MID, HIGH, (c - 50) / 50);
}
