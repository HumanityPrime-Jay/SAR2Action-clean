/**
 * Disaster events the app can open, grouped by region.
 *
 * Curated by hand for now. Later this list can be fed from 中央氣象署 typhoon warnings
 * plus 農業部 relief announcements (which counties qualify for cash relief).
 */
import type { Lang, Text } from '../i18n';

export type RegionKey = 'north' | 'central' | 'south';

export const REGIONS: { key: RegionKey; label: Text; counties: Text }[] = [
  {
    key: 'north',
    label: { zh: '北部', en: 'Northern' },
    counties: { zh: '基隆・台北・新北・桃園・新竹・宜蘭', en: 'Keelung, Taipei, New Taipei, Taoyuan, Hsinchu, Yilan' },
  },
  {
    key: 'central',
    label: { zh: '中部', en: 'Central' },
    counties: { zh: '苗栗・台中・彰化・南投・雲林', en: 'Miaoli, Taichung, Changhua, Nantou, Yunlin' },
  },
  {
    key: 'south',
    label: { zh: '南部', en: 'Southern' },
    counties: { zh: '嘉義・台南・高雄・屏東', en: 'Chiayi, Tainan, Kaohsiung, Pingtung' },
  },
];

export interface DisasterEvent {
  id: string;
  region: RegionKey;
  /** Chinese and international names, e.g. 薔琵颱風 / Typhoon CHAMPI. */
  name: Text;
  intlName: string;
  kind: Text;
  county: Text;
  town: Text;
  /** Period the storm circle was over Taiwan's land (CWA). */
  period: string;
  /** Whether NISAR scenes for this event are already processed. */
  hasImagery: boolean;
}

export const EVENTS: DisasterEvent[] = [
  {
    id: 'champi-2026-yunlin',
    region: 'central',
    name: { zh: '薔琵颱風', en: 'Typhoon Champi' },
    intlName: 'CHAMPI',
    kind: { zh: '颱風', en: 'Typhoon' },
    county: { zh: '雲林縣', en: 'Yunlin County' },
    town: { zh: '台西鄉', en: 'Taixi Township' },
    period: '2026-10-23 – 10-24',
    hasImagery: true,
  },
];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function eventLabel(e: DisasterEvent, lang: Lang) {
  const year = e.period.slice(0, 4);
  const month = Number(e.period.slice(5, 7));
  return lang === 'zh'
    ? `${e.county.zh} ${e.name.zh}（${e.intlName}，${year} 年 ${month} 月）`
    : `${e.name.en}, ${e.county.en} (${MONTHS[month - 1]} ${year})`;
}

/** Short label for the top bar, e.g. 薔琵颱風 · 雲林縣. */
export const eventShort = (e: DisasterEvent, lang: Lang) => `${e.name[lang]} · ${e.county[lang]}`;
