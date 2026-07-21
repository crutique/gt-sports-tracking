import type { HitterGame, PitcherGame } from './data';

// Game logs carry AB/H/BB but not HBP/SF, so OBP here is (H+BB)/(AB+BB) —
// a close approximation, used only for trends and recency lines, never in
// place of the official season rates shown elsewhere.

export interface TrendPoint {
  date: string;
  value: number | null;
}

export interface RecentLine {
  games: number;
  ab: number;
  h: number;
  hr: number;
  ops: number | null;
}

export function gameOpsParts(g: HitterGame): { tb: number; ab: number; reached: number; pa: number } {
  const singles = g.h - g.d - g.t - g.hr;
  return {
    tb: singles + 2 * g.d + 3 * g.t + 4 * g.hr,
    ab: g.ab,
    reached: g.h + g.bb,
    pa: g.ab + g.bb,
  };
}

function chronological<T extends { date: string }>(games: T[]): T[] {
  return [...games].sort((a, b) => a.date.localeCompare(b.date));
}

function windowOps(games: HitterGame[]): number | null {
  const t = games.reduce(
    (acc, g) => {
      const p = gameOpsParts(g);
      acc.tb += p.tb; acc.ab += p.ab; acc.reached += p.reached; acc.pa += p.pa;
      return acc;
    },
    { tb: 0, ab: 0, reached: 0, pa: 0 },
  );
  if (t.pa === 0 || t.ab === 0) return null;
  return t.reached / t.pa + t.tb / t.ab;
}

/** Trailing-`window`-games OPS at each game of the log, oldest first. */
export function rollingOps(games: HitterGame[], window: number): TrendPoint[] {
  const chron = chronological(games);
  return chron.map((g, i) => ({
    date: g.date,
    value: windowOps(chron.slice(Math.max(0, i - window + 1), i + 1)),
  }));
}

/** Trailing-`window`-outings ERA at each outing of the log, oldest first. */
export function rollingEra(games: PitcherGame[], window: number): TrendPoint[] {
  const chron = chronological(games);
  return chron.map((_, i) => {
    const slice = chron.slice(Math.max(0, i - window + 1), i + 1);
    const outs = slice.reduce((s, g) => s + g.ip_outs, 0);
    const er = slice.reduce((s, g) => s + g.er, 0);
    return {
      date: chron[i].date,
      value: outs === 0 ? null : (er * 27) / outs,
    };
  });
}

function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);
}

/** Pooled hitting line over the last `days` days ending at `refDate` (inclusive). */
export function lastDaysLine(games: HitterGame[], days: number, refDate: string): RecentLine {
  const recent = games.filter((g) => {
    const d = daysBetween(g.date, refDate);
    return d >= 0 && d < days;
  });
  return {
    games: recent.length,
    ab: recent.reduce((s, g) => s + g.ab, 0),
    h: recent.reduce((s, g) => s + g.h, 0),
    hr: recent.reduce((s, g) => s + g.hr, 0),
    ops: windowOps(recent),
  };
}
