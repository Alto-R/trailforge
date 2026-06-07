// Candidate route colours. Colour-blind-friendly qualitative palette
// (ColorBrewer Set2-ish), avoiding pure red/green clashes. Assigned by the
// candidate's order in the response (score desc), so "route 1 is always orange".
export const CANDIDATE_COLORS: [number, number, number][] = [
  [230, 126, 34], // orange
  [52, 152, 219], // blue
  [39, 174, 96], // green
  [155, 89, 182], // purple
  [149, 117, 89], // brown
  [241, 196, 15], // yellow
  [26, 188, 156], // teal
  [231, 76, 60], // red (only if 8 routes)
];

export function candidateColor(i: number): [number, number, number] {
  return CANDIDATE_COLORS[i % CANDIDATE_COLORS.length];
}

/** CSS rgb() string for a candidate index (for list dots / chips). */
export function candidateCss(i: number, alpha = 1): string {
  const [r, g, b] = candidateColor(i);
  return alpha >= 1 ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${alpha})`;
}

/** Faint grey for the background trail network. */
export const TRAIL_COLOR: [number, number, number] = [200, 204, 208];
