import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { AppLogsCard } from "./AppLogsCard";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("App-Protokolle", () => {
  it("listet Protokolle mit Download-Link unter dem Ingress-Präfix", async () => {
    (window as { __INGRESS_PATH__?: string }).__INGRESS_PATH__ = "/api/hassio_ingress/tok";
    mockFetch({ "/api/diagnostics/app-logs": [{ name: "app-11-2026-10-05.log", size: 2048, mtime: 1_780_000_000 }] });
    renderAt(<AppLogsCard />);
    const link = await screen.findByRole("link", { name: /Herunterladen/ });
    expect(link).toHaveAttribute("href", "/api/hassio_ingress/tok/api/diagnostics/app-logs/app-11-2026-10-05.log");
    delete (window as { __INGRESS_PATH__?: string }).__INGRESS_PATH__;
  });

  it("zeigt einen Leerzustand", async () => {
    mockFetch({ "/api/diagnostics/app-logs": [] });
    renderAt(<AppLogsCard />);
    expect(await screen.findByText("Noch keine Protokolle hochgeladen.")).toBeInTheDocument();
  });
});
