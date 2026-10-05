import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { Extension } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { DoorStationsCard } from "./DoorStationsCard";
import { DoorSettingsDialog } from "./DoorSettingsDialog";
import { DoorbellHistory } from "./DoorbellHistory";

export default function Doorbell() {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Extension | null>(null);

  useEffect(() => {
    fetch("/api/extensions")
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((data: Extension[]) => setExtensions(data))
      .catch(() => toast.error("Nebenstellen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  function handleSaved(updated: Extension) {
    setExtensions((list) => list.map((e) => (e.id === updated.id ? updated : e)));
  }

  return (
    <div className="grid gap-4">
      <PageHeader />
      <DoorStationsCard extensions={extensions} loading={loading} onEdit={setEditing} />
      <DoorbellHistory />
      {editing && <DoorSettingsDialog extension={editing} onClose={() => setEditing(null)} onSaved={handleSaved} />}
    </div>
  );
}
