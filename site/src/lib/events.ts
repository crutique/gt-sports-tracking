import type { HitterGame, PitcherGame } from './data';
import { outsToIp } from './format';

// Notable-game detection for the season-narrative chart. Thresholds are
// deliberately high — an annotation layer only works when it stays sparse.

export interface GameEvent {
  date: string;
  label: string;
}

const HIT_STREAK_MIN = 5;

function chronological<T extends { date: string }>(games: T[]): T[] {
  return [...games].sort((a, b) => a.date.localeCompare(b.date));
}

export function detectHitterEvents(games: HitterGame[]): GameEvent[] {
  const chron = chronological(games);
  const byDate = new Map<string, string[]>();

  for (const g of chron) {
    const feats: string[] = [];
    if (g.hr >= 2) feats.push(`${g.hr} HR`);
    if (g.h >= 4) feats.push('4-hit game');
    if (g.sb >= 3) feats.push(`${g.sb} SB`);
    if (feats.length) byDate.set(g.date, feats);
  }

  // Hit streaks: annotate once, at the game that ends the streak.
  let run = 0;
  for (let i = 0; i <= chron.length; i++) {
    const hit = i < chron.length && chron[i].h >= 1 && chron[i].ab > 0;
    if (hit) {
      run++;
    } else {
      if (run >= HIT_STREAK_MIN) {
        const end = chron[i - 1].date;
        byDate.set(end, [...(byDate.get(end) ?? []), `${run}-game hit streak`]);
      }
      run = 0;
    }
  }

  return [...byDate.entries()]
    .map(([date, feats]) => ({ date, label: feats.join(' · ') }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function detectPitcherEvents(games: PitcherGame[]): GameEvent[] {
  return chronological(games)
    .map((g) => {
      const feats: string[] = [];
      if (g.k >= 8) feats.push(`${g.k} K`);
      if (g.er === 0 && g.ip_outs >= 12) feats.push(`${outsToIp(g.ip_outs)} scoreless IP`);
      return feats.length ? { date: g.date, label: feats.join(' · ') } : null;
    })
    .filter((e): e is GameEvent => e !== null);
}
