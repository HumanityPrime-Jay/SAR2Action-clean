/** What a farmer tells us about their own field (crop identification: farmer input). */
import type { Text } from '../i18n';

export type CropKey = 'rice' | 'garlic' | 'peanut' | 'corn' | 'sweet_potato' | 'vegetables' | 'other';

export const CROPS: { key: CropKey; label: Text }[] = [
  { key: 'rice', label: { zh: '水稻', en: 'Rice' } },
  { key: 'garlic', label: { zh: '大蒜', en: 'Garlic' } },
  { key: 'peanut', label: { zh: '落花生', en: 'Peanut' } },
  { key: 'corn', label: { zh: '玉米', en: 'Corn' } },
  { key: 'sweet_potato', label: { zh: '甘藷', en: 'Sweet potato' } },
  { key: 'vegetables', label: { zh: '蔬菜', en: 'Vegetables' } },
  { key: 'other', label: { zh: '其他', en: 'Other' } },
];

export interface FarmerInfo {
  /** Land parcel number (地籍地號), optional. */
  cadastral: string;
  crop: CropKey;
  /** Free text when crop is "other". */
  cropOther: string;
}

/** Display name of the farmer's crop, e.g. "大蒜" or the free-text "other" crop. */
export function cropName(info: FarmerInfo, lang: 'zh' | 'en'): string {
  if (info.crop === 'other' && info.cropOther.trim()) return info.cropOther.trim();
  return CROPS.find((c) => c.key === info.crop)!.label[lang];
}
