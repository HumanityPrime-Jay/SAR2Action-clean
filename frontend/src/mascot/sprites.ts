/**
 * Hand-drawn pixel sprites of the site's two guides: a farmer (left) and a farmers'
 * association officer (right), holding hands. Each figure is 16 x 24 cells; a pose is the
 * base figure with arm and face layers drawn over it. "." is transparent.
 */

export const PALETTE: Record<string, string> = {
  K: '#1b1b22', // outline, eyes
  S: '#f3c7a1', // skin
  s: '#cf946c', // skin shade, closed eyes
  M: '#b5473e', // mouth
  H: '#ecc867', // bamboo hat
  h: '#c49a3c', // hat brim
  T: '#f7f5ee', // towel
  B: '#3a6db3', // farmer's work shirt
  b: '#284f86',
  P: '#a88b5c', // khaki trousers
  G: '#3f8f4b', // rubber boots
  R: '#26232a', // officer's hair
  W: '#f7f7f7', // polo shirt
  V: '#2f7d4f', // vest
  v: '#235f3b',
  L: '#d7322a', // lanyard
  Y: '#ffd34d', // ID badge
  N: '#2c3552', // trousers
  O: '#4a3a30', // shoes
  C: '#9b6b3a', // clipboard
  D: '#6ec3ff', // sweat drop
};

export const FIGURE_W = 16;
/** The officer stands 12 cells right of the farmer, so their inner hands meet in the gap. */
const OFFICER_X = 12;
export const SPRITE_W = OFFICER_X + FIGURE_W;
export const SPRITE_H = 24;

/** Rows of a layer by y; each row is FIGURE_W cells. */
type Layer = Record<number, string>;

const rows = (list: string[], from = 0): Layer => Object.fromEntries(list.map((r, i) => [from + i, r]));

const FARMER = rows([
  '......KKKK......',
  '....KKHHHHKK....',
  '..KKHHHHHHHHKK..',
  '.KhhhhhhhhhhhhK.',
  '..KKKKKKKKKKKK..',
  '....KSSSSSSK....',
  '....KSKSSKSK....',
  '....KSSSSSSK....',
  '....KSSMMSSK....',
  '.....KSSSSK.....',
  '....KTTTTTTK....',
  '....KBTBBTBK....',
  '....KBTBBTBK....',
  '....KBBBBBBK....',
  '....KBBBBBBK....',
  '....KbbbbbbK....',
  '....KPPPPPPK....',
  '....KPPPPPPK....',
  '....KPPKKPPK....',
  '....KPPKKPPK....',
  '....KPPKKPPK....',
  '....KGGKKGGK....',
  '...KGGGKKGGGK...',
  '...KKKKKKKKKK...',
]);

const OFFICER = rows([
  '................',
  '................',
  '.....KKKKKK.....',
  '....KRRRRRRK....',
  '....KRRRRRRK....',
  '....KRSSSSRK....',
  '....KSKSSKSK....',
  '....KSSSSSSK....',
  '....KSSMMSSK....',
  '.....KSSSSK.....',
  '....KWWLLWWK....',
  '....KVWLLWVK....',
  '....KVWWLWVK....',
  '....KVWWYWVK....',
  '....KVWWWWVK....',
  '....KvvvvvvK....',
  '....KNNNNNNK....',
  '....KNNNNNNK....',
  '....KNNKKNNK....',
  '....KNNKKNNK....',
  '....KNNKKNNK....',
  '....KOOKKOOK....',
  '...KOOOKKOOOK...',
  '...KKKKKKKKKK...',
]);

/** The inner hands meet across the two figures. */
const FARMER_HOLD = rows(['............BK..', '............BK..', '............BK..', '............SS..', '............KK..'], 11);
const OFFICER_HOLD = rows(['..KW............', '..KW............', '..KS............', '..SS............', '..KK............'], 11);

const FARMER_ARM = {
  down: rows(['..KB............', '.KBB............', '.KBB............', '.KBB............', '.KSS............', '..KK............'], 11),
  up: rows(
    [
      '.KSK............',
      '.KSK............',
      '.KBK............',
      '.KBK............',
      '.KBK............',
      '..KBK...........',
      '..KB............',
      '..KB............',
    ],
    4,
  ),
  upOut: rows(['KSK.............', 'KSK.............', '.KBK............', '.KBK............', '..KBK...........', '..KB............', '..KB............'], 5),
};

