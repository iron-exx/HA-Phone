import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

export function useLogout(): () => Promise<void> {
  const navigate = useNavigate();
  return useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Keine Verbindung: die Sitzung im Browser trotzdem verlassen.
    }
    navigate("/login");
  }, [navigate]);
}
