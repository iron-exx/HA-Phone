import { describe, expect, it } from "vitest";
import { fireEvent, screen, within } from "@testing-library/react";
import Shell from "./Shell";
import { renderAt } from "@/test/render";

describe("Shell", () => {
  it("öffnet die Navigation als Schublade und schließt sie nach der Auswahl", () => {
    renderAt(<Shell><p>Inhalt</p></Shell>);
    const menuButton = screen.getByRole("button", { name: "Menü öffnen" });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(menuButton);
    const drawer = screen.getByRole("dialog", { name: "Navigation" });
    fireEvent.click(within(drawer).getByRole("link", { name: "Telefonbuch" }));
    expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/phonebook");
  });

  it("schließt die Schublade mit Escape und über den Hintergrund", () => {
    renderAt(<Shell><p>Inhalt</p></Shell>);
    fireEvent.click(screen.getByRole("button", { name: "Menü öffnen" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Menü öffnen" }));
    fireEvent.click(screen.getByRole("button", { name: "Menü schließen" }));
    expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument();
  });
});
