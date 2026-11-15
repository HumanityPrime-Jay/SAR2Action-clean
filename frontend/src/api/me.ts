/** What a signed-in user keeps (`/api/me/*`). Every call needs the session cookie; signed out they answer 401. */
import type { CropKey, FarmerInfo } from '../data/farmer';
import type { AuthorityReply } from './authorityAgent';
import type { TwAgroReliefEstimateResponse } from './tw05';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

interface SavedField {
  event_id: string;
  field_id: string | null;
  crop: CropKey;
  crop_other: string | null;
  cadastral: string | null;
}

const send = async (path: string, method: string, body?: unknown): Promise<Response> => {
  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp;
};

/** The farmer card saved for each disaster, keyed by event id. */
export async function fetchMyFields(): Promise<Record<string, FarmerInfo>> {
  const list: SavedField[] = await (await send('/api/me/fields', 'GET')).json();
  return Object.fromEntries(list.map((f) => [f.event_id, { crop: f.crop, cropOther: f.crop_other ?? '', cadastral: f.cadastral ?? '' }]));
}

export const saveMyField = (eventId: string, info: FarmerInfo) =>
  send(`/api/me/fields/${encodeURIComponent(eventId)}`, 'PUT', {
    crop: info.crop,
    crop_other: info.crop === 'other' ? info.cropOther : null,
    cadastral: info.cadastral || null,
  });

export const deleteMyField = (eventId: string) => send(`/api/me/fields/${encodeURIComponent(eventId)}`, 'DELETE');

export const logAnswer = (entry: { field_id: string; view: 'farmer' | 'authority'; lang: 'zh' | 'en'; question: string; reply: AuthorityReply }) =>
  send('/api/me/assistant-log', 'POST', entry);

/** The server recomputes the estimate from the official schedule before keeping it. */
export const saveEstimate = async (req: { field_id: string; crop_item_id: string; area_ha: number; loss_threshold: 'meets_20_percent' }) =>
  (await send('/api/me/estimates', 'POST', req)).json() as Promise<TwAgroReliefEstimateResponse>;
