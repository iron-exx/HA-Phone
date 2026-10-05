import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import Sidebar from "./components/layout/Sidebar";
import { renderAt } from "./test/render";

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

describe("Navigation unter dem Ingress-Präfix", () => {
  it("Menülinks tragen das Präfix und der aktive Punkt stimmt", () => {
    const base = "/api/hassio_ingress/tok123";
    renderAt(<Sidebar />, { basename: base, route: `${base}/calls/inbound` });
    const link = screen.getByRole("link", { name: "Eingehend" });
    expect(link).toHaveAttribute("href", `${base}/calls/inbound`);
    expect(link).toHaveAttribute("aria-current", "page");
  });
});
