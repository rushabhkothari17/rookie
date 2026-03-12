import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress benign ResizeObserver loop notifications from the dev error overlay.
// This browser event is non-fatal and does not affect functionality.
window.addEventListener(
  "error",
  (e) => {
    if (
      e.message === "ResizeObserver loop completed with undelivered notifications." ||
      e.message === "ResizeObserver loop limit exceeded"
    ) {
      e.stopImmediatePropagation();
    }
  },
  true, // capture phase — runs before CRA's overlay handler
);

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
