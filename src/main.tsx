import { createRoot } from "react-dom/client";
import * as Sentry from "@sentry/react";
import App from "./App.tsx";
import "./index.css";

// Initialise Sentry before rendering so all errors (including React render
// errors caught by ErrorBoundary) are captured.
// Set VITE_SENTRY_DSN in .env — safe to omit (no-op without a DSN).
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    // Capture 10% of page loads for performance tracing
    tracesSampleRate: 0.1,
    // Don't send PII
    sendDefaultPii: false,
  });
}

// Global unhandled Promise rejection safety net.
// Sentry captures these automatically when a DSN is configured.
// In dev, print a clear stack so missing .catch() handlers are easy to spot.
window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
  if (import.meta.env.DEV) {
    console.error('[UnhandledRejection] Promise rejected without a .catch() handler:', event.reason);
  }
  // When Sentry is active it already calls event.preventDefault() internally.
  // Without Sentry, swallow to avoid duplicate browser console noise for 401s
  // which are handled by the api.ts interceptor → tradementor:token-expired event.
  if (!import.meta.env.VITE_SENTRY_DSN) {
    const status = (event.reason as any)?.response?.status;
    if (status === 401 || status === 503) event.preventDefault();
  }
});

createRoot(document.getElementById("root")!).render(<App />);
