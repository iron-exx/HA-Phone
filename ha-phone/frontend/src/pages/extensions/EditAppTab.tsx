import type { UseFormReturn } from "react-hook-form";
import type { Extension } from "@/types/api";
import { FormGrid } from "@/components/FormGrid";
import { ToggleRow } from "@/components/ToggleRow";
import { FormField } from "@/components/ui/form";
import type { EditFormValues } from "./schema";

export function EditAppTab({ form, extension }: { form: UseFormReturn<EditFormValues>; extension: Extension }) {
  const paired = extension.mobile_devices ?? 0;
  return (
    <div className="space-y-4">
      <p className="rounded-ctl bg-raised px-3 py-2 text-sm font-semibold text-muted-foreground">
        {paired === 0
          ? "Noch kein Handy gekoppelt. Den QR-Code dafür gibt es in der Liste unter „HA-Phone App QR“."
          : `${paired === 1 ? "1 Handy ist" : `${paired} Handys sind`} mit dieser Nebenstelle gekoppelt.`}
      </p>
      <FormGrid>
        <FormField
          control={form.control}
          name="video_capable"
          render={({ field }) => (
            <ToggleRow
              id={field.name}
              label="Video-fähig"
              description="Erlaubt Videotelefonie (H.264) — z.B. Video-Türsprechstelle oder Linphone. Beide Gesprächsseiten müssen video-fähig sein."
              checked={field.value}
              onToggle={field.onChange}
            />
          )}
        />
        <FormField
          control={form.control}
          name="recording_allowed"
          render={({ field }) => (
            <ToggleRow
              id={field.name}
              label="Gesprächsaufzeichnung erlauben"
              description={"Die HA-Phone App darf Gespräche dieser Nebenstelle aufzeichnen (Taste „Aufnehmen“). Rechtlich nur mit Zustimmung aller Gesprächsteilnehmer zulässig (§ 201 StGB, DSGVO). Aufnahmen liegen unter /data/recordings/<Nebenstelle>/."}
              checked={field.value}
              onToggle={field.onChange}
            />
          )}
        />
      </FormGrid>
    </div>
  );
}
