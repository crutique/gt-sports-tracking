import leaguesJson from '../data/leagues.json';
import playersJson from '../data/players.json';

export interface Slider {
  metric: string;
  value: number;
  percentile: number;
  leagueAvg: number | null;
  leagueAvgPercentile: number | null;
  derived: boolean;
}

export interface StatBlock {
  counting: Record<string, number | string>;
  rates: Record<string, number | null>;
  /** Meets the summer qualifying bar (2.0 PA / 0.5 IP per team game); false =
      small sample, shown with hatched percentile bars. Absent on older data. */
  qualified?: boolean;
  sliders: Slider[] | null;
}

export interface PlayerSummer {
  status: 'assigned' | 'unassigned' | 'not_playing';
  team?: string;
  leagueKey?: string;
}

export interface Player {
  slug: string;
  name: string;
  gtStatus: 'returning' | 'transfer' | 'freshman';
  /** Transfer origin school (full name), null for non-transfers. */
  fromSchool: string | null;
  /** Short display form of fromSchool for tags (e.g. "Jax State"). */
  fromShort: string | null;
  /** Listed height/weight from an official roster (null when unsourced). */
  height: string | null;
  weight: number | null;
  position: string;
  classYear: string;
  playerType: 'hitter' | 'pitcher' | 'two_way' | null;
  summer: PlayerSummer;
  photo: string | null;
  asOf: string | null;
  hitting: StatBlock | null;
  pitching: StatBlock | null;
  recruit: Record<string, string | number> | null;
  note: string | null;
}

export interface League {
  key: string;
  name: string;
  abbrev: string;
  officialUrl: string;
  platform: string;
  tier: number | null;
  gtPlayers: string[];
}

export interface PitcherGame {
  date: string; opponent: string; ip_outs: number;
  h: number; r: number; er: number; bb: number; k: number; hr: number; dec: string;
}

export interface HitterGame {
  date: string; opponent: string; ab: number; r: number; h: number; d: number;
  t: number; hr: number; rbi: number; bb: number; k: number; sb: number;
}

export type GameLogEntry = PitcherGame | HitterGame;

const players = playersJson as unknown as Player[];
const leagues = leaguesJson as unknown as League[];

const gamelogModules = import.meta.glob<GameLogEntry[]>('../data/gamelogs/*.json', {
  eager: true,
  import: 'default',
});

export function getPlayers(): Player[] {
  return players;
}

export function getPlayer(slug: string): Player | undefined {
  return players.find((p) => p.slug === slug);
}

export function getAssignedPlayers(): Player[] {
  return players.filter((p) => p.summer.status === 'assigned');
}

export function getUnassignedPlayers(): Player[] {
  return players.filter((p) => p.summer.status !== 'assigned');
}

export function getLeagues(): League[] {
  return leagues;
}

export function getLeagueByKey(key: string | undefined): League | undefined {
  return leagues.find((l) => l.key === key);
}

export function isSampleLeague(key: string | undefined): boolean {
  return getLeagueByKey(key)?.platform === 'fixture';
}

/**
 * Players whose stats may be DISPLAYED: assigned, has a stat block, and the
 * league feed is real. Fixture-league stats exist in the data files but must
 * never render (hard product rule: no fake data, ever).
 */
export function getDisplayablePlayers(): Player[] {
  return getAssignedPlayers().filter(
    (p) => (p.hitting || p.pitching) && !isSampleLeague(p.summer.leagueKey),
  );
}

/**
 * One-line provenance for an incoming player — spoken by the + arrival
 * badge's tooltip. Null for returning players (the unmarked default).
 */
export function provenanceLabel(
  p: Pick<Player, 'gtStatus' | 'fromSchool' | 'recruit'>,
): string | null {
  if (p.gtStatus === 'transfer') {
    return `Incoming transfer from ${p.fromSchool ?? 'another school'}`;
  }
  if (p.gtStatus === 'freshman') {
    const hs = p.recruit?.high_school;
    return `Incoming freshman${hs ? ` · ${String(hs)} HS` : ''}`;
  }
  return null;
}

export function getGamelog(slug: string): GameLogEntry[] {
  return gamelogModules[`../data/gamelogs/${slug}.json`] ?? [];
}
