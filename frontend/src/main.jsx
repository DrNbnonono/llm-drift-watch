import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";
import "./i18n/index.js";
import "./styles.css";

// 初始化外观:在 React 挂载前应用 localStorage 里的 theme / density,
// 避免首屏闪烁 (FOUC)。
(function applyAppearance() {
  if (typeof window === "undefined") return;
  try {
    const theme = window.localStorage.getItem("qb_theme") || "slate";
    const density = window.localStorage.getItem("qb_density") || "cozy";
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("data-density", density);
  } catch (err) {
    /* noop */
  }
})();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
