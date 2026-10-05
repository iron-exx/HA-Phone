import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import Extensions from "./Extensions";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Nebenstellen", () => {
  it("listet Nebenstellen mit Status und verweist Türstationen auf die Türklingel", async () => {
    mockFetch({
      "/api/extensions": [
        { id: 1, number: 11, display_name: "Sandro", enabled: true },
        { id: 6, number: 16, display_name: "Türklingel", enabled: true, is_door: true },
      ],
      "/api/extensions/status": [{ number: "11", status: "Online" }, { number: "16", status: "Offline" }],
      "/api/ring-groups": [],
      "/api/provisioning/devices": [],
      "/api/diagnostics/overview": { extensions: [] },
    });
    renderAt(<Extensions />, { route: "/extensions" });
    expect(await screen.findByText("Sandro")).toBeInTheDocument();
    expect(await screen.findByText("angemeldet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tür" })).toHaveAttribute("href", "/doorbell");
    expect(screen.getByRole("button", { name: "Nebenstelle anlegen" })).toBeInTheDocument();
  });
});
