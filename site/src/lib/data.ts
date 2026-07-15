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

export function getGamelog(slug: string): GameLogEntry[] {
  return gamelogModules[`../data/gamelogs/${slug}.json`] ?? [];
}
