/**
 * Disaster events the app can open, grouped by region.
 *
 * Curated by hand for now. Later this list can be fed from 中央氣象署 typhoon warnings
 * plus 農業部 relief announcements (which counties qualify for cash relief).
 */

export type RegionKey = 'north' | 'central' | 'south';

export const REGIONS: { key: RegionKey; label: string; counties: string }[] = [
  { key: 'north', label: '北部', counties: '基隆・台北・新北・桃園・新竹・宜蘭' },
  { key: 'central', label: '中部', counties: '苗栗・台中・彰化・南投・雲林' },
  { key: 'south', label: '南部', counties: '嘉義・台南・高雄・屏東' },
];

export interface DisasterEvent {
  id: string;
  region: RegionKey;
  /** Chinese and international names, e.g. 薔琵 / CHAMPI. */
  name: string;
  intlName: string;
  kind: '颱風';
  county: string;
  town: string;
  /** Period the storm circle was over Taiwan's land (CWA). */
  period: string;
  /** Whether NISAR scenes for this event are already processed. */
  hasImagery: boolean;
}

export const EVENTS: DisasterEvent[] = [
  {
    id: 'champi-2026-yunlin',
    region: 'central',
    name: '薔琵颱風',
    intlName: 'CHAMPI',
    kind: '颱風',
    county: '雲林縣',
    town: '台西鄉',
    period: '2026-10-23 – 10-24',
    hasImagery: true,
  },
];

export const eventLabel = (e: DisasterEvent) => `${e.county} ${e.name}（${e.intlName}，${e.period.slice(0, 4)} 年 ${Number(e.period.slice(5, 7))} 月）`;
