import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { TooltipProvider } from "./components/ui/tooltip";
import "./index.css";

// Force dark mode — dark-only per UI-SPEC; no ThemeProvider, no localStorage
document.documentElement.classList.add("dark");

// HA ingress path injection — FastAPI injects window.__INGRESS_PATH__ into index.html
const ingressPath: string = (window as any).__INGRESS_PATH__ ?? "";

// Under HA ingress the SPA is served from /api/hassio_ingress/<token>/, so a
// root-relative fetch("/api/...") would hit HA Core instead of this add-on and
// bypass the ingress prefix entirely. Prefix every root-relative /api/ call with
// the ingress path so all 8 pages' fetches reach the backend without per-call edits.
if (ingressPath) {
  const origFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && input.startsWith("/api/")) {
      input = ingressPath + input;
    }
    return origFetch(input, init);
  };
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter basename={ingressPath}>
        <TooltipProvider>
          <App />
        </TooltipProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
