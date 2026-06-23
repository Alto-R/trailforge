// TS contract mirroring backend/schemas.py. Hand-maintained: if the backend
// contract changes, update here and the compiler flags the breakage.

/** The 5 preference sliders. Keys === PREF_MAP keys in src/persona.py. */
export type Prefs = {
  challenge: number;
  nature: number;
  culture: number;
  popularity: number;
  scenic: number;
};

export const PREF_KEYS = [
  "challenge",
  "nature",
  "culture",
  "popularity",
  "scenic",
] as const;

/** Chinese display labels for each preference key. */
export const PREF_LABELS: Record<keyof Prefs, string> = {
  challenge: "挑战",
  nature: "自然",
  culture: "人文",
  popularity: "热门",
  scenic: "打卡",
};

/** GET /personas -> PersonaOut[] */
export type Persona = {
  id: string;
  label: string;
  description: string;
  size: number;
  default_prefs: Partial<Prefs>;
};

/** A WGS84 [lng, lat] pair. */
export type LngLat = [number, number];

/** POST /route request body (RouteRequest). */
export type RouteRequest = {
  start: LngLat;
  persona?: string | null;
  preferences?: Partial<Prefs> | null;
  budget_km: number;
  n_routes?: number;
  loop?: boolean;
};

/** One route in the candidate list (RouteCandidate). */
export type RouteCandidate = {
  length_km: number;
  n_segments: number;
  reachable: boolean;
  score: number;
  segments: number[];
  geojson: GeoJSON.FeatureCollection;
  attributes: Record<string, number>;
  labels: string[];
  loop?: boolean;
  closed?: boolean;
};

/** POST /route response (RouteResponse). */
export type RouteResponse = {
  candidates: RouteCandidate[];
  start_snapped: LngLat;
  reachable: boolean;
  prefs_used: Partial<Prefs>;
  note: string | null;
};

/** GET /health (HealthOut). */
export type Health = {
  status: string;
  model_loaded: boolean;
  n_segments: number;
  n_personas: number;
};

/** POST /feedback request (FeedbackIn). */
export type FeedbackIn = {
  chosen_index?: number | null;
  rating?: number | null;
  comment?: string | null;
  context?: Record<string, unknown> | null;
};

/** POST /feedback response (FeedbackOut). */
export type FeedbackOut = {
  status: string;
  stored: number;
};
