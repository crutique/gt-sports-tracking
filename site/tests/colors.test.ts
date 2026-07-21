import { describe, expect, it } from 'vitest';
import { percentileColor } from '../src/lib/colors';

// WCAG relative luminance / contrast, used to pin the accessibility contract:
// every chip on the ramp renders 11px bold white text, so every color the ramp
// can produce must stay ≥ 4.5:1 against white.
function linear(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
}
function contrastVsWhite(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const l = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
  return 1.05 / (l + 0.05);
}

describe('percentileColor', () => {
  it('hits the anchor colors', () => {
    expect(percentileColor(0)).toBe('#3566cc');
    expect(percentileColor(50)).toBe('#5f6d83');
    expect(percentileColor(100)).toBe('#c53022');
  });

  it('interpolates between anchors', () => {
    const c25 = percentileColor(25);
    expect(c25).toMatch(/^#[0-9a-f]{6}$/);
    expect(c25).not.toBe('#3566cc');
    expect(c25).not.toBe('#5f6d83');
  });

  it('clamps out-of-range input', () => {
    expect(percentileColor(-5)).toBe('#3566cc');
    expect(percentileColor(120)).toBe('#c53022');
  });

  it('keeps white text AA-readable (≥4.5:1) at every percentile', () => {
    for (let p = 0; p <= 100; p++) {
      expect(contrastVsWhite(percentileColor(p)), `percentile ${p}`)
        .toBeGreaterThanOrEqual(4.5);
    }
  });
});
