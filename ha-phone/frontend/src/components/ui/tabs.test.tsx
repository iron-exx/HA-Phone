import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

describe("Tabs", () => {
  it("wechselt den Reiter und hält inaktive Inhalte mit forceMount im DOM", () => {
    render(
      <Tabs defaultValue="a">
        <TabsList aria-label="Test">
          <TabsTrigger value="a">Eins</TabsTrigger>
          <TabsTrigger value="b">Zwei</TabsTrigger>
        </TabsList>
        <TabsContent value="a" forceMount>Inhalt A</TabsContent>
        <TabsContent value="b" forceMount>Inhalt B</TabsContent>
      </Tabs>,
    );
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Zwei" }), { button: 0 });
    expect(screen.getByRole("tab", { name: "Zwei" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Inhalt A")).toHaveAttribute("data-state", "inactive");
    expect(screen.getByText("Inhalt A")).toHaveClass("data-[state=inactive]:hidden");
  });
});
