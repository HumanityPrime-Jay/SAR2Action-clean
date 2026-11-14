/**
 * Illustrative (示意) values that still have no verified source: the relief rate and the
 * assistant's canned replies. Replace with the announcement data and the agent API.
 */
import type { Parcel } from '../data/champi';

/** Illustrative relief rate, NT$ per hectare. Real rates come from each relief announcement. */
export const RELIEF_RATE_PER_HA = 26_000;

export const SUGGESTED_QUESTIONS = ['申請需要哪些文件？', '申請期限是什麼時候？', '幫我寫給農民的說明'];

export function cannedReply(question: string, parcel: Parcel): string {
  switch (question) {
    case '申請需要哪些文件？':
      return `通常需要：申請書、身分證明、土地與耕作證明、存摺影本。[3]\n本系統可以附上田區 ${parcel.id} 的雷達觀測紀錄，作為勘查參考。`;
    case '申請期限是什麼時候？':
      return '期限依縣府公告為準，通常在公告後一段固定天數內。[3]\n建議以縣府最新公告確認，並提醒農民提早準備。';
    case '幫我寫給農民的說明':
      return `您好，衛星雷達在薔琵颱風前後觀測到您的田區 ${parcel.id} 回波有變化，但還不能確定是否受損。農會將安排現場勘查，請準備土地與耕作證明，以便確認是否符合救助資格。[1]`;
    default:
      return '（示意）這裡會顯示助手依法規檢索後的回答，並附上引用來源。[3]';
  }
}

/** Signed dB with a real minus sign, e.g. "+0.51 dB", "−3.51 dB". */
export function formatDb(db: number): string {
  return `${db > 0 ? '+' : ''}${db.toFixed(2).replace('-', '−')} dB`;
}
