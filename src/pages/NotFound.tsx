import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Compass, LayoutDashboard, LifeBuoy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { supportMailto } from "@/lib/support";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground px-6">
      <div className="w-full max-w-md text-center">
        <div className="w-14 h-14 mx-auto mb-5 rounded-2xl bg-[rgb(var(--tm-brand))]/10 flex items-center justify-center">
          <Compass className="h-7 w-7 text-[rgb(var(--tm-brand))]" />
        </div>

        <p className="text-5xl font-bold tracking-tight text-foreground">404</p>
        <h1 className="mt-2 text-lg font-semibold text-foreground">This page doesn’t exist</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          The link may be broken, or the page may have moved. Let’s get you back on track.
        </p>

        {location.pathname && (
          <p className="mt-3 text-[11px] font-mono text-muted-foreground/70 break-all">
            {location.pathname}
          </p>
        )}

        <div className="mt-6 flex items-center justify-center gap-2.5">
          <Button asChild>
            <Link to="/dashboard"><LayoutDashboard className="h-4 w-4" /> Back to Dashboard</Link>
          </Button>
          <a
            href={supportMailto({ subject: "TradeMentor — broken link", ref: location.pathname })}
            className="inline-flex items-center gap-2 px-4 py-2 border border-border rounded-md text-sm text-foreground hover:bg-accent/20"
          >
            <LifeBuoy className="h-4 w-4" /> Report it
          </a>
        </div>
      </div>
    </div>
  );
};

export default NotFound;
