/**
 * The two NISAR L2 GCOV granules around 薔琵颱風 (CHAMPI), and the full-frame overview in
 * `public/nisar/` rendered from the post-event one for the home globe.
 *
 * Same track and frame, but different processing versions (P05023 provisional, P05036
 * validated): the team's QA does not allow comparing their values directly.
 */

const BASE = `${import.meta.env.BASE_URL}nisar`;

export const NISAR_SCENE = {
  mission: 'NISAR L2 GCOV',
  track: 61,
  frame: 76,
  pass: 'Descending',
  preDate: '2026-10-16',
  postDate: '2026-10-28',
};

export const NISAR_IMG = {
  /** Full frame, false color (R=HH, G=HV, B=HH/HV), transparent outside the swath. */
  frame: `${BASE}/frame-post.webp`,
};

/** Full-frame image corners (TL, TR, BR, BL) as [lng, lat], for a map image source. */
export const NISAR_FRAME_CORNERS: [[number, number], [number, number], [number, number], [number, number]] = [
  [118.680714, 26.259605],
  [122.166777, 26.322251],
  [122.187144, 23.234573],
  [118.785924, 23.180175],
];
