import { describe, expect, it } from 'vitest';
import { fmtMoney, getDraft, STATUS_LABEL, type DraftPlayer } from '../src/lib/draft';

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
