import { describe, expect, it } from 'vitest';
import {
  classYearFull, getAssignedPlayers, getGamelog, getLeagueByKey, getLeagues,
  getPlayer, getPlayers, getUnassignedPlayers, isSampleLeague, mapPlayerToCard,
  provenanceLabel,
} from '../src/lib/data';

describe('data access', () => {
  it('loads all 40 players', () => {
    expect(getPlayers()).toHaveLength(40);
  });

  it('finds a player by slug, undefined for unknown', () => {
    expect(getPlayer('jackson-blakely')?.name).toBe('Jackson Blakely');
    expect(getPlayer('nobody')).toBeUndefined();
  });

  it('splits assigned and unassigned', () => {
    const assigned = getAssignedPlayers();
    expect(assigned).toHaveLength(21);
    const slugs = assigned.map((p) => p.slug);
    expect(slugs).toContain('coleman-lewis');
    expect(slugs).toContain('jordan-lodise');
    expect(slugs).toContain('jackson-blakely');
    expect(slugs).toContain('nathanael-coupet');
    expect(slugs).toContain('kolby-martin');
    expect(slugs).toContain('isaiah-galason');
    expect(getUnassignedPlayers()).toHaveLength(19);
  });

  it('exposes sliders with leagueAvgPercentile', () => {
    const jb = getPlayer('riley-hasenstab')!;
    const sliders = jb.pitching!.sliders!;
    expect(sliders).toHaveLength(6);
    expect(sliders[0]).toHaveProperty('leagueAvgPercentile');
  });

  it('loads leagues sorted by player count', () => {
    const leagues = getLeagues();
    expect(leagues[0].key).toBe('cape_cod');
    expect(getLeagueByKey('northwoods')?.abbrev).toBe('NWL');
    expect(getLeagueByKey('nope')).toBeUndefined();
  });

  it('no leagues are sample data after cutover', () => {
    expect(isSampleLeague('northwoods')).toBe(false);
    expect(isSampleLeague('mlb_draft')).toBe(false);
  });

  it('treats an absent note field as null, string when present', () => {
    for (const p of getPlayers()) {
      expect(p.note == null || typeof p.note === 'string').toBe(true);
    }
    expect(typeof getPlayer('jackson-blakely')!.note).toBe('string');
    expect(getPlayer('coleman-lewis')!.note ?? null).toBeNull();
  });

  it('loads gamelogs by slug, empty for missing', () => {
    expect(getGamelog('riley-hasenstab').length).toBeGreaterThanOrEqual(2);
    expect(getGamelog('jackson-blakely')).toEqual([]);
    expect(getGamelog('will-baker')).toEqual([]);
  });
});

describe('provenanceLabel', () => {
  const base = { fromSchool: null, recruit: null } as any;
  it('describes a transfer with his origin school', () => {
    expect(provenanceLabel({ ...base, gtStatus: 'transfer', fromSchool: 'Jacksonville State' }))
      .toBe('Incoming transfer from Jacksonville State');
  });
  it('describes a freshman with his high school when known', () => {
    expect(provenanceLabel({ ...base, gtStatus: 'freshman', recruit: { high_school: 'Etowah' } }))
      .toBe('Incoming freshman · Etowah HS');
    expect(provenanceLabel({ ...base, gtStatus: 'freshman' })).toBe('Incoming freshman');
  });
  it('is null for returning players', () => {
    expect(provenanceLabel({ ...base, gtStatus: 'returning' })).toBeNull();
  });
});

describe('mapPlayerToCard', () => {
  it('expands coded class years', () => {
    expect(classYearFull('SO')).toBe('Sophomore');
    expect(classYearFull('R-JR')).toBe('Redshirt Junior');
    expect(classYearFull('FR')).toBe('Freshman');
    expect(classYearFull(null)).toBe('');
  });

  it('returning hitter carries his GT seasons — never the summer line', () => {
    const card = mapPlayerToCard(getPlayer('coleman-lewis')!);
    expect(card.theme).toBe('gold');
    expect(card.eyebrow).toBe('Returning');
    expect(card.statLabel).toBe('Georgia Tech');
    expect(card.cols).toEqual(['G', 'AVG', 'OPS', 'HR', 'SB']);
    expect(card.rows).toEqual([
      { label: '2026', values: ['14', '.240', '.705', '1', '0'] },
    ]);
    // bio from the official GT roster page
    expect(card.bats).toBe('L');
    expect(card.throws).toBe('R');
    expect(card.hometown).toBe('Lake Park, Ga.');
    expect(card.originSchool).toBe('Lowndes HS');
    // his summer numbers (.336 AVG, 9 HR at Green Bay) must not leak onto the card
    const flat = card.rows.flatMap((r) => r.values).join(' ');
    expect(flat).not.toContain('.336');
    expect(card.pending).toBeNull();
  });

  it('returning pitcher gets pitcher columns, seasons newest first', () => {
    const card = mapPlayerToCard(getPlayer('jackson-blakely')!);
    expect(card.cols).toEqual(['G', 'IP', 'ERA', 'WHIP', 'K']);
    expect(card.rows[0]).toEqual({ label: '2026', values: ['15', '64.1', '3.36', '1.26', '69'] });
    expect(card.rows[1].label).toBe('2025');
  });

  it('redshirt with no college record keeps a neutral empty state', () => {
    const card = mapPlayerToCard(getPlayer('riley-hasenstab')!);
    expect(card.rows).toEqual([]);
    expect(card.pending).toBe('No prior-season stats available');
    // audience-facing copy never names backend systems or plans
    expect(card.pending).not.toMatch(/feed|NCAA|coming|pipeline/i);
    expect(card.statLabel).toBe('');
  });

  it('recruit shows PG marks and hometown · HS, no stat table', () => {
    const card = mapPlayerToCard(getPlayer('deion-cole')!);
    expect(card.theme).toBe('white');
    expect(card.eyebrow).toBe('2026 Recruit');
    expect(card.ranks).toEqual([
      { k: 'PG Grade', v: '10' },
      { k: "Nat'l", v: '#143' },
      { k: 'OF Rank', v: '#23' },
    ]);
    expect(card.hometown).toBe('Acworth, GA');
    expect(card.originSchool).toBe('Etowah');
    expect(card.rows).toEqual([]);
    expect(card.bats).toBe('R');
    expect(card.throws).toBe('R');
  });
});
