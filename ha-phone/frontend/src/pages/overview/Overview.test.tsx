import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import Overview from "./Overview";
import { mockFetch, withStatus } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const today = new Date();
const door = (h: number, answered: string) => ({
  id: h, door_number: 16, door_name: "Türklingel", started_at: new Date(today.getFullYear(), today.getMonth(), today.getDate(), h, 5).toISOString(),
  ended_at: null, answered_by: answered, door_opened: false, has_image: false,
});

describe("Übersicht", () => {
  it("zeigt Kacheln, letzte Klingeln und offene Punkte", async () => {
    mockFetch({
      "/api/trunk/status": { status: "Registered" },
      "/api/extensions": [{ id: 1, number: 11, display_name: "Sandro", enabled: true }, { id: 2, number: 15, display_name: "dect", enabled: true }],
      "/api/extensions/status": [{ number: "11", status: "Online" }, { number: "15", status: "Offline" }],
      "/api/status/active-calls": { count: 0 },
      "/api/doorbell": [door(0, ""), door(1, "Büro")],
      "/api/update/info": { version: "0.7.158", version_latest: "0.7.158", update_available: false },
      "/api/diagnostics/config-regeneration": { ok: true, source: null, last_run_at: null, last_failure_at: null, steps: [] },
    });
    renderAt(<Overview />, { route: "/" });
    expect(await screen.findByText("Nst. 15 „dect“ ist nicht angemeldet.")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Zuletzt an der Tür" })).toBeInTheDocument();
    expect(screen.getByText("verpasst")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Handy koppeln" })).toHaveAttribute("href", "/extensions");
  });

  it("meldet einen fehlgeschlagenen Update-Start per Hinweis und lässt den Knopf wieder zu", async () => {
    mockFetch({
      "/api/trunk/status": { status: "Registered" },
      "/api/extensions": [],
      "/api/extensions/status": [],
      "/api/status/active-calls": { count: 0 },
      "/api/doorbell": [],
      "/api/update/info": { version: "0.7.158", version_latest: "0.7.159", update_available: true },
      "/api/diagnostics/config-regeneration": { ok: true, source: null, last_run_at: null, last_failure_at: null, steps: [] },
      "POST /api/update/start": withStatus(500, { detail: "boom" }),
    });
    renderAt(<Overview />, { route: "/" });
    fireEvent.click(await screen.findByRole("button", { name: "Jetzt aktualisieren" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Update konnte nicht gestartet werden."));
    expect(await screen.findByRole("button", { name: "Jetzt aktualisieren" })).toBeEnabled();
  });
});
