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

// Also suppress via window.onerror to fully prevent CRA dev overlay from catching it
const _origOnError = window.onerror;
window.onerror = (msg, source, line, col, err) => {
  if (typeof msg === "string" && msg.includes("ResizeObserver")) {
    return true; // returning true suppresses the error
  }
  return _origOnError ? _origOnError(msg, source, line, col, err) : false;
};

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
