import { describe, expect, it } from 'vitest';
import {
  gameOpsParts,
  hitterGameScore,
  lastDaysLine,
  pitcherGameScore,
  rollingEra,
  rollingOps,
} from '../src/lib/stats';
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

describe('gameOpsParts', () => {
  it('computes total bases and reach/plate-appearance parts', () => {
    // 2 H: one single, one HR → TB = 1 + 4 = 5
    const g = hg({ ab: 4, h: 2, hr: 1, bb: 1 });
    expect(gameOpsParts(g)).toEqual({ tb: 5, ab: 4, reached: 3, pa: 5 });
  });
});

describe('rollingOps', () => {
  it('returns chronological points even when the log is newest-first', () => {
    const games = [
      hg({ date: '2026-07-03', h: 4, ab: 4 }),
      hg({ date: '2026-07-02', h: 0, ab: 4 }),
      hg({ date: '2026-07-01', h: 2, ab: 4 }),
    ];
    const pts = rollingOps(games, 10);
    expect(pts.map((p) => p.date)).toEqual(['2026-07-01', '2026-07-02', '2026-07-03']);
  });

  it('computes trailing-window OPS (window smaller than log)', () => {
    const games = [
      hg({ date: '2026-07-01', h: 0, ab: 4 }),
      hg({ date: '2026-07-02', h: 0, ab: 4 }),
      hg({ date: '2026-07-03', h: 4, ab: 4, hr: 4 }),
    ];
    // window 1 → last point covers only Jul 3: OBP 1.000 + SLG 4.000 = 5.000
    const pts = rollingOps(games, 1);
    expect(pts[2].value).toBeCloseTo(5.0, 3);
    // window 10 → all games pooled: OBP 4/12, SLG 16/12 → 1.667
    const all = rollingOps(games, 10);
    expect(all[2].value).toBeCloseTo(4 / 12 + 16 / 12, 3);
  });

  it('skips zero-PA windows', () => {
    const pts = rollingOps([hg({ ab: 0, h: 0, bb: 0 })], 5);
    expect(pts[0].value).toBeNull();
  });
});

describe('rollingEra', () => {
  it('computes trailing-window ERA in chronological order', () => {
    const games = [
      pg({ date: '2026-07-08', ip_outs: 9, er: 0 }),
      pg({ date: '2026-07-01', ip_outs: 9, er: 3 }),
    ];
    // window 5 pools both: 3 ER over 6 IP → 4.50
    const pts = rollingEra(games, 5);
    expect(pts.map((p) => p.date)).toEqual(['2026-07-01', '2026-07-08']);
    expect(pts[1].value).toBeCloseTo(4.5, 2);
  });
});

describe('game scores (star-of-the-night ordering)', () => {
  it('a homer-and-steals night outranks a two-hit night', () => {
    expect(hitterGameScore(hg({ hr: 1, sb: 3, h: 2, rbi: 2, bb: 2 })))
      .toBeGreaterThan(hitterGameScore(hg({ h: 2 })));
  });
  it('a long scoreless outing outranks a mediocre one', () => {
    expect(pitcherGameScore(pg({ er: 0, ip_outs: 18, k: 6 })))
      .toBeGreaterThan(pitcherGameScore(pg({ er: 3, ip_outs: 15, k: 7 })));
  });
});

describe('lastDaysLine', () => {
  const games = [
    hg({ date: '2026-07-19', h: 2, ab: 3, hr: 1, bb: 2 }),
    hg({ date: '2026-07-15', h: 1, ab: 4 }),
    hg({ date: '2026-07-05', h: 0, ab: 4 }),
  ];

  it('pools only games within the window of the reference date', () => {
    const line = lastDaysLine(games, 7, '2026-07-19');
    expect(line.games).toBe(2);
    expect(line.ab).toBe(7);
    expect(line.h).toBe(3);
    expect(line.hr).toBe(1);
    // OBP (3+2)/(7+2) + SLG 6/7
    expect(line.ops).toBeCloseTo(5 / 9 + 6 / 7, 3);
  });

  it('returns zeros when nothing falls in the window', () => {
    const line = lastDaysLine(games, 7, '2026-08-30');
    expect(line.games).toBe(0);
    expect(line.ops).toBeNull();
  });
});
