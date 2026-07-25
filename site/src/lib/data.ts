import collegeJson from '../data/college.json';
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

/**
 * Baseball-card color theme by roster status — gold = returning, navy =
 * incoming transfer, white = incoming recruit. Drives the Headshot frame so
 * a player's path onto (or off) the roster reads at a glance.
 */
export function cardTheme(
  gtStatus: Player['gtStatus'] | undefined,
): 'gold' | 'navy' | 'white' {
  if (gtStatus === 'transfer') return 'navy';
  if (gtStatus === 'freshman') return 'white';
  return 'gold';
}

export function getGamelog(slug: string): GameLogEntry[] {
  return gamelogModules[`../data/gamelogs/${slug}.json`] ?? [];
}

export interface CardRow { label: string; values: string[] }
export interface PlayerCardData {
  name: string;
  cutout: string | null;
  theme: 'gold' | 'navy' | 'white';
  posAbbr: string;
  classYear: string;
  height: string | null;
  weight: number | null;
  bats: string | null;
  throws: string | null;
  eyebrow: string;
  eyebrowSub: string | null;
  hometown: string | null;
  /** Second half of the foot line: HS for recruits/HS-developed players, the
      roster's "Last School" (a prior college) for players who arrived by
      transfer at some point. */
  originSchool: string | null;
  ranks: { k: string; v: string }[] | null;
  statLabel: string;
  cols: string[];
  rows: CardRow[];
  pending: string | null;
}

interface CollegeSeason {
  year: number;
  g: number;
  avg?: string; ops?: string; hr?: number; sb?: number;   // hitters
  ip?: string; era?: string; whip?: string; k?: number;   // pitchers
}
interface CollegeEntry {
  school: string;
  schoolNote?: string | null;   // e.g. "NJCAA" / "D-II" — competition context
  type: 'hitter' | 'pitcher' | null;
  seasons: CollegeSeason[];
  bats?: string | null;
  throws?: string | null;
  hometown?: string | null;
  lastSchool?: string | null;
}
const college = (collegeJson as unknown as { players: Record<string, CollegeEntry> }).players;

const HIT_CARD_COLS = ['G', 'AVG', 'OPS', 'HR', 'SB'];
const PIT_CARD_COLS = ['G', 'IP', 'ERA', 'WHIP', 'K'];

function collegeRows(entry: CollegeEntry): { cols: string[]; rows: CardRow[] } {
  if (!entry.seasons.length) return { cols: [], rows: [] };
  const pitcher = entry.type === 'pitcher';
  return {
    cols: pitcher ? PIT_CARD_COLS : HIT_CARD_COLS,
    rows: entry.seasons.map((s) => ({
      label: String(s.year),
      values: pitcher
        ? [String(s.g), s.ip ?? '—', s.era ?? '—', s.whip ?? '—', String(s.k ?? '—')]
        : [String(s.g), s.avg ?? '—', s.ops ?? '—', String(s.hr ?? '—'), String(s.sb ?? '—')],
    })),
  };
}

const CLASS_YEAR_FULL: Record<string, string> = {
  FR: 'Freshman', SO: 'Sophomore', JR: 'Junior', SR: 'Senior', GR: 'Graduate',
  'R-FR': 'Redshirt Freshman', 'R-SO': 'Redshirt Sophomore',
  'R-JR': 'Redshirt Junior', 'R-SR': 'Redshirt Senior',
};

/** Expand a coded class year (SO, R-JR) to its full display form for the card. */
export function classYearFull(cls: string | null | undefined): string {
  if (!cls) return '';
  return CLASS_YEAR_FULL[cls] ?? cls;
}

// Every current incoming freshman is the 2026 signing class (arriving for the
// 2027 season); a recruit is named by the year they signed. Promote this to
// per-player data once more than one recruiting class is on the board.
const RECRUIT_CLASS_YEAR = 2026;

/**
 * Derive trading-card props from a Player. Stat lines are prior seasons only —
 * college records from data/college.json (hand-backfilled from official
 * athletics sites; see its _provenance) — never the live summer line, per the
 * no-summer-stats-on-cards rule. Recruits show Perfect Game marks instead.
 * Missing data renders as a neutral empty state (no backend detail — see
 * memory: never-show-backend-plans-to-audience). The cutout mirrors the
 * headshot with its background removed; no headshot → initials monogram.
 */
export function mapPlayerToCard(p: Player): PlayerCardData {
  const base = {
    name: p.name,
    cutout: p.photo ? `/cutouts/${p.slug}.png` : null,
    theme: cardTheme(p.gtStatus),
    posAbbr: p.position || '—',
    classYear: classYearFull(p.classYear),
    height: p.height,
    weight: p.weight,
    statLabel: '',
    cols: [] as string[],
    rows: [] as CardRow[],
  };

  if (p.gtStatus === 'freshman') {
    const r = p.recruit ?? {};
    const bt = String(r.bats_throws ?? '').split('/');
    const ranks: { k: string; v: string }[] = [];
    if (r.pg_grade != null) ranks.push({ k: 'PG Grade', v: String(r.pg_grade) });
    if (r.pg_rank != null) ranks.push({ k: "Nat'l", v: `#${r.pg_rank}` });
    return {
      ...base,
      bats: bt[0]?.trim() || null,
      throws: bt[1]?.trim() || null,
      eyebrow: `${RECRUIT_CLASS_YEAR} Recruit`,
      eyebrowSub: null,
      hometown: r.hometown ? String(r.hometown) : null,
      originSchool: r.high_school ? String(r.high_school) : null,
      ranks: ranks.length ? ranks : null,
      pending: null, // senior-season HS stats aren't collected — show none
    };
  }

  const isTransfer = p.gtStatus === 'transfer';
  const c = college[p.slug];
  const table = c ? collegeRows(c) : { cols: [], rows: [] };
  return {
    ...base,
    ...table,
    bats: c?.bats ?? null,
    throws: c?.throws ?? null,
    eyebrow: isTransfer ? 'Transfer' : 'Returning',
    eyebrowSub: isTransfer ? (p.fromShort ?? p.fromSchool ?? null) : null,
    hometown: c?.hometown ?? null,
    originSchool: c?.lastSchool ?? null,
    ranks: null,
    statLabel: c && table.rows.length
      ? c.school + (c.schoolNote ? ` · ${c.schoolNote}` : '')
      : '',
    pending: table.rows.length ? null : 'No prior-season stats available',
  };
}
