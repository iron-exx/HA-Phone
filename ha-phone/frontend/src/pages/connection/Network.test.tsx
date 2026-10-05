import { describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import Network from "./Network";
import { callsTo, jsonBody, mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Netzwerk", () => {
  it("übernimmt die erkannte Adresse und speichert sie", async () => {
    const fetchMock = mockFetch({ "/api/settings/public-ip": { ip: "203.0.113.9" }, "POST /api/settings/public-ip": { ok: true } });
    renderAt(<Network />, { route: "/connection/network" });
    expect(await screen.findByLabelText("Externe IP-Adresse")).toHaveValue("203.0.113.9");
    fireEvent.click(screen.getByRole("button", { name: "Speichern und anwenden" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/settings/public-ip")).toHaveLength(1));
    expect(jsonBody(callsTo(fetchMock, "POST", "/api/settings/public-ip")[0])).toEqual({ ip: "203.0.113.9" });
  });
});
