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

createRoot(document.getElementById("root")!).render(<App />);
