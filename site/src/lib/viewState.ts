import type { SortDir } from './tableSort';

export type Tab = 'hitters' | 'pitchers';

export interface ViewState {
  tab: Tab;
  league: string;
  sort: { key: string; dir: SortDir } | null;
}

export const DEFAULT_VIEW: ViewState = Object.freeze({ tab: 'hitters', league: '', sort: null });

/**
 * Parse a query string (with or without leading "?") into a dashboard view state.
 * Unknown params and invalid values fall back to defaults; never throws.
 * Callers must still validate `league` / `sort.key` against what actually exists.
 */
export function parseViewState(search: string): ViewState {
  const params = new URLSearchParams(search);
  const tab: Tab = params.get('tab') === 'pitchers' ? 'pitchers' : 'hitters';
  const league = params.get('league') ?? '';
  const key = params.get('sort') ?? '';
  const dir: SortDir = params.get('dir') === 'desc' ? 'desc' : 'asc';
  return { tab, league, sort: key ? { key, dir } : null };
}

/** Serialize a view state to a query string, omitting params at their defaults ("" when all default). */
export function serializeViewState(state: ViewState): string {
  const params = new URLSearchParams();
  if (state.tab !== 'hitters') params.set('tab', state.tab);
  if (state.league) params.set('league', state.league);
  if (state.sort) {
    params.set('sort', state.sort.key);
    if (state.sort.dir !== 'asc') params.set('dir', state.sort.dir);
  }
  return params.toString();
}
