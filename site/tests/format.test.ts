import { describe, expect, it } from 'vitest';
import { fmtDate, fmtEra, fmtPct, fmtPer9, fmtRate3, outsToIp, classFull } from '../src/lib/format';

describe('formatters', () => {
  it('formats batting rates savant-style', () => {
    expect(fmtRate3(0.298)).toBe('.298');
    expect(fmtRate3(1.0)).toBe('1.000');
    expect(fmtRate3(0.9124)).toBe('.912');
    expect(fmtRate3(null)).toBe('—');
  });

  it('formats ERA/WHIP at 2 decimals', () => {
    expect(fmtEra(2.6518)).toBe('2.65');
    expect(fmtEra(null)).toBe('—');
  });

  it('formats percentages from fractions', () => {
    expect(fmtPct(0.2371)).toBe('24%');
    expect(fmtPct(0)).toBe('0%');
    expect(fmtPct(null)).toBe('—');
  });

  it('formats per-9 rates at 1 decimal', () => {
    expect(fmtPer9(9.878)).toBe('9.9');
    expect(fmtPer9(null)).toBe('—');
  });

  it('converts outs to IP display', () => {
    expect(outsToIp(18)).toBe('6.0');
    expect(outsToIp(19)).toBe('6.1');
  });

  it('formats ISO dates as short month-day', () => {
    expect(fmtDate('2026-07-12')).toBe('Jul 12');
  });
});

describe('classFull', () => {
  it('writes out class years', () => {
    expect(classFull('FR')).toBe('Freshman');
    expect(classFull('SO')).toBe('Sophomore');
    expect(classFull('JR')).toBe('Junior');
    expect(classFull('SR')).toBe('Senior');
  });
  it('expands redshirt prefixes', () => {
    expect(classFull('R-SO')).toBe('Redshirt Sophomore');
    expect(classFull('R-SR')).toBe('Redshirt Senior');
  });
  it('passes unknown values through', () => {
    expect(classFull('GR')).toBe('GR');
    expect(classFull('')).toBe('');
  });
});
