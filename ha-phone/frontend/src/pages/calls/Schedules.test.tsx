import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import Schedules from "./Schedules";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Zeiten & Feiertage", () => {
  it("zeigt Zeitsteuerungen und Feiertage auf einer Seite", async () => {
    mockFetch({ "/api/extensions": [], "/api/ring-groups": [], "/api/ivrs": [], "/api/time-conditions": [], "/api/holidays": [] });
    renderAt(<Schedules />, { route: "/calls/schedules" });
    expect(await screen.findByText("Noch keine Zeitsteuerung")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Zeitsteuerungen" })).toBeInTheDocument();
    expect(screen.getByText("Feiertage")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zeitsteuerung anlegen" })).toBeInTheDocument();
  });
});
