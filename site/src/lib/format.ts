const DASH = '—';

export function fmtRate3(v: number | null | undefined): string {
  if (v === null || v === undefined) return DASH;
  const s = v.toFixed(3);
  return s.startsWith('0.') ? s.slice(1) : s;
}

export function fmtEra(v: number | null | undefined): string {
  return v === null || v === undefined ? DASH : v.toFixed(2);
}

export function fmtPct(v: number | null | undefined): string {
  return v === null || v === undefined ? DASH : `${Math.round(v * 100)}%`;
}

export function fmtPer9(v: number | null | undefined): string {
  return v === null || v === undefined ? DASH : v.toFixed(1);
}

export function outsToIp(outs: number): string {
  return `${Math.floor(outs / 3)}.${outs % 3}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function fmtDate(iso: string): string {
  const [, m, d] = iso.split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}`;
}

/** Written-out class year for the card: SO → Sophomore, R-SO → Redshirt Sophomore. */
export function classFull(cls: string): string {
  const NAMES: Record<string, string> = {
    FR: 'Freshman', SO: 'Sophomore', JR: 'Junior', SR: 'Senior',
  };
  const redshirt = cls.startsWith('R-');
  const base = redshirt ? cls.slice(2) : cls;
  const name = NAMES[base];
  if (!name) return cls;
  return redshirt ? `Redshirt ${name}` : name;
}
