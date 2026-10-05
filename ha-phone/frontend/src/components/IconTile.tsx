import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type Tone = "blue" | "answer" | "door" | "violet" | "end";

const TONE_CLASSES: Record<Tone, string> = {
  blue: "bg-blue-soft text-blue",
  answer: "bg-answer-soft text-answer",
  door: "bg-door-soft text-door",
  violet: "bg-violet-soft text-violet",
  end: "bg-end-soft text-end",
};

export function IconTile({ icon: Icon, tone = "blue", size = "md" }: { icon: LucideIcon; tone?: Tone; size?: "sm" | "md" }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center",
        size === "md" ? "size-10 rounded-[12px] [&_svg]:size-[21px]" : "size-[30px] rounded-[9px] [&_svg]:size-4",
        TONE_CLASSES[tone],
      )}
    >
      <Icon />
    </span>
  );
}
