import type { UseFormReturn } from "react-hook-form";
import type { RingGroup } from "@/types/api";
import { FormGrid } from "@/components/FormGrid";
import { ToggleRow } from "@/components/ToggleRow";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import type { EditFormValues } from "./schema";
import { RingGroupPicker } from "./RingGroupPicker";

export function EditGeneralTab({
  form,
  ringGroups,
  selectedRingGroupIds,
  onSelectedRingGroupIdsChange,
}: {
  form: UseFormReturn<EditFormValues>;
  ringGroups: RingGroup[];
  selectedRingGroupIds: number[];
  onSelectedRingGroupIdsChange: (ids: number[]) => void;
}) {
  return (
    <div className="space-y-4">
      <FormGrid>
        <FormField
          control={form.control}
          name="number"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Durchwahl (Nummer)</FormLabel>
              <FormControl>
                <Input type="number" className="font-mono opacity-60 cursor-not-allowed" {...field} readOnly />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="display_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Anzeigename</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="sip_password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>SIP-Passwort</FormLabel>
              <FormControl>
                <Input type="password" placeholder="Leer lassen = behalten" className="font-mono" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="internal_only"
          render={({ field }) => (
            <ToggleRow
              id={field.name}
              label="Nur intern"
              description="Kann nur intern telefonieren — kein Anruf nach außen (z.B. Türsprechstelle)."
              checked={field.value}
              onToggle={field.onChange}
            />
          )}
        />
        <FormField
          control={form.control}
          name="numeric_callerid"
          render={({ field }) => (
            <ToggleRow
              id={field.name}
              label="Altgeräte-Modus"
              description={'Anrufe an dieses Gerät senden nur die Nummer als Anrufername. Für alte SIP-Clients (z.B. Android nativ), die Namen als "Anonym" anzeigen.'}
              checked={field.value}
              onToggle={field.onChange}
            />
          )}
        />
      </FormGrid>
      <RingGroupPicker ringGroups={ringGroups} selectedIds={selectedRingGroupIds} onChange={onSelectedRingGroupIdsChange} />
    </div>
  );
}
