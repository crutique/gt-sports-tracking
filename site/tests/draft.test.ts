import { describe, expect, it } from 'vitest';
import { DEADLINE_LABEL, fmtMoney, fmtMoneyDelta, getDraft, isDeadlinePending, poolSummary, SIGNING_DEADLINE, STATUS_LABEL, type DraftPlayer } from '../src/lib/draft';

describe('poolSummary', () => {
  const base: Omit<DraftPlayer, 'name' | 'slot' | 'bonus' | 'status'> = {
    personId: null, gtRole: 'departing', slug: null, round: null, pick: null,
    team: null, bonusSource: null, reportedSourceUrl: null,
    unverifiedSourceUrl: null, signedDate: null, headshot: null, note: null,
  };
  const mk = (name: string, slot: number | null, bonus: number | null, status: DraftPlayer['status']): DraftPlayer =>
    ({ ...base, name, slot, bonus, status });

  it('sums slot pool, known bonuses, and counts unreported signings', () => {
    const s = poolSummary([
      mk('A', 1_000_000, 1_200_000, 'signed'),
      mk('B', 500_000, null, 'signed'),      // signed, terms not reported
      mk('C', 400_000, null, 'unsigned'),
      mk('D', null, 97_500, 'signed'),        // no slot (late round)
    ]);
    expect(s.slotPool).toBe(1_900_000);
    expect(s.signedKnown).toBe(1_297_500);
    expect(s.signedCount).toBe(3);
    expect(s.unreportedCount).toBe(1);
    expect(s.unsignedCount).toBe(1);
  });

  it('handles an empty class', () => {
    const s = poolSummary([]);
    expect(s.slotPool).toBe(0);
    expect(s.signedCount).toBe(0);
  });
});

describe('fmtMoneyDelta', () => {
  it('em-dashes when either side is unknown', () => {
    expect(fmtMoneyDelta(null, 1848200)).toBe('—');
    expect(fmtMoneyDelta(97500, null)).toBe('—');
    expect(fmtMoneyDelta(null, null)).toBe('—');
  });

  it('labels an exact-slot signing', () => {
    expect(fmtMoneyDelta(516300, 516300)).toBe('slot');
  });

  it('formats thousands with sign and one decimal', () => {
    expect(fmtMoneyDelta(7500000, 6982600)).toBe('+$517.4K');
    expect(fmtMoneyDelta(1900000, 1848200)).toBe('+$51.8K');
    expect(fmtMoneyDelta(500, 212000)).toBe('−$211.5K');
  });

  it('formats millions and sub-thousand deltas', () => {
    expect(fmtMoneyDelta(9000000, 6982600)).toBe('+$2M');
    expect(fmtMoneyDelta(1000, 1500)).toBe('−$500');
  });
});

describe('draft data', () => {
  it('loads the draft file with players and udfa arrays', () => {
    const d = getDraft();
    expect(Array.isArray(d.players)).toBe(true);
    expect(Array.isArray(d.udfa)).toBe(true);
  });

  it('maps every status to a label', () => {
    expect(STATUS_LABEL.signed).toBe('Signed');
    expect(STATUS_LABEL.unsigned).toBe('Unsigned');
    expect(STATUS_LABEL.returning).toBe('Returning to GT');
    expect(STATUS_LABEL.did_not_sign).toBe('Did not sign');
    expect(STATUS_LABEL.signed_udfa).toBe('Signed (UDFA)');
  });

  it('formats money and em-dashes null', () => {
    expect(fmtMoney(9740100)).toBe('$9,740,100');
    expect(fmtMoney(null)).toBe('—');
  });

  it('typechecks a DraftPlayer with the unverified bonus tier', () => {
    const p: DraftPlayer = {
      name: 'Test Player',
      personId: 1,
      gtRole: 'signee',
      slug: null,
      round: null,
      pick: null,
      team: null,
      slot: null,
      bonus: 9000000,
      bonusSource: 'unverified',
      reportedSourceUrl: null,
      unverifiedSourceUrl: 'https://fan.example',
      status: 'unsigned',
      signedDate: null,
      headshot: null,
      note: null,
    };
    expect(p.bonusSource).toBe('unverified');
    expect(p.unverifiedSourceUrl).toBe('https://fan.example');
  });
});

describe('signing deadline', () => {
  it('exposes the deadline label and instant', () => {
    expect(DEADLINE_LABEL).toBe('Jul 27');
    expect(new Date(SIGNING_DEADLINE).getTime()).toBeGreaterThan(0);
  });
  it('is pending before the deadline and resolved after', () => {
    expect(isDeadlinePending(new Date('2026-07-22T12:00:00-04:00'))).toBe(true);
    expect(isDeadlinePending(new Date('2026-07-27T16:59:00-04:00'))).toBe(true);
    expect(isDeadlinePending(new Date('2026-07-27T17:01:00-04:00'))).toBe(false);
    expect(isDeadlinePending(new Date('2026-08-01T00:00:00-04:00'))).toBe(false);
  });
});
