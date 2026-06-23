// App: single-screen layout. Left control panel (persona + sliders), right map.
// Owns the shared state (start / persona / prefs / budget / selection) and wires
// useRoute -> map candidate layer + candidate list.

import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { ControlPanel } from "./components/ControlPanel";
import { CandidateList } from "./components/CandidateList";
import { Banner } from "./components/Banner";
import { MapView } from "./components/MapView";
import { useRoute } from "./hooks/useRoute";
import type { Health, LngLat, Persona, Prefs, RouteCandidate } from "./types";
import "./styles/app.css";

const BALANCED: Prefs = {
  challenge: 0.2,
  nature: 0.2,
  culture: 0.2,
  popularity: 0.2,
  scenic: 0.2,
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [trails, setTrails] = useState<GeoJSON.FeatureCollection | null>(null);

  const [start, setStart] = useState<LngLat | null>(null);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<Prefs>(BALANCED);
  const [budgetKm, setBudgetKm] = useState(4);
  const [loop, setLoop] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  // Feedback keyed by a stable route signature so a "✓ recorded" mark survives
  // re-routes (drag a slider, the same route reappears → still marked).
  const [rated, setRated] = useState<Record<string, number | null>>({});

  // startup self-check + load personas/trails once
  useEffect(() => {
    const ac = new AbortController();
    api
      .health(ac.signal)
      .then(setHealth)
      .catch((e: unknown) => {
        if (ac.signal.aborted) return; // StrictMode remount aborted us; ignore
        setHealthErr(e instanceof Error ? e.message : "后端未连接");
      });
    api.personas(ac.signal).then(setPersonas).catch(() => undefined);
    api.trails(ac.signal).then(setTrails).catch(() => undefined);
    return () => ac.abort();
  }, []);

  const route = useRoute(start, prefs, budgetKm, loop);
  const candidates = route.data?.candidates ?? [];

  // reset selection whenever a fresh result arrives
  useEffect(() => {
    setSelectedIdx(null);
    setHoveredIdx(null);
  }, [route.data]);

  const onPickPersona = (p: Persona) => {
    setPersonaId(p.id);
    setPrefs({ ...BALANCED, ...p.default_prefs });
  };
  const onChangePrefs = (next: Prefs) => {
    setPrefs(next);
    setPersonaId(null); // diverged from preset
  };

  const sigOf = (c: RouteCandidate) =>
    `${c.segments[0]}_${c.segments[c.segments.length - 1]}_${c.n_segments}`;
  const submittedFor = (c: RouteCandidate) => {
    const sig = sigOf(c);
    return sig in rated ? { rating: rated[sig] } : null;
  };
  const submitFeedback = (
    c: RouteCandidate,
    rating: number | null,
    index: number,
  ) => {
    const sig = sigOf(c);
    if (sig in rated) return;
    setRated((prev) => ({ ...prev, [sig]: rating })); // optimistic
    api
      .feedback({
        chosen_index: index,
        rating,
        comment: null,
        context: { start, prefs, budget_km: budgetKm },
      })
      .catch(() => {
        setRated((prev) => {
          const next = { ...prev };
          delete next[sig]; // roll back so the user can retry
          return next;
        });
      });
  };

  const activeIdx = hoveredIdx ?? selectedIdx;
  const startSnapped = route.data?.start_snapped ?? null;

  const banner = useMemo(() => {
    if (healthErr) return { kind: "error" as const, text: `后端未连接：${healthErr}（请先启动 uvicorn backend.app:app）` };
    if (route.error) return { kind: "error" as const, text: `请求失败：${route.error}` };
    if (route.data && !route.data.reachable && route.data.note)
      return { kind: "warn" as const, text: route.data.note };
    return null;
  }, [healthErr, route.error, route.data]);

  return (
    <div className="app">
      <aside className="sidebar">
        <ControlPanel
          health={health}
          personas={personas}
          personaId={personaId}
          prefs={prefs}
          budgetKm={budgetKm}
          loop={loop}
          hasStart={start !== null}
          loading={route.loading}
          onPickPersona={onPickPersona}
          onChangePrefs={onChangePrefs}
          onChangeBudget={setBudgetKm}
          onChangeLoop={setLoop}
        />
        <CandidateList
          candidates={candidates}
          loading={route.loading}
          selectedIdx={selectedIdx}
          hoveredIdx={hoveredIdx}
          hasStart={start !== null}
          submittedFor={submittedFor}
          onRate={submitFeedback}
          onSelect={setSelectedIdx}
          onHover={setHoveredIdx}
        />
      </aside>
      <main className="map-pane">
        {banner && <Banner kind={banner.kind} text={banner.text} />}
        <MapView
          trails={trails}
          candidates={candidates}
          pickedStart={start}
          startSnapped={startSnapped}
          activeIdx={activeIdx}
          onPickStart={setStart}
          onSelectCandidate={setSelectedIdx}
          onHoverCandidate={setHoveredIdx}
        />
      </main>
    </div>
  );
}
