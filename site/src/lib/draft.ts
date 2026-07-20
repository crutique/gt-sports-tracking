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
