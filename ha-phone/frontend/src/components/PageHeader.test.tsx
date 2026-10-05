import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { PageHeader } from "./PageHeader";
import { renderAt } from "@/test/render";

describe("PageHeader", () => {
  it("nimmt Brotkrumen, Titel und Beschreibung aus der Navigation", () => {
    renderAt(<PageHeader />, { route: "/calls/schedules" });
    expect(screen.getByText("Anrufe")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Zeiten & Feiertage" })).toHaveClass("text-brand-title");
    expect(screen.getByText(/Zeitsteuerung/)).toBeInTheDocument();
  });
  it("übernimmt eigenen Titel und Hauptaktion", () => {
    renderAt(<PageHeader title="Eigener Titel" actions={<button type="button">Los</button>} />, { route: "/extensions" });
    expect(screen.getByRole("heading", { level: 1, name: "Eigener Titel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Los" })).toBeInTheDocument();
  });
});
