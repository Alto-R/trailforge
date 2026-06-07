import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { useRoute } from "./hooks/useRoute";
import type { LngLat, Prefs } from "./types";

vi.mock("./api", () => ({
  api: { route: vi.fn().mockResolvedValue({ candidates: [] }) },
}));

const PREFS: Prefs = {
  challenge: 0.2,
  nature: 0.2,
  culture: 0.2,
  popularity: 0.2,
  scenic: 0.2,
};
const START: LngLat = [116.1, 40.0];

describe("useRoute", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(api.route).mockClear();
  });
  afterEach(() => vi.useRealTimers());

  it("does not fire without a start point", () => {
    renderHook(() => useRoute(null, PREFS, 4));
    vi.advanceTimersByTime(1000);
    expect(api.route).not.toHaveBeenCalled();
  });

  it("debounces and fires exactly once for a stable start", () => {
    renderHook(() => useRoute(START, PREFS, 4));
    expect(api.route).not.toHaveBeenCalled(); // still inside the debounce window
    vi.advanceTimersByTime(300);
    expect(api.route).toHaveBeenCalledTimes(1);
  });

  it("resets the debounce when prefs change mid-window", () => {
    const { rerender } = renderHook(({ p }) => useRoute(START, p, 4), {
      initialProps: { p: PREFS },
    });
    vi.advanceTimersByTime(200);
    rerender({ p: { ...PREFS, challenge: 0.9 } }); // new input → timer restarts
    vi.advanceTimersByTime(200);
    expect(api.route).not.toHaveBeenCalled();
    vi.advanceTimersByTime(150);
    expect(api.route).toHaveBeenCalledTimes(1);
  });
});
