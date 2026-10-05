import { describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import Email from "./Email";
import { callsTo, mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";

describe("E-Mail", () => {
  it("lädt den Postausgang und speichert ihn", async () => {
    const fetchMock = mockFetch({
      "/api/settings/smtp": { host: "smtp.example.com", port: 587, encryption: "starttls", username: "u", password: "", from_addr: "pbx@example.com", from_name: "HA-Phone", enabled: true },
      "POST /api/settings/smtp": { ok: true },
    });
    renderAt(<Email />, { route: "/system/email" });
    expect(await screen.findByLabelText("SMTP-Server")).toHaveValue("smtp.example.com");
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/settings/smtp")).toHaveLength(1));
  });

  it("schickt keinen Test ohne Empfänger", async () => {
    const fetchMock = mockFetch({ "/api/settings/smtp": {} });
    renderAt(<Email />, { route: "/system/email" });
    fireEvent.click(await screen.findByRole("button", { name: "Test senden" }));
    expect(callsTo(fetchMock, "POST", "/api/settings/smtp/test")).toHaveLength(0);
  });
});
