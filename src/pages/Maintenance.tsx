import { Wrench } from "lucide-react";

interface MaintenanceProps {
  message?: string;
}

const Maintenance = ({ message }: MaintenanceProps) => {
  const displayMessage =
    message ||
    new URLSearchParams(window.location.search).get("message") ||
    "We're performing scheduled maintenance. Back in a few minutes.";

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
