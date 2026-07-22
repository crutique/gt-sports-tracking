import draftJson from '../data/draft.json';

export type DraftStatus = 'signed' | 'unsigned' | 'returning' | 'did_not_sign' | 'signed_udfa';

export interface DraftPlayer {
  name: string;
  personId: number | null;
  gtRole: 'departing' | 'signee';
  slug: string | null;
  round: string | null;
  pick: number | null;
  team: string | null;
  slot: number | null;
  bonus: number | null;
  bonusSource: 'official' | 'reported' | 'unverified' | null;
  reportedSourceUrl: string | null;
  unverifiedSourceUrl: string | null;
  status: DraftStatus;
  signedDate: string | null;
  headshot: string | null;
  note: string | null;
}

export interface DraftData {
  asOf: string | null;
  players: DraftPlayer[];
  udfa: DraftPlayer[];
}

export const STATUS_LABEL: Record<DraftStatus, string> = {
  signed: 'Signed',
  unsigned: 'Unsigned',
  returning: 'Returning to GT',
  did_not_sign: 'Did not sign',
  signed_udfa: 'Signed (UDFA)',
};

export function getDraft(): DraftData {
  return draftJson as unknown as DraftData;
}

export function fmtMoney(n: number | null): string {
  return n == null ? '—' : '$' + n.toLocaleString('en-US');
}

function compactMoney(n: number): string {
  if (n >= 1_000_000) return `$${trimZero((n / 1_000_000).toFixed(1))}M`;
  if (n >= 1_000) return `$${trimZero((n / 1_000).toFixed(1))}K`;
  return `$${n}`;
}

function trimZero(s: string): string {
  return s.endsWith('.0') ? s.slice(0, -2) : s;
}

/** Signed bonus vs. slot value, compact: '+$517.4K', '−$211.5K', 'slot', or '—'. */
export function fmtMoneyDelta(bonus: number | null, slot: number | null): string {
  if (bonus == null || slot == null) return '—';
  const d = bonus - slot;
  if (d === 0) return 'slot';
  return (d > 0 ? '+' : '−') + compactMoney(Math.abs(d));
}

export interface PoolSummary {
  slotPool: number;
  signedKnown: number;
  signedCount: number;
  unreportedCount: number;
  unsignedCount: number;
}

const SIGNED: DraftStatus[] = ['signed', 'signed_udfa'];

/** Money picture of the drafted class (excludes the separate UDFA list). */
export function poolSummary(players: DraftPlayer[]): PoolSummary {
  const signed = players.filter((p) => SIGNED.includes(p.status));
  return {
    slotPool: players.reduce((s, p) => s + (p.slot ?? 0), 0),
    signedKnown: signed.reduce((s, p) => s + (p.bonus ?? 0), 0),
    signedCount: signed.length,
    unreportedCount: signed.filter((p) => p.bonus == null).length,
    unsignedCount: players.filter((p) => p.status === 'unsigned').length,
  };
}

export function fmtMoneyCompact(n: number): string {
  return compactMoney(n);
}
