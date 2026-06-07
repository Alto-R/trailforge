import { describe, expect, it } from "vitest";
import { candidateColor, candidateCss, CANDIDATE_COLORS } from "./palette";

describe("palette", () => {
  it("assigns colours by index so route 1 is always orange", () => {
    expect(candidateColor(0)).toEqual([230, 126, 34]);
    expect(candidateColor(1)).toEqual([52, 152, 219]);
  });

  it("wraps around past the palette length", () => {
    const n = CANDIDATE_COLORS.length;
    expect(candidateColor(n)).toEqual(candidateColor(0));
    expect(candidateColor(n + 1)).toEqual(candidateColor(1));
  });

  it("emits rgb() when opaque and rgba() when translucent", () => {
    expect(candidateCss(0)).toBe("rgb(230,126,34)");
    expect(candidateCss(0, 0.35)).toBe("rgba(230,126,34,0.35)");
  });
});
