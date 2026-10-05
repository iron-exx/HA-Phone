import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "./button";

describe("Button", () => {
  it("Hauptknopf nutzt Markenverlauf und lesbare Schriftfarbe", () => {
    render(<Button>Los</Button>);
    expect(screen.getByRole("button", { name: "Los" })).toHaveClass("bg-brand", "text-brand-ink", "shadow-glow", "rounded-ctl");
  });
  it("Umriss-Knopf hat keinen Verlauf", () => {
    render(<Button variant="outline">Abbrechen</Button>);
    expect(screen.getByRole("button", { name: "Abbrechen" })).not.toHaveClass("bg-brand");
  });
});
