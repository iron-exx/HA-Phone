import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type ChipTone = "ok" | "off" | "door" | "error" | "info";

const CHIP_CLASSES: Record<ChipTone, string> = {
  ok: "bg-answer-soft text-answer",
  off: "bg-raised text-faint",
  door: "bg-door-soft text-door",
  error: "bg-end-soft text-end",
  info: "bg-blue-soft text-blue",
};

export function StatusChip({ tone, dot = false, children }: { tone: ChipTone; dot?: boolean; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-extrabold", CHIP_CLASSES[tone])}>
      {dot && <span aria-hidden="true" className="size-[7px] rounded-full bg-current" />}
      {children}
    </span>
  );
}
