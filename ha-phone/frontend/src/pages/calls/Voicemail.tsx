import { useEffect, useState } from "react";
import { toast } from "sonner";
import { type Extension, type VoicemailSettings } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { VoicemailCard } from "./VoicemailCard";

export default function Voicemail() {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [settings, setSettings] = useState<VoicemailSettings[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/voicemail-settings").then((r) => r.json()),
    ])
      .then(([exts, vms]: [Extension[], VoicemailSettings[]]) => {
        setExtensions(exts);
        setSettings(vms);
      })
      .catch(() => toast.error("Voicemail-Einstellungen konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  function handleSaved(updated: VoicemailSettings) {
    setSettings((prev) => {
      const exists = prev.find((s) => s.id === updated.id);
      if (exists) return prev.map((s) => (s.id === updated.id ? updated : s));
      return [...prev, updated];
    });
  }

  return (
    <div>
      <PageHeader />

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : extensions.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-sm text-muted-foreground">
            Keine Nebenstellen vorhanden. Lege zuerst Nebenstellen an, um Voicemail-Einstellungen zu konfigurieren.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {extensions.map((ext) => {
            const extSettings = settings.find((s) => s.extension_id === ext.id);
            return (
              <VoicemailCard
                key={ext.id}
                extension={ext}
                settings={extSettings}
                onSaved={handleSaved}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
