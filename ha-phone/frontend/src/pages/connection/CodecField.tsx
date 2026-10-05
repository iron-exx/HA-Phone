import type { Control } from "react-hook-form";
import { FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { cn } from "@/lib/utils";
import { CODEC_OPTIONS, type TrunkFormValues } from "./trunkSchema";

export function CodecField({ control }: { control: Control<TrunkFormValues> }) {
  return (
    <FormField
      control={control}
      name="codecs"
      render={({ field }) => {
        const selected = field.value ? field.value.split(",").filter(Boolean) : [];
        const toggle = (id: string) => {
          const next = selected.includes(id) ? selected.filter((c) => c !== id) : [...selected, id];
          field.onChange(next.join(","));
        };
        return (
          <FormItem>
            <FormLabel>
              Sprachformate (Codecs){" "}
              <span className="ml-1 font-normal text-muted-foreground">(Reihenfolge = Priorität; Standard: u-law, a-law)</span>
            </FormLabel>
            <div className="flex flex-wrap gap-2">
              {CODEC_OPTIONS.map((c) => {
                const on = selected.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggle(c.id)}
                    className={cn(
                      "cursor-pointer rounded-ctl border px-3 py-1.5 font-mono text-xs transition-colors",
                      on ? "border-blue bg-blue-soft text-foreground" : "border-stroke bg-card text-muted-foreground",
                    )}
                  >
                    {on ? "✓ " : ""}
                    {c.label}
                  </button>
                );
              })}
            </div>
            <FormMessage />
          </FormItem>
        );
      }}
    />
  );
}
