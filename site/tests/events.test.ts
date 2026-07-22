import { describe, expect, it } from 'vitest';
import { detectHitterEvents, detectPitcherEvents } from '../src/lib/events';
import type { HitterGame, PitcherGame } from '../src/lib/data';

function hg(over: Partial<HitterGame>): HitterGame {
  return {
    date: '2026-07-01', opponent: 'vs Test', ab: 4, r: 0, h: 1, d: 0, t: 0,
    hr: 0, rbi: 0, bb: 0, k: 0, sb: 0, ...over,
  };
}
function pg(over: Partial<PitcherGame>): PitcherGame {
  return {
    date: '2026-07-01', opponent: 'vs Test', ip_outs: 9, h: 2, r: 1, er: 1,
    bb: 1, k: 3, hr: 0, dec: '', ...over,
  };
}

describe('detectHitterEvents', () => {
  it('flags multi-HR, 4-hit, and 3-SB games', () => {
    const events = detectHitterEvents([
      hg({ date: '2026-07-04', hr: 2, h: 2 }),
      hg({ date: '2026-07-03', h: 4, ab: 5 }),
      hg({ date: '2026-07-02', sb: 3, h: 1 }),
      hg({ date: '2026-07-01', h: 1 }),
    ]);
    expect(events.map((e) => [e.date, e.label])).toEqual([
      ['2026-07-02', '3 SB'],
      ['2026-07-03', '4-hit game'],
      ['2026-07-04', '2 HR'],
    ]);
  });

  it('merges multiple feats in one game', () => {
    const events = detectHitterEvents([hg({ hr: 2, h: 4, ab: 5 })]);
    expect(events[0].label).toBe('2 HR · 4-hit game');
  });

  it('flags hit streaks of 5+ games at the streak end', () => {
    const games = ['01', '02', '03', '04', '05', '06'].map((d) =>
      hg({ date: `2026-07-${d}`, h: 1 }));
    games.push(hg({ date: '2026-07-07', h: 0 }));
    const events = detectHitterEvents(games);
    expect(events).toEqual([{ date: '2026-07-06', label: '6-game hit streak' }]);
  });

  it('ignores short streaks and quiet games', () => {
    expect(detectHitterEvents([
      hg({ date: '2026-07-01', h: 1 }),
      hg({ date: '2026-07-02', h: 1 }),
      hg({ date: '2026-07-03', h: 0 }),
    ])).toEqual([]);
  });
});

describe('detectPitcherEvents', () => {
  it('flags big strikeout days and scoreless outings of 4+ IP', () => {
    const events = detectPitcherEvents([
      pg({ date: '2026-07-08', k: 9 }),
      pg({ date: '2026-07-01', er: 0, ip_outs: 15, k: 4 }),
    ]);
    expect(events.map((e) => [e.date, e.label])).toEqual([
      ['2026-07-01', '5.0 scoreless IP'],
      ['2026-07-08', '9 K'],
    ]);
  });
});
