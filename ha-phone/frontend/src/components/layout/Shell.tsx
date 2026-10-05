import { useEffect, useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import Sidebar from "./Sidebar";
import { BrandMark } from "./BrandMark";

export default function Shell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 border-r border-hair bg-surface nav:block">
        <Sidebar />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-hair bg-surface px-4 py-2.5 nav:hidden">
          <button
            type="button"
            aria-label="Menü öffnen"
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            onClick={() => setMenuOpen(true)}
            className="grid size-10 place-items-center rounded-ctl border border-stroke bg-card text-foreground"
          >
            <Menu className="size-5" aria-hidden="true" />
          </button>
          <BrandMark className="size-8" />
          <span className="font-display text-base font-extrabold">HA-Phone</span>
        </header>
        <main className="flex-1 overflow-y-auto overflow-x-hidden">
          <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 nav:py-6">{children}</div>
        </main>
      </div>

      {menuOpen && (
        <div id="mobile-nav" role="dialog" aria-modal="true" aria-label="Navigation" className="fixed inset-0 z-40 nav:hidden">
          <button type="button" aria-label="Menü schließen" onClick={closeMenu} className="absolute inset-0 bg-black/40" />
          <aside className="absolute inset-y-0 left-0 w-60 max-w-[85vw] bg-surface shadow-2xl">
            <Sidebar onNavigate={closeMenu} />
          </aside>
        </div>
      )}
    </div>
  );
}
