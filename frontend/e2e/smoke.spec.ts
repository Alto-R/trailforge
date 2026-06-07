import { expect, test } from "@playwright/test";

// Full-stack smoke: needs the FastAPI backend on :8000 (see playwright.config.ts).
// Flow: load → backend ready → pick a dense start → candidates appear →
// drag a slider (re-route) → "选这条" → feedback recorded.

// Trail-network bbox (from GET /trails) + a known dense climbing start.
const BBOX = {
  minLng: 115.4410858102621,
  minLat: 39.57995704571979,
  maxLng: 117.38461628876605,
  maxLat: 40.96460322837786,
};
const START = { lng: 116.18, lat: 39.97 };
const PAD = 60;
const TS = 512;

const lng2x = (lng: number) => ((lng + 180) / 360) * TS;
const lat2y = (lat: number) => {
  const s = Math.sin((lat * Math.PI) / 180);
  return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * TS;
};

test("pick start → candidates → re-route → feedback", async ({ page }) => {
  await page.goto("/");

  // backend self-check resolved
  await expect(page.getByText(/后端就绪/)).toBeVisible({ timeout: 15_000 });

  // project the dense start to a screen pixel inside the deck canvas
  const canvas = page.locator(".map-canvas");
  await expect(canvas).toBeVisible();
  await page.waitForTimeout(2000); // /trails load + fitBounds
  const rect = await canvas.boundingBox();
  if (!rect) throw new Error("map canvas not laid out");
  const x0 = lng2x(BBOX.minLng);
  const x1 = lng2x(BBOX.maxLng);
  const y0 = lat2y(BBOX.maxLat);
  const y1 = lat2y(BBOX.minLat);
  const zoom = Math.min(
    Math.log2((rect.width - 2 * PAD) / (x1 - x0)),
    Math.log2((rect.height - 2 * PAD) / (y1 - y0)),
  );
  const scale = 2 ** zoom;
  const px = rect.x + rect.width / 2 + (lng2x(START.lng) - (x0 + x1) / 2) * scale;
  const py =
    rect.y + rect.height / 2 + (lat2y(START.lat) - (y0 + y1) / 2) * scale;

  await page.mouse.click(px, py);

  // candidates render
  await expect(page.locator(".card").first()).toBeVisible({ timeout: 15_000 });
  const before = await page.locator(".card").count();
  expect(before).toBeGreaterThan(0);

  // drag the challenge slider → re-route (debounced); cards stay present
  const slider = page.getByLabel("挑战");
  await slider.focus();
  for (let i = 0; i < 4; i++) await slider.press("ArrowRight");
  await page.waitForTimeout(1200); // debounce + re-route settle
  await expect(page.getByText("正在生成候选路线…")).toHaveCount(0);
  await expect(page.locator(".card").first()).toBeVisible();

  // feedback closes the loop
  const first = page.locator(".card").first();
  const choose = first.getByRole("button", { name: "选这条" });
  await choose.scrollIntoViewIfNeeded();
  await choose.click();
  await expect(first.getByText(/已记录/)).toBeVisible({ timeout: 10_000 });
});
