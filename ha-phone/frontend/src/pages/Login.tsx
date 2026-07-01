import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (resp.status === 401) { setError("Falsches Passwort"); return; }
      if (!resp.ok) { setError("Anmeldung fehlgeschlagen — bitte erneut versuchen"); return; }
      const data = await resp.json();
      navigate(data.must_change_password ? "/change-password" : "/");
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
        <div className="absolute -bottom-20 left-1/4 h-64 w-64 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(6,78,59,0.25) 0%, transparent 70%)" }} />
        <div className="absolute top-1/3 right-1/4 h-48 w-48 rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle, rgba(30,58,138,0.2) 0%, transparent 70%)" }} />
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
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <img
            src="/haphone-logo.svg"
            alt="HA-Phone"
            className="h-20 w-20"
            style={{ filter: "drop-shadow(0 0 16px rgba(56,189,248,0.6))" }}
          />
          <div className="text-center">
            <h1 className="text-gradient text-2xl font-semibold tracking-tight">HA-Phone</h1>
            <p className="mt-1 text-xs text-muted-foreground">PBX Admin</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="password"
              className="block text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Passwort
            </label>
            <Input id="password" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus required className="h-11 font-mono text-base" placeholder="••••••••" />
          </div>

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
            {loading ? "Anmelden…" : "Anmelden"}
          </Button>
        </form>
      </div>
    </div>
  );
}
