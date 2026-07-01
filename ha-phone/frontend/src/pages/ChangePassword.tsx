import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShieldCheck } from "lucide-react";
import Logo from "@/components/Logo";

export default function ChangePassword() {
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (pw.length < 12) { setError("Mindestens 12 Zeichen erforderlich"); return; }
    if (pw !== confirm) { setError("Passwörter stimmen nicht überein"); return; }
    setLoading(true);
    try {
      const resp = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: pw }),
      });
      if (resp.status === 401) { navigate("/login"); return; }
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data?.detail ?? "Passwort konnte nicht gesetzt werden");
        return;
      }
      navigate("/");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="relative flex min-h-screen items-center justify-center overflow-hidden"
      style={{ background: "hsl(222, 84%, 4%)" }}
    >
      {/* Ambient orbs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(76,29,149,0.4) 0%, transparent 70%)" }} />
        <div className="absolute -bottom-20 right-1/4 h-64 w-64 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(6,78,59,0.25) 0%, transparent 70%)" }} />
      </div>

      {/* Card */}
      <div className="relative z-10 w-full max-w-sm rounded-2xl p-8"
        style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.08)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          boxShadow: "0 25px 50px rgba(0,0,0,0.5), 0 0 0 1px rgba(139,92,246,0.08)",
        }}
      >
        {/* Logo + header */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="relative">
            <Logo
              className="h-16 w-16"
              style={{ filter: "drop-shadow(0 0 12px rgba(56,189,248,0.5))" }}
            />
            <div className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full"
              style={{ background: "linear-gradient(135deg, #7C3AED, #4F46E5)", boxShadow: "0 0 8px rgba(124,58,237,0.6)" }}>
              <ShieldCheck className="h-3.5 w-3.5 text-white" />
            </div>
          </div>
          <div className="text-center">
            <h1 className="text-gradient text-xl font-semibold tracking-tight">Neues Passwort</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Erster Login — wähle ein sicheres Admin-Passwort.
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="new-password"
              className="block text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Neues Passwort
              <span className="ml-1 normal-case font-normal">(min. 12 Zeichen)</span>
            </label>
            <Input id="new-password" type="password" value={pw}
              onChange={(e) => setPw(e.target.value)}
              autoFocus required className="h-11 font-mono text-base" />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="confirm-password"
              className="block text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Passwort bestätigen
            </label>
            <Input id="confirm-password" type="password" value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required className="h-11 font-mono text-base" />
          </div>

          {/* Password strength hint */}
          {pw.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="h-1 flex-1 rounded-full overflow-hidden"
                style={{ background: "rgba(255,255,255,0.06)" }}>
                <div className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.min(100, (pw.length / 20) * 100)}%`,
                    background: pw.length < 12 ? "#EF4444" : pw.length < 16 ? "#F59E0B" : "#22C55E",
                  }} />
              </div>
              <span className="text-xs" style={{
                color: pw.length < 12 ? "#FCA5A5" : pw.length < 16 ? "#FCD34D" : "#86EFAC"
              }}>
                {pw.length < 12 ? "Zu kurz" : pw.length < 16 ? "Gut" : "Stark"}
              </span>
            </div>
          )}

          {error && (
            <div className="rounded-lg px-3 py-2 text-sm"
              style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#FCA5A5" }}>
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading}
            className="mt-2 h-11 w-full cursor-pointer text-sm font-semibold"
            style={{
              background: "linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%)",
              boxShadow: loading ? "none" : "0 0 20px rgba(124,58,237,0.4)",
              border: "none",
            }}>
            {loading ? "Speichert…" : "Speichern & Weiter"}
          </Button>
        </form>
      </div>
    </div>
  );
}
