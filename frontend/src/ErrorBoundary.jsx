import React from "react";

/**
 * A minimal Error Boundary used in development to surface
 * uncaught render errors instead of leaving the page blank.
 * In production this can be replaced with a silent fallback.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] caught:", error, info);
    this.setState({ info });
  }

  handleReset = () => {
    this.setState({ error: null, info: null });
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  };

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            margin: "1.5rem",
            padding: "1.25rem",
            border: "1px solid #b91c1c",
            background: "#fff5f5",
            color: "#7f1d1d",
            fontFamily: "system-ui, -apple-system, sans-serif",
            fontSize: "0.9rem",
            lineHeight: 1.5,
          }}
        >
          <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>前端渲染错误</h2>
          <p style={{ margin: "0.4rem 0" }}>页面遇到一个未捕获的错误。请尝试刷新或复制下面信息以便排查。</p>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              background: "rgba(0,0,0,0.04)",
              padding: "0.6rem",
              margin: "0.4rem 0",
              fontFamily: "IBM Plex Mono, monospace",
              fontSize: "0.78rem",
            }}
          >
            {String(this.state.error && this.state.error.stack || this.state.error)}
          </pre>
          {this.state.info ? (
            <pre
              style={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                background: "rgba(0,0,0,0.02)",
                padding: "0.6rem",
                margin: "0.4rem 0",
                fontFamily: "IBM Plex Mono, monospace",
                fontSize: "0.74rem",
                color: "#475569",
              }}
            >
              {String(this.state.info.componentStack || "")}
            </pre>
          ) : null}
          <button
            type="button"
            onClick={this.handleReset}
            style={{
              border: "1px solid #b91c1c",
              background: "#fff",
              color: "#7f1d1d",
              padding: "0.35rem 0.7rem",
              borderRadius: "2px",
              cursor: "pointer",
            }}
          >
            重新加载
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
