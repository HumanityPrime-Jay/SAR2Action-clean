/**
 * Illustrative (示意) values that still have no verified source: the relief rate.
 * Replace with the announcement data.
 */
import type { Text } from '../i18n';

/** Illustrative relief rate, NT$ per hectare. Real rates come from each relief announcement. */
export const RELIEF_RATE_PER_HA = 26_000;

/** Questions the relief agent understands; the agent is sent the Chinese text in either language. */
export const SUGGESTED_QUESTIONS: { key: 'relief' | 'docs' | 'deadline'; text: Text }[] = [
  { key: 'relief', text: { zh: '我可以申請救助嗎？', en: 'Can I apply for relief?' } },
  { key: 'docs', text: { zh: '申請需要哪些文件？', en: 'What documents do I need?' } },
  { key: 'deadline', text: { zh: '申請期限是什麼時候？', en: 'When is the deadline?' } },
];

/** Signed dB with a real minus sign, e.g. "+0.51 dB", "−3.51 dB". */
export function formatDb(db: number): string {
  return `${db > 0 ? '+' : ''}${db.toFixed(2).replace('-', '−')} dB`;
}
