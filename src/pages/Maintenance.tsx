import { Wrench } from "lucide-react";

interface MaintenanceProps {
  message?: string;
}

const DEFAULT_MESSAGE = "We're performing scheduled maintenance. Back in a few minutes.";

// /maintenance is public and unauthenticated. Reflecting a caller-supplied
// ?message= turned it into a phishing surface ("Account suspended, call …") —
// React escapes it so there is no XSS, but the text is still attacker-chosen.
// Only a fixed set of known reasons is accepted from the URL now.
const ALLOWED_REASONS: Record<string, string> = {
  scheduled: DEFAULT_MESSAGE,
  deploy: "We're rolling out an update. Back in a few minutes.",
  broker: "Zerodha's API is unavailable right now. Trading data will resume once it recovers.",
  incident: "We're investigating an issue. Service will resume shortly.",
};

const Maintenance = ({ message }: MaintenanceProps) => {
  // A prop passed by the app itself is trusted; the query string is not.
  const reason = new URLSearchParams(window.location.search).get("reason") ?? "";
  const displayMessage = message || ALLOWED_REASONS[reason] || DEFAULT_MESSAGE;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground px-4">
      <div className="flex flex-col items-center gap-6 max-w-md text-center">
        <div className="p-4 rounded-full bg-amber-500/10 text-amber-500">
          <Wrench className="h-10 w-10" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold mb-2">Maintenance in Progress</h1>
          <p className="text-muted-foreground">{displayMessage}</p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="text-sm text-amber-500 underline underline-offset-4 hover:text-amber-400"
        >
          Retry
        </button>
      </div>
    </div>
  );
};

export default Maintenance;
