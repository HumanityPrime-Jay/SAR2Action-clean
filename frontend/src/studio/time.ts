const TAIWAN_OFFSET_MS = 8 * 60 * 60 * 1000;

export function formatTaiwanTime(value: unknown): string {
  if (typeof value !== 'string' || !Number.isFinite(Date.parse(value))) return 'unavailable';
  return new Date(value).toLocaleString('en-GB', {
    timeZone: 'Asia/Taipei', year: 'numeric', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }) + ' Taiwan time (UTC+8)';
}

export function taiwanSeasonDay(value: string): number {
  const local = new Date(Date.parse(value) + TAIWAN_OFFSET_MS);
  return Date.UTC(2025, local.getUTCMonth(), local.getUTCDate());
}
