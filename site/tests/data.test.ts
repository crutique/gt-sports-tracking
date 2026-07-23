import { describe, expect, it } from 'vitest';
import {
  getAssignedPlayers, getGamelog, getLeagueByKey, getLeagues,
  getPlayer, getPlayers, getUnassignedPlayers, isSampleLeague, provenanceLabel,
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
