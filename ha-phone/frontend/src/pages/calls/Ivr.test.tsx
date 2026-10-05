import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import Ivr from "./Ivr";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Sprachmenüs", () => {
  it("heißt Sprachmenüs und hat die deutsche Hauptaktion", async () => {
    mockFetch({ "/api/ivrs": [], "/api/extensions": [], "/api/ring-groups": [] });
    renderAt(<Ivr />, { route: "/calls/ivr" });
    expect(screen.getByRole("heading", { level: 1, name: "Sprachmenüs" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sprachmenü anlegen" })).toBeInTheDocument();
    expect(await screen.findByText("Noch keine Sprachmenüs")).toBeInTheDocument();
  });

  it("zeigt im Anlegen-Dialog Pflichtfeld-Fehler an, statt stumm zu bleiben", async () => {
    mockFetch({ "/api/ivrs": [], "/api/extensions": [], "/api/ring-groups": [] });
    renderAt(<Ivr />, { route: "/calls/ivr" });
    fireEvent.click(screen.getByRole("button", { name: "Sprachmenü anlegen" }));
    fireEvent.click(await screen.findByRole("button", { name: "IVR anlegen" }));
    expect(await screen.findByText("Pflichtfeld")).toBeInTheDocument();
  });
});
