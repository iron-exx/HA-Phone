import type { LucideIcon } from "lucide-react";
import { IconTile, type Tone } from "@/components/IconTile";

export function KpiTile({ icon, tone, value, label }: { icon: LucideIcon; tone: Tone; value: string; label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-card border border-hair bg-card p-4">
      <IconTile icon={icon} tone={tone} />
      <div className="min-w-0">
        <div className="font-display text-[26px] font-extrabold leading-none tabular-nums">{value}</div>
        <small className="mt-1 block text-[12.5px] font-semibold text-muted-foreground">{label}</small>
      </div>
    </div>
  );
}
