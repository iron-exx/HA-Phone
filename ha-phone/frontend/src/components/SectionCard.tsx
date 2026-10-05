import { useId, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { IconTile, type Tone } from "./IconTile";

export function SectionCard({
  icon,
  tone = "blue",
  title,
  description,
  actions,
  className,
  children,
}: {
  icon?: LucideIcon;
  tone?: Tone;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={cn("grid gap-4 rounded-card border border-hair bg-card p-4 sm:p-5", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          {icon && <IconTile icon={icon} tone={tone} size="sm" />}
          <div className="min-w-0">
            <h2 id={headingId} className="font-display text-base font-extrabold leading-tight">{title}</h2>
            {description && <p className="mt-0.5 text-[13px] font-semibold text-muted-foreground">{description}</p>}
          </div>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  );
}
