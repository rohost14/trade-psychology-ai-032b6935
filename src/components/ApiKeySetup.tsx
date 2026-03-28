import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { ExternalLink, Key, ChevronRight, CheckCircle2, AlertCircle } from "lucide-react";
import api from "@/lib/api";

// Steps shown to guide the user through creating a KiteConnect app
const STEPS = [
  {
    n: 1,
    title: "Go to Zerodha Developer Console",
    body: (
      <>
        Visit{" "}
        <a
          href="https://developers.zerodha.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline text-primary inline-flex items-center gap-0.5"
        >
          developers.zerodha.com <ExternalLink className="h-3 w-3" />
        </a>{" "}
        and log in with your Zerodha credentials.
      </>
    ),
  },
  {
    n: 2,
    title: "Create a new app",
    body: 'Click "Create new app". Choose type "Connect". Give it any name (e.g. "TradeMentor Test").',
  },
  {
    n: 3,
    title: "Set the Redirect URL",
    body: (
      <>
        In the <strong>Redirect URL</strong> field, enter exactly:
        <code className="block mt-1 rounded bg-muted px-2 py-1 text-xs break-all">
          {window.location.origin.replace(/^http:/, "https:")}
          /api/zerodha/callback
        </code>
        Replace the origin with your deployment URL if needed.
      </>
    ),
  },
  {
    n: 4,
    title: "Copy your API Key & Secret",
    body: 'After saving, the dashboard shows your "API key" and "API secret". Copy both and paste them below.',
  },
];

interface Props {
  /** Called after OAuth redirect is initiated */
  onRedirecting?: () => void;
  /** Trigger element — defaults to a styled button */
  trigger?: React.ReactNode;
}

export default function ApiKeySetup({ onRedirecting, trigger }: Props) {
  const [open, setOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const { toast } = useToast();

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await api.post("/api/zerodha/setup-credentials", {
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim(),
      });
      return res.data.setup_token as string;
    },
    onSuccess: async (setupToken) => {
      try {
        const res = await api.get("/api/zerodha/connect", {
          params: { setup_token: setupToken },
        });
        const { login_url } = res.data;
        if (login_url) {
          setOpen(false);
          onRedirecting?.();
          window.location.href = login_url;
        }
      } catch {
        toast({
          title: "Failed to generate login URL",
          description: "Check your API key and try again.",
          variant: "destructive",
        });
      }
    },
    onError: (e: any) => {
      toast({
        title: "Invalid credentials",
        description: e.response?.data?.detail || "Check your API key and secret.",
        variant: "destructive",
      });
    },
  });

  const canSubmit = apiKey.trim().length > 4 && apiSecret.trim().length > 4;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" className="gap-2">
            <Key className="h-4 w-4" />
            Use your own API key
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Key className="h-5 w-5 text-primary" />
            Connect with your own KiteConnect app
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5 pt-1">
          {/* Why banner */}
          <div className="rounded-lg border bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800 px-4 py-3 text-sm text-amber-800 dark:text-amber-300 flex gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>
              Until TradeMentor receives official Zerodha partnership, each tester needs
              their own free KiteConnect app. Takes ~2 minutes.
            </span>
          </div>

          {/* Step-by-step instructions */}
          <div className="space-y-3">
            <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Setup Instructions
            </p>
            {STEPS.map((step) => (
              <div key={step.n} className="flex gap-3">
                <div className="shrink-0 mt-0.5">
                  <Badge
                    variant="outline"
                    className="h-5 w-5 rounded-full p-0 flex items-center justify-center text-[10px] font-bold"
                  >
                    {step.n}
                  </Badge>
                </div>
                <div className="space-y-0.5">
                  <p className="text-sm font-medium">{step.title}</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">{step.body}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Divider */}
          <hr className="border-border" />

          {/* Credential inputs */}
          <div className="space-y-4">
            <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Your credentials
            </p>

            <div className="space-y-1.5">
              <Label>API Key</Label>
              <Input
                placeholder="e.g. abcdefgh12345678"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete="off"
              />
            </div>

            <div className="space-y-1.5">
              <Label>API Secret</Label>
              <Input
                type="password"
                placeholder="Your KiteConnect app secret"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                autoComplete="new-password"
              />
              <p className="text-xs text-muted-foreground">
                Stored encrypted. Never shared. Used only to complete the one-time OAuth handshake.
              </p>
            </div>
          </div>

          <Button
            className="w-full gap-2"
            disabled={!canSubmit || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? (
              "Connecting..."
            ) : (
              <>
                <ChevronRight className="h-4 w-4" />
                Connect to Zerodha
              </>
            )}
          </Button>

          {/* Security note */}
          <p className="text-center text-[10px] text-muted-foreground">
            <CheckCircle2 className="inline h-3 w-3 mr-0.5" />
            Your API secret is encrypted at rest using Fernet symmetric encryption and is
            never logged or transmitted in plaintext.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
