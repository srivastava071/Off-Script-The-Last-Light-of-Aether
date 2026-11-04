import { Component, type ErrorInfo, type ReactNode } from "react";

/** Shows a readable message instead of a blank page if a screen fails to render. */
export class ErrorBoundary extends Component<{ children: ReactNode; onReset: () => void }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Screen crashed:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto max-w-lg px-4 py-24 text-center">
        <h1 className="font-display text-2xl text-amber">Something went wrong on this screen</h1>
        <p className="mt-3 text-muted">
          The game server may be an older version than this page. Restart the backend, then try again.
        </p>
        <p className="mt-2 font-mono text-xs text-danger">{this.state.error.message}</p>
        <button className="mt-6 rounded-lg bg-amber px-4 py-2 text-ink"
          onClick={() => { this.setState({ error: null }); this.props.onReset(); }}>
          Back to the main menu
        </button>
      </div>
    );
  }
}
