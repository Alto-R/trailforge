// Thin wrapper over the 5 backend endpoints. All calls go to VITE_API_BASE
// (default "/api"), which Vite proxies to the FastAPI backend in dev.

import type {
  FeedbackIn,
  FeedbackOut,
  Health,
  Persona,
  RouteRequest,
  RouteResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJSON<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: (signal?: AbortSignal) => getJSON<Health>("/health", signal),
  personas: (signal?: AbortSignal) => getJSON<Persona[]>("/personas", signal),
  trails: (signal?: AbortSignal) =>
    getJSON<GeoJSON.FeatureCollection>("/trails", signal),
  route: (req: RouteRequest, signal?: AbortSignal) =>
    postJSON<RouteResponse>("/route", req, signal),
  feedback: (fb: FeedbackIn, signal?: AbortSignal) =>
    postJSON<FeedbackOut>("/feedback", fb, signal),
};
