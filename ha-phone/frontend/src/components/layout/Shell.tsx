import { type ReactNode } from "react";
import Sidebar from "./Sidebar";

interface ShellProps {
  children: ReactNode;
}

export default function Shell({ children }: ShellProps) {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "hsl(222, 84%, 4%)" }}>

      {/* Ambient background orbs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div
          className="absolute -top-40 -left-40 h-80 w-80 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(76,29,149,0.35) 0%, transparent 70%)" }}
        />
        <div
          className="absolute bottom-0 right-0 h-96 w-96 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(6,78,59,0.2) 0%, transparent 70%)" }}
        />
        <div
          className="absolute top-1/2 left-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(30,58,138,0.12) 0%, transparent 70%)" }}
        />
      </div>

      {/* Sidebar */}
      <aside
        className="relative z-20 flex w-60 shrink-0 flex-col"
        style={{
          background: "rgba(10, 12, 30, 0.9)",
          borderRight: "1px solid rgba(139, 92, 246, 0.12)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
        }}
      >
        <Sidebar />
      </aside>

      {/* Main content */}
      <main className="relative z-10 flex-1 overflow-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
