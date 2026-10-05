import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import Groups from "./Groups";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Gruppen", () => {
  it("zeigt Rufgruppen und Nebenstellen-Gruppen unter einem Titel", async () => {
    mockFetch({ "/api/extension-groups": [], "/api/extensions": [], "/api/ring-groups": [] });
    renderAt(<Groups />, { route: "/calls/groups" });
    expect(screen.getByRole("heading", { level: 1, name: "Gruppen" })).toBeInTheDocument();
    expect(await screen.findByText("Rufgruppen")).toBeInTheDocument();
    expect(screen.getByText("Nebenstellen-Gruppen")).toBeInTheDocument();
  });
});
