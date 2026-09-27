// BARA – React Error Boundary
// Prevents the entire app from going blank when a component throws.
import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[BARA] Uncaught render error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "var(--bg, #0f1117)",
            color: "var(--text, #e2e4ed)",
            fontFamily: "system-ui, sans-serif",
            padding: 32,
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>
            Something went wrong
          </h1>
          <p
            style={{
              color: "var(--muted, #8b92a9)",
              maxWidth: 480,
              marginBottom: 20,
              lineHeight: 1.6,
            }}
          >
            BARA encountered an unexpected error. This usually happens when the
            backend returns an unexpected response or a component failed to
            render.
          </p>
          <div
            style={{
              background: "rgba(224,82,82,.1)",
              border: "1px solid rgba(224,82,82,.35)",
              borderRadius: 8,
              padding: "12px 20px",
              color: "var(--red, #e05252)",
              fontSize: 13,
              fontFamily: "monospace",
              maxWidth: 600,
              wordBreak: "break-word",
              marginBottom: 24,
            }}
          >
            {this.state.error?.message ?? "Unknown error"}
          </div>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
            }}
            style={{
              background: "var(--accent, #4f7ef7)",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "10px 24px",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            ← Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
