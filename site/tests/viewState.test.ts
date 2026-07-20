import { describe, expect, it } from 'vitest';
import { DEFAULT_VIEW, parseViewState, serializeViewState } from '../src/lib/viewState';
import type { ViewState } from '../src/lib/viewState';

describe('parseViewState', () => {
  it('returns defaults for an empty search string', () => {
    expect(parseViewState('')).toEqual(DEFAULT_VIEW);
    expect(parseViewState('?')).toEqual(DEFAULT_VIEW);
  });

  it('parses a fully specified state', () => {
    expect(parseViewState('?tab=pitchers&league=cape_cod&sort=era&dir=desc')).toEqual({
      tab: 'pitchers',
      league: 'cape_cod',
      sort: { key: 'era', dir: 'desc' },
    });
  });

  it('accepts search with or without a leading question mark', () => {
    expect(parseViewState('tab=pitchers')).toEqual(parseViewState('?tab=pitchers'));
  });

  it('falls back to the default tab on unknown tab values', () => {
    expect(parseViewState('?tab=bogus').tab).toBe('hitters');
    expect(parseViewState('?tab=').tab).toBe('hitters');
  });

  it('defaults dir to asc when missing or invalid', () => {
    expect(parseViewState('?sort=ops').sort).toEqual({ key: 'ops', dir: 'asc' });
    expect(parseViewState('?sort=ops&dir=sideways').sort).toEqual({ key: 'ops', dir: 'asc' });
  });

  it('ignores dir without a sort key', () => {
    expect(parseViewState('?dir=desc')).toEqual(DEFAULT_VIEW);
    expect(parseViewState('?sort=&dir=desc').sort).toBeNull();
  });

  it('ignores unknown params', () => {
    expect(parseViewState('?foo=bar&utm_source=x')).toEqual(DEFAULT_VIEW);
    expect(parseViewState('?foo=bar&tab=pitchers').tab).toBe('pitchers');
  });

  it('never throws on garbage input', () => {
    expect(() => parseViewState('?%%%&==&sort=%zz')).not.toThrow();
  });
});

describe('serializeViewState', () => {
  it('returns an empty string when everything is at its default', () => {
    expect(serializeViewState(DEFAULT_VIEW)).toBe('');
    expect(serializeViewState({ tab: 'hitters', league: '', sort: null })).toBe('');
  });

  it('omits params at their defaults', () => {
    expect(serializeViewState({ tab: 'hitters', league: 'cape_cod', sort: null })).toBe('league=cape_cod');
    expect(serializeViewState({ tab: 'pitchers', league: '', sort: null })).toBe('tab=pitchers');
    // asc is the default direction, so dir is omitted
    expect(serializeViewState({ tab: 'hitters', league: '', sort: { key: 'ops', dir: 'asc' } })).toBe('sort=ops');
  });

  it('serializes a fully non-default state', () => {
    expect(
      serializeViewState({ tab: 'pitchers', league: 'cape_cod', sort: { key: 'era', dir: 'desc' } }),
    ).toBe('tab=pitchers&league=cape_cod&sort=era&dir=desc');
  });
});

describe('round trips', () => {
  const states: ViewState[] = [
    { tab: 'hitters', league: '', sort: null },
    { tab: 'pitchers', league: '', sort: null },
    { tab: 'hitters', league: 'northwoods', sort: null },
    { tab: 'pitchers', league: 'cape_cod', sort: { key: 'era', dir: 'asc' } },
    { tab: 'hitters', league: 'appalachian', sort: { key: 'ops', dir: 'desc' } },
  ];

  it('parse(serialize(state)) preserves every state', () => {
    for (const state of states) {
      expect(parseViewState(serializeViewState(state))).toEqual(state);
    }
  });

  it('serialize(parse(url)) is stable (normalizing) for already-clean URLs', () => {
    for (const url of ['', 'tab=pitchers', 'league=cape_cod&sort=ops', 'tab=pitchers&sort=era&dir=desc']) {
      expect(serializeViewState(parseViewState(url))).toBe(url);
    }
  });
});
