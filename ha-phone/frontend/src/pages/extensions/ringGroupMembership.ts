import type { Extension, RingGroup } from "@/types/api";

export function getExtensionRingGroupIds(extension: Extension, ringGroups: RingGroup[]) {
  return ringGroups
    .filter((group) =>
      group.extension_numbers
        .split(",")
        .map((number) => number.trim())
        .includes(String(extension.number))
    )
    .map((group) => group.id);
}

export function toggleRingGroupId(ids: number[], id: number) {
  return ids.includes(id) ? ids.filter((current) => current !== id) : [...ids, id];
}

export function buildExtensionNumbers(group: RingGroup, extensionNumber: number, selected: boolean) {
  const numbers = group.extension_numbers
    .split(",")
    .map((number) => number.trim())
    .filter(Boolean)
    .filter((number) => number !== String(extensionNumber));

  if (selected) numbers.push(String(extensionNumber));

  return Array.from(new Set(numbers))
    .map((number) => Number(number))
    .filter((number) => Number.isFinite(number))
    .sort((a, b) => a - b)
    .join(",");
}

export async function syncRingGroupMemberships(
  extensionNumber: number,
  selectedRingGroupIds: number[],
  ringGroups: RingGroup[]
) {
  const updates = ringGroups
    .map((group) => ({
      ...group,
      extension_numbers: buildExtensionNumbers(
        group,
        extensionNumber,
        selectedRingGroupIds.includes(group.id)
      ),
    }))
    .filter((group, index) => group.extension_numbers !== ringGroups[index].extension_numbers);

  await Promise.all(
    updates.map((group) =>
      fetch(`/api/ring-groups/${group.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(group),
      }).then((resp) => {
        if (!resp.ok) throw new Error("Rufgruppe konnte nicht aktualisiert werden");
        return resp.json();
      })
    )
  );
}
