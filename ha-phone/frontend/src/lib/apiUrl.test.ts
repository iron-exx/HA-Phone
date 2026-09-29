import { afterEach, describe, expect, it } from "vitest";
import { apiUrl } from "./apiUrl";

describe("apiUrl", () => {
  afterEach(() => {
    delete (window as { __INGRESS_PATH__?: string }).__INGRESS_PATH__;
  });

  it("prefixes /api/ paths with the Home Assistant ingress path", () => {
    (window as { __INGRESS_PATH__?: string }).__INGRESS_PATH__ = "/api/hassio_ingress/abc";
    expect(apiUrl("/api/doorbell/7/image")).toBe("/api/hassio_ingress/abc/api/doorbell/7/image");
  });

  it("leaves paths alone without ingress (direct access on port 80)", () => {
    expect(apiUrl("/api/doorbell/7/image")).toBe("/api/doorbell/7/image");
  });

  it("does not touch other URLs", () => {
    (window as { __INGRESS_PATH__?: string }).__INGRESS_PATH__ = "/api/hassio_ingress/abc";
    expect(apiUrl("https://example.org/x.png")).toBe("https://example.org/x.png");
  });
});
