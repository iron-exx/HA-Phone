import type { UseFormReturn } from "react-hook-form";
import { FormGrid } from "@/components/FormGrid";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PRESENCE_STATUSES, type EditFormValues } from "./schema";
import { PresenceRules } from "./PresenceRules";

export function EditReachTab({ form, extensionId }: { form: UseFormReturn<EditFormValues>; extensionId: number }) {
  return (
    <div className="space-y-6">
      <FormGrid>
        <FormField
          control={form.control}
          name="presence_status"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Anwesenheit</FormLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {PRESENCE_STATUSES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Bestimmt, welche Weiterleitungsregel unten für diesen Status gilt.
              </p>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="ha_person"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Gehört zu (Home-Assistant-Person)</FormLabel>
              <FormControl>
                <Input placeholder="person.anna" className="font-mono" {...field} />
              </FormControl>
              <p className="text-xs text-muted-foreground">
                Klingelt die Türstation, bleibt dieses Telefon still, solange die Person unterwegs und jemand anderes zu Hause ist. Ist niemand zu Hause, klingelt es auch unterwegs. Leer = klingelt immer.
              </p>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="mobile_fallback"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Rückfall auf Handynummer</FormLabel>
              <FormControl>
                <Input placeholder="0171 5551234" inputMode="tel" className="font-mono" {...field} />
              </FormControl>
              <p className="text-xs text-muted-foreground">
                Ist kein Gerät dieser Nebenstelle erreichbar (App offline, Tischtelefon aus), ruft die Anlage diese Nummer über die Amtsleitung an, statt gleich auf die Mailbox zu gehen. Klingelt ein Gerät und niemand nimmt ab, geht es wie bisher auf die Mailbox. Achtung: Das Gespräch über die Amtsleitung kann Kosten verursachen. Leer = aus.
              </p>
              <FormMessage />
            </FormItem>
          )}
        />
      </FormGrid>
      <PresenceRules extensionId={extensionId} />
    </div>
  );
}
