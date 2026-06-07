// Vitest setup (referenced by vite.config.ts `test.setupFiles`).
// With `globals: true`, Testing Library auto-registers its afterEach cleanup,
// so this file only needs to exist as a hook point for future test helpers.
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