const OFFICER_ARM = {
  clipboard: rows(
    ['............WK..', '............WWK.', '............SSK.', '...........KCCCC', '...........KCWWC', '...........KCWWC', '...........KCCCC'],
    11,
  ),
  reading: rows(['............CCCC', '...........SCWWC', '...........SCWWC', '...........KCCCC', '............WK..', '............WK..'], 8),
  up: rows(
    [
      '............KSK.',
      '............KSK.',
      '...........KSK..',
      '...........KSK..',
      '...........KSK..',
      '...........KSK..',
      '...........KWK..',
      '...........KWK..',
      '............WK..',
    ],
    3,
  ),
};

/** Face rows, the same for both figures. */
const FACE = {
  blink: rows(['....KSsSSsSK....'], 6),
  smile: rows(['....KSMSSMSK....', '.....KSMMSK.....'], 8),
  worried: rows(['....KSSKKSSK....'], 8),
  readingEyes: rows(['....KSSSSSSK....', '....KSSKSKSK....'], 6),
};

const DROP_FARMER = rows(['............D...', '............D...'], 5);
const DROP_OFFICER = rows(['...D............', '...D............'], 4);

export type Mood = 'idle' | 'wave' | 'think' | 'happy' | 'sorry';

export interface Pose {
  farmerArm: keyof typeof FARMER_ARM;
  officerArm: keyof typeof OFFICER_ARM;
  farmerFace?: keyof typeof FACE;
  officerFace?: keyof typeof FACE;
  drops?: boolean;
}

/** Frames of each mood, played in a loop (one frame: a still pose). */
export const MOOD_FRAMES: Record<Mood, Pose[]> = {
  idle: [{ farmerArm: 'down', officerArm: 'clipboard' }],
  wave: [
    { farmerArm: 'up', officerArm: 'clipboard', farmerFace: 'smile', officerFace: 'smile' },
    { farmerArm: 'upOut', officerArm: 'clipboard', farmerFace: 'smile', officerFace: 'smile' },
  ],
  think: [{ farmerArm: 'down', officerArm: 'reading', officerFace: 'readingEyes' }],
  happy: [{ farmerArm: 'down', officerArm: 'clipboard', farmerFace: 'smile', officerFace: 'smile' }],
  sorry: [{ farmerArm: 'up', officerArm: 'up', farmerFace: 'worried', officerFace: 'worried', drops: true }],
};

/** The sprite as SPRITE_H rows of SPRITE_W palette keys. */
export function composePose(pose: Pose, blink = false): string[] {
  const grid = Array.from({ length: SPRITE_H }, () => Array<string>(SPRITE_W).fill('.'));
  const draw = (layer: Layer, dx: number) => {
    for (const [y, row] of Object.entries(layer)) {
      [...row].forEach((c, x) => {
        if (c !== '.') grid[Number(y)][dx + x] = c;
      });
    }
  };
  const figure = (base: Layer, inner: Layer, outer: Layer, face: keyof typeof FACE | undefined, dx: number) => {
    draw(base, dx);
    draw(inner, dx);
    draw(outer, dx);
    if (face) draw(FACE[face], dx);
    // Reading eyes already look down at the clipboard; a blink would undo them.
    if (blink && face !== 'readingEyes') draw(FACE.blink, dx);
  };
  figure(FARMER, FARMER_HOLD, FARMER_ARM[pose.farmerArm], pose.farmerFace, 0);
  figure(OFFICER, OFFICER_HOLD, OFFICER_ARM[pose.officerArm], pose.officerFace, OFFICER_X);
  if (pose.drops) {
    draw(DROP_FARMER, 0);
    draw(DROP_OFFICER, OFFICER_X);
  }
  return grid.map((r) => r.join(''));
}

/** One SVG path per colour, one unit square per cell. */
export function spritePaths(grid: string[]): { fill: string; d: string }[] {
  const byColour = new Map<string, string[]>();
  grid.forEach((row, y) =>
    [...row].forEach((c, x) => {
      if (c === '.') return;
      byColour.set(c, [...(byColour.get(c) ?? []), `M${x} ${y}h1v1h-1z`]);
    }),
  );
  return [...byColour].map(([c, cells]) => ({ fill: PALETTE[c], d: cells.join('') }));
}

/** Every layer row must be exactly one figure wide; checked by the tests. */
export const ALL_LAYERS: Layer[] = [
  FARMER,
  OFFICER,
  FARMER_HOLD,
  OFFICER_HOLD,
  ...Object.values(FARMER_ARM),
  ...Object.values(OFFICER_ARM),
  ...Object.values(FACE),
  DROP_FARMER,
  DROP_OFFICER,
];
