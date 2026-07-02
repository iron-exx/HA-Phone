import { useEffect, useState } from "react";
import { Routes, Route, useNavigate } from "react-router-dom";
import { Toaster } from "sonner";
import Shell from "./components/layout/Shell";
import Dashboard from "./pages/Dashboard";
import Extensions from "./pages/Extensions";
import Trunk from "./pages/Trunk";
import Routing from "./pages/Routing";
import Voicemail from "./pages/Voicemail";
import PublicIP from "./pages/PublicIP";
import Diagnostics from "./pages/Diagnostics";
import Provisioning from "./pages/Provisioning";
import Logo from "./components/Logo";
import Login from "./pages/Login";
import ChangePassword from "./pages/ChangePassword";

type AuthStatus = "checking" | "ok" | "error";

/**
 * Auth guard: check session on app load; redirect to /login on 401 or
 * /change-password on 403. Always renders visible feedback — a visible loading
 * indicator while the check is in flight and a visible error panel (with reload)
 * on network failure — so a hung/failed check can never produce a silent blank
 * screen (GAP-AUTHGUARD-BLANK).
 */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState<AuthStatus>("checking");

  useEffect(() => {
    // fetch stays root-relative so the main.tsx ingress wrapper prefixes it.
    fetch("/api/extensions")
      .then((resp) => {
        if (resp.status === 401) {
          navigate("/login");
        } else if (resp.status === 403) {
          const mustChange = resp.headers.get("x-must-change-password");
          if (mustChange === "true") {
            navigate("/change-password");
          } else {
            navigate("/login");
          }
        }
        setStatus("ok");
      })
      .catch(() => {
        // Network error / hung add-on — surface a visible recoverable error
        // instead of silently rendering children with no session.
        setStatus("error");
      });
  }, [navigate]);

  if (status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-3" role="status" aria-live="polite">
          <Logo className="size-12" />
          <div
            className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary"
            aria-hidden="true"
          />
          <span className="text-sm text-muted-foreground">Lade…</span>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground">
        <div className="flex max-w-sm flex-col items-center gap-4 text-center" role="alert">
          <p className="text-base font-medium">
            Verbindung zum Add-on fehlgeschlagen
          </p>
          <p className="text-sm text-muted-foreground">
            Die Sitzung konnte nicht geprüft werden. Bitte laden Sie die Seite neu.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Seite neu laden
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <>
      <Toaster position="top-right" richColors />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/change-password" element={<ChangePassword />} />
        <Route
          path="/*"
          element={
            <AuthGuard>
              <Shell>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/extensions" element={<Extensions />} />
                  <Route path="/trunk" element={<Trunk />} />
                  <Route path="/routing" element={<Routing />} />
                  <Route path="/voicemail" element={<Voicemail />} />
                  <Route path="/settings/public-ip" element={<PublicIP />} />
                  <Route path="/diagnostics" element={<Diagnostics />} />
                  <Route path="/provisioning" element={<Provisioning />} />
                </Routes>
              </Shell>
            </AuthGuard>
          }
        />
      </Routes>
    </>
  );
}
