import { Phone } from "lucide-react";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <span aria-hidden="true" className={cn("grid size-[34px] shrink-0 place-items-center rounded-[10px] bg-brand text-brand-ink", className)}>
      <Phone className="size-[18px]" />
    </span>
  );
}
