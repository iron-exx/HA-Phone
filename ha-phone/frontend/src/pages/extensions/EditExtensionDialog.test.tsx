import { describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { EditExtensionDialog } from "./EditExtensionDialog";
import { callsTo, jsonBody, mockFetch } from "@/test/mockFetch";
import { renderAt } from "@/test/render";
import type { Extension } from "@/types/api";

const EXT: Extension = { id: 1, number: 11, display_name: "Sandro", enabled: true, presence_status: "available", mobile_fallback: "" };
const LOADS = { "/api/extensions": [EXT], "/api/ring-groups": [], "/api/ivrs": [], "/api/presence-rules": [] };

function renderDialog() {
  return renderAt(
    <EditExtensionDialog extension={EXT} onClose={() => {}} onUpdated={() => {}} ringGroups={[]} onRingGroupsChanged={async () => {}} />,
  );
}

describe("EditExtensionDialog", () => {
  it("hat die Reiter Allgemein, Handy-App und Erreichbarkeit", () => {
    mockFetch(LOADS);
    renderDialog();
    expect(screen.getByRole("tab", { name: "Allgemein" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Handy-App" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Erreichbarkeit" })).toBeInTheDocument();
    expect(screen.queryByText("Türstation")).not.toBeInTheDocument();
  });

  it("springt bei einem Fehler im verdeckten Reiter dorthin", async () => {
    const fetchMock = mockFetch(LOADS);
    renderDialog();
    fireEvent.change(screen.getByLabelText("Rückfall auf Handynummer"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(screen.getByRole("tab", { name: "Erreichbarkeit" })).toHaveAttribute("aria-selected", "true"));
    expect(screen.getByText("Telefonnummer, z. B. 0171 5551234")).toBeInTheDocument();
    expect(callsTo(fetchMock, "PATCH", "/api/extensions/1")).toHaveLength(0);
  });

  it("„Regel speichern“ legt nur die Regel an und speichert nicht die Nebenstelle", async () => {
    const fetchMock = mockFetch({ ...LOADS, "POST /api/presence-rules": { id: 9 } });
    renderDialog();
    fireEvent.click(await screen.findByRole("button", { name: "Regel speichern" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/api/presence-rules")).toHaveLength(1));
    expect(jsonBody(callsTo(fetchMock, "POST", "/api/presence-rules")[0]).extension_id).toBe(1);
    expect(callsTo(fetchMock, "PATCH", "/api/extensions/1")).toHaveLength(0);
  });
});
