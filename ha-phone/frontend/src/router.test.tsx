import { describe, it, expect } from "vitest";

describe("ingress path bootstrap", () => {
  it("reads window.__INGRESS_PATH__ and defaults to empty string", () => {
    (window as any).__INGRESS_PATH__ = "/api/ingress/test123";
    const ingressPath: string = (window as any).__INGRESS_PATH__ ?? "";
    expect(ingressPath).toBe("/api/ingress/test123");
  });

  it("defaults to empty string when not set", () => {
    delete (window as any).__INGRESS_PATH__;
    const ingressPath: string = (window as any).__INGRESS_PATH__ ?? "";
    expect(ingressPath).toBe("");
  });
});
