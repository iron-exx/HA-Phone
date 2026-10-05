import { apiUrl } from "./lib/apiUrl";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/manrope/latin-500.css";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "@fontsource/manrope/latin-800.css";
import "@fontsource/bricolage-grotesque/latin-700.css";
import "@fontsource/bricolage-grotesque/latin-800.css";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./components/ThemeProvider";
import { TooltipProvider } from "./components/ui/tooltip";
import { applyTheme, readThemePreference, resolveTheme } from "./lib/theme";
import "./index.css";

// Hell/dunkel vor dem ersten Rendern setzen, damit nichts aufblitzt.
// Danach übernimmt der ThemeProvider (Systemwechsel, Wahl im Konto).
applyTheme(resolveTheme(readThemePreference()));

// HA ingress path injection — FastAPI injects window.__INGRESS_PATH__ into index.html
const ingressPath: string = (window as any).__INGRESS_PATH__ ?? "";

// Under HA ingress the SPA is served from /api/hassio_ingress/<token>/, so a
// root-relative fetch("/api/...") would hit HA Core instead of this add-on and
// bypass the ingress prefix entirely. Prefix every root-relative /api/ call with
// the ingress path so all 8 pages' fetches reach the backend without per-call edits.
if (ingressPath) {
  const origFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string") input = apiUrl(input);
    return origFetch(input, init);
  };
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <BrowserRouter basename={ingressPath}>
          <TooltipProvider>
            <App />
          </TooltipProvider>
        </BrowserRouter>
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
