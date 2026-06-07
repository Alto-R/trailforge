import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import type { RouteRequest } from "./types";

describe("api", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ ok: 1 }) });
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("GET /health hits base + path", async () => {
    await api.health();
    expect(fetchMock).toHaveBeenCalledWith("/api/health", { signal: undefined });
  });

  it("POST /route sends JSON body + header", async () => {
    const req: RouteRequest = {
      start: [116.1, 40.0],
      preferences: { challenge: 0.5 },
      budget_km: 4,
      n_routes: 4,
    };
    await api.route(req);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/route");
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual(req);
  });

  it("rejects on a non-2xx response", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500 });
    await expect(api.health()).rejects.toThrow("500");
  });
});
