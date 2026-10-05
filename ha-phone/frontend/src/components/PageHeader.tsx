import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { findNavEntry } from "@/nav";

export function PageHeader({ title, description, actions }: { title?: string; description?: string; actions?: ReactNode }) {
  const { pathname } = useLocation();
  const entry = findNavEntry(pathname);
  const crumb = entry?.group.label ?? "Übersicht";
  const heading = title ?? entry?.item.label ?? "";
  const text = description ?? entry?.item.description;
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-[0.06em] text-faint">{crumb}</p>
        <h1 className="mt-0.5 font-display text-[26px] font-extrabold leading-tight text-brand-title">{heading}</h1>
        {text && <p className="mt-1 max-w-[62ch] text-sm font-semibold text-muted-foreground">{text}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}
