import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
  info: ErrorInfo | null;
}

/**
 * Top-level error boundary. React render crashes otherwise produce a blank
 * white screen with the real error only visible in the dev console. Under HA
 * ingress the console is hard to reach, so surface the error ON SCREEN instead.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ error, info });
    // Also log for anyone who does have the console open.
    console.error("Unhandled render error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            minHeight: "100vh",
            background: "#0f1117",
            color: "#e5e7eb",
            padding: "2rem",
            fontFamily: "ui-monospace, monospace",
            overflow: "auto",
          }}
        >
          <h1 style={{ color: "#f87171", fontSize: "1.25rem", marginBottom: "1rem" }}>
            UI error — {this.state.error.name}: {this.state.error.message}
          </h1>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem", color: "#9ca3af" }}>
            {this.state.error.stack}
          </pre>
          {this.state.info?.componentStack && (
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.75rem", color: "#6b7280", marginTop: "1rem" }}>
              {this.state.info.componentStack}
            </pre>
          )}
          <button
            onClick={() => location.reload()}
            style={{
              marginTop: "1.5rem",
              padding: "0.5rem 1rem",
              background: "#1f2937",
              color: "#e5e7eb",
              border: "1px solid #374151",
              borderRadius: "0.375rem",
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
