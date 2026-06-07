// useRoute: owns the request to POST /route. Debounces input changes (~300ms),
// only fires when a start point is set, and uses an incrementing request id +
// AbortController so only the latest response is applied (race-safe).

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { LngLat, Prefs, RouteResponse } from "../types";

const DEBOUNCE_MS = 300;
const N_ROUTES = 4;

export type RouteState = {
  data: RouteResponse | null;
  loading: boolean;
  error: string | null;
};

export function useRoute(
  start: LngLat | null,
  prefs: Prefs,
  budgetKm: number,
): RouteState {
  const [state, setState] = useState<RouteState>({
    data: null,
    loading: false,
    error: null,
  });

  const reqId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(
    (s: LngLat, p: Prefs, b: number) => {
      const id = ++reqId.current;
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      setState((prev) => ({ ...prev, loading: true, error: null }));
      api
        .route(
          { start: s, preferences: p, budget_km: b, n_routes: N_ROUTES },
          ac.signal,
        )
        .then((data) => {
          if (id === reqId.current) setState({ data, loading: false, error: null });
        })
        .catch((err: unknown) => {
          if (ac.signal.aborted || id !== reqId.current) return; // superseded
          setState((prev) => ({
            ...prev,
            loading: false,
            error: err instanceof Error ? err.message : "请求失败",
          }));
        });
    },
    [],
  );

  useEffect(() => {
    if (!start) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    const t = setTimeout(() => run(start, prefs, budgetKm), DEBOUNCE_MS);
    return () => clearTimeout(t);
    // start identity changes on each click; prefs/budget on each slider move
  }, [start, prefs, budgetKm, run]);

  return state;
}
