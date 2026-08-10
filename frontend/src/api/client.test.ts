import { describe, expect, it } from "vitest";

import { apiClient, setCsrfToken } from "./client";

describe("apiClient CSRF", () => {
  it("передаёт выданный backend токен в защитном заголовке", () => {
    setCsrfToken("test-csrf-token");

    expect(apiClient.defaults.headers.common["X-CSRFToken"]).toBe("test-csrf-token");
  });
});
