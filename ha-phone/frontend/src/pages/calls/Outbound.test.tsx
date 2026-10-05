import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import Outbound from "./Outbound";
import { mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("Ausgehend", () => {
  it("zeigt die Wahlregeln", async () => {
    mockFetch({ "/api/outbound-rules": [], "/api/trunk": { phone_number: "+49221" }, "/api/trunk/dids": [] });
    renderAt(<Outbound />, { route: "/calls/outbound" });
    expect(screen.getByRole("heading", { level: 1, name: "Ausgehend" })).toBeInTheDocument();
    expect(await screen.findByText("Ausgehende Regeln")).toBeInTheDocument();
  });
});
