/** Farmer relief agent (`POST /api/farmer/chat`): rule-based answers from the relief regulations, phrased or translated by Gemini when configured. */
import type { Text } from '../i18n';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface FarmerChatRequest {
  session_id: string;
  message: string;
  selected_field_id?: string;
  optional_event_id?: string;
  crop?: string;
  /** "en": the agent translates the question in and the reply out, when Gemini is available. */
  lang?: 'zh' | 'en';
}

export interface FarmerChatReply {
  reply: string;
  intent: string;
  conversation_state: string;
  /** Source ids, e.g. "M0090019-ARTICLE-12-1" (農業天然災害救助辦法 第 12-1 條). */
  sources: string[];
  result_cards: { card_type: string; title: string; sources: string[]; limitations: string[] }[];
  /** Language the reply is actually in; "zh" when an English translation was not possible. */
  reply_language?: 'zh' | 'en';
}

export class AgentUnavailableError extends Error {}

export async function farmerChat(req: FarmerChatRequest, signal?: AbortSignal): Promise<FarmerChatReply> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/api/farmer/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new AgentUnavailableError('network');
  }
  if (!resp.ok) throw new AgentUnavailableError(`HTTP ${resp.status}`);
  const body = (await resp.json()) as FarmerChatReply;
  if (typeof body?.reply !== 'string' || !body.reply.trim()) throw new AgentUnavailableError('empty reply');
  return body;
}

/** Pcode of 農業天然災害救助辦法 in the national law database. */
const RELIEF_LAW = 'M0090019';

export interface SourceInfo {
  title: Text;
  url?: string;
}

/** Non-law sources the agent cites: data products and calculation methods. */
const OTHER_SOURCES: Record<string, SourceInfo> = {
  'OPERA_L2_RTC-S1': { title: { zh: 'Sentinel-1 雷達影像（NASA OPERA RTC）', en: 'Sentinel-1 radar (NASA OPERA RTC)' } },
  WGS84_GEODESIC_SPHERICAL_EXCESS: { title: { zh: '面積計算：WGS84 橢球面積', en: 'Area method: WGS84 geodesic area' } },
};

/** Human label for a backend source id; unknown ids are shown as they are. */
export function describeSource(id: string): SourceInfo {
  const m = new RegExp(`^${RELIEF_LAW}-ARTICLE-([\\d-]+)$`).exec(id);
  if (m) {
    return {
      title: { zh: `農業天然災害救助辦法 第 ${m[1]} 條`, en: `Agricultural Natural Disaster Relief Regulations, Art. ${m[1]}` },
      url: `https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode=${RELIEF_LAW}&flno=${m[1]}`,
    };
  }
  return OTHER_SOURCES[id] ?? { title: { zh: id, en: id } };
}

/** Sources of the reply and its result cards, without duplicates. */
export function replySources(r: FarmerChatReply): string[] {
  return [...new Set([...r.sources, ...r.result_cards.flatMap((c) => c.sources)])];
}
