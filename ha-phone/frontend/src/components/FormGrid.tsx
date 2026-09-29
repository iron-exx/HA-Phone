import type { ReactNode } from "react";

/**
 * Layout for forms in dialogs (DialogContent size="form"): two columns from md up,
 * one on phones. Short fields and toggles take one cell, editors and long fields
 * span both with FormSpan. FormSection groups related fields under a heading.
 */
export function FormGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-x-6">{children}</div>;
}

export function FormSpan({ children }: { children: ReactNode }) {
  return <div className="md:col-span-2">{children}</div>;
}

export function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}
