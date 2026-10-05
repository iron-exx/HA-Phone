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
            background: "var(--ground)",
            color: "var(--text)",
            padding: "2rem",
            fontFamily: "ui-monospace, monospace",
            overflow: "auto",
          }}
        >
          <h1 style={{ color: "var(--end)", fontSize: "1.25rem", marginBottom: "1rem" }}>
            Oberflächenfehler – {this.state.error.name}: {this.state.error.message}
          </h1>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            {this.state.error.stack}
          </pre>
          {this.state.info?.componentStack && (
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.75rem", color: "var(--text-faint)", marginTop: "1rem" }}>
              {this.state.info.componentStack}
            </pre>
          )}
          <button
            onClick={() => location.reload()}
            style={{
              marginTop: "1.5rem",
              padding: "0.5rem 1rem",
              background: "var(--raised)",
              color: "var(--text)",
              border: "1px solid var(--stroke)",
              borderRadius: "0.375rem",
              cursor: "pointer",
            }}
          >
            Neu laden
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
