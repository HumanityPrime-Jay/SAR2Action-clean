/**
 * Small pixel props for the damage map's picker page: crops from the relief list, a rain cloud
 * and a raindrop. "." is transparent; an outline is added around every sprite by `outlined`.
 */

export const PROP_PALETTE: Record<string, string> = {
  K: '#1b1b22', // outline
  g: '#d9a62e', // rice grain
  y: '#f4d77a', // grain highlight
  e: '#5d9b3a', // stem
  E: '#3d6e2a', // stem shade
  w: '#f3eee2', // garlic skin
  p: '#b48bb5', // garlic stripe
  q: '#b9c6d8', // root, cloud shade
  n: '#d1a066', // peanut shell
  m: '#9b7240', // peanut shell grooves
  c: '#eef2f8', // cloud
  r: '#4f9ff0', // raindrop
  a: '#bfe2ff', // raindrop highlight
};

export const RICE = [
  '...g.....',
  '..gyg....',
  '..ygg.g..',
  '...gyggy.',
  '..g.gyg..',
  '...ggyg.g',
  '....gygy.',
  '.....ge..',
  '.....e...',
  '....Ee...',
  '....e....',
  '....e....',
  '...Ee....',
];

export const GARLIC = [
  '....e....',
  '....e....',
  '...wpw...',
  '..wwpww..',
  '.wwwpwww.',
  'wwwpwpwww',
  'wwwpwpwww',
  'wwwwpwwww',
  '.wwwwwww.',
  '..qwqwq..',
];

export const PEANUT = [
  '.nnn.',
  'nmnmn',
  'nnnnn',
  'nmnmn',
  '.nnn.',
  '..n..',
  '.nnn.',
  'nmnmn',
  'nnnnn',
  'nmnmn',
  '.nnn.',
];

export const CLOUD = [
  '.....cccc.......',
  '...cccccccc.....',
  '..cccccccccccc..',
  '.cccccccccccccc.',
  'cccccccccccccccc',
  'qqcccccccccccqqq',
  '.qqqqqqqqqqqqqq.',
];

export const DROP = ['.r.', '.r.', 'rar', 'rar', '.r.'];

/** The grid with a one-cell dark outline around every filled cell. */
export function outlined(grid: string[]): string[] {
  const h = grid.length + 2;
  const w = grid[0].length + 2;
  const at = (x: number, y: number) => grid[y - 1]?.[x - 1] ?? '.';
  return Array.from({ length: h }, (_, y) =>
    Array.from({ length: w }, (_, x) => {
      const c = at(x, y);
      if (c !== '.') return c;
      const near = [-1, 0, 1].some((dy) => [-1, 0, 1].some((dx) => (dx || dy) && at(x + dx, y + dy) !== '.'));
      return near ? 'K' : '.';
    }).join(''),
  );
}

/** One SVG path per colour, one unit square per cell. */
export function propPaths(grid: string[]): { fill: string; d: string }[] {
  const byColour = new Map<string, string[]>();
  grid.forEach((row, y) =>
    [...row].forEach((c, x) => {
      if (c !== '.') byColour.set(c, [...(byColour.get(c) ?? []), `M${x} ${y}h1v1h-1z`]);
    }),
  );
  return [...byColour].map(([c, cells]) => ({ fill: PROP_PALETTE[c], d: cells.join('') }));
}
