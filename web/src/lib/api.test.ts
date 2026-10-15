import { describe, expect, it } from "vitest";

import { fetchHealth } from "./api";

describe("fetchHealth", () => {
  it("parses a successful health payload", async () => {
    const original = global.fetch;
    global.fetch = async () =>
      new Response(
        JSON.stringify({
          status: "ok",
          version: "0.1.0",
          service: "databuddy-api",
        }),
        { status: 200 },
      );

    try {
      const body = await fetchHealth();
      expect(body.status).toBe("ok");
      expect(body.service).toBe("databuddy-api");
    } finally {
      global.fetch = original;
    }
  });
});
