import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Send, TrendingUp, TrendingDown, Wallet, PieChart,
  RefreshCw, Bot, User, Briefcase, ChevronRight, History,
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import ComplianceDisclaimer from "@/components/ComplianceDisclaimer";
import api, { AUTH_TOKEN_KEY } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────────────────

interface PortfolioSnapshot {
  as_of: string | null;
  synced: boolean;
  holdings_summary: {
    count: number;
    total_invested: number;
    current_value: number;
    total_pnl: number;
    total_pnl_pct: number;
  };
  holdings: any[];
  mf_holdings: any[];
  sector_exposure: Record<string, { value: number; pct: number }>;
}

interface LastSession {
  id: string;
  summary: string | null;
  message_count: number;
  started_at: string;
  messages: { role: string; content: string; timestamp: string }[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const STARTER_PROMPTS = [
  "Give me a full portfolio summary — value, P&L, top gainers and losers",
  "Am I over-concentrated in any stock or sector vs Nifty 50?",
  "Which holdings should I sell before 1 year to save on tax?",
  "Do a tax-loss harvesting analysis — which losses can I book to offset gains?",
  "Analyse my mutual funds — any overlapping categories or high expense ratios?",
  "Which of my stocks are already LTCG and what's my estimated tax if I sell today?",
  "Should I rebalance? Compare my sector weights to Nifty 50",
  "How much cash and margin do I have available?",
];

function fmt(n: number) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Math.abs(n));
}

// ── Sector Bar ────────────────────────────────────────────────────────────────

function SectorBar({ sector, value, pct, max }: { sector: string; value: number; pct: number; max: number }) {
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{sector}</span>
        <span className="font-medium">{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${(pct / max) * 100}%` }}
        />
      </div>
    </div>
  );
}

// ── Portfolio Panel ───────────────────────────────────────────────────────────

function PortfolioPanel({ snapshot, isLoading, onRefresh }: {
  snapshot: PortfolioSnapshot | undefined;
  isLoading: boolean;
  onRefresh: () => void;
}) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
    );
  }

  if (!snapshot || !snapshot.synced) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <Briefcase className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
          <p className="text-sm font-medium">Syncing your portfolio…</p>
          <p className="text-xs text-muted-foreground mt-1">
            This takes a moment on first visit
          </p>
          <Button size="sm" variant="outline" className="mt-3 gap-2" onClick={onRefresh}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { holdings_summary: hs, sector_exposure, holdings, mf_holdings } = snapshot;
  const isPnlPos = hs.total_pnl >= 0;
  const sectorEntries = Object.entries(sector_exposure);
  const maxPct = sectorEntries.length ? Math.max(...sectorEntries.map(([, v]) => v.pct)) : 1;

  return (
    <div className="space-y-3">
      {/* Overall P&L card */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-muted-foreground">Portfolio Value</span>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onRefresh} title="Refresh">
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="text-2xl font-bold">₹{fmt(hs.current_value)}</div>
          <div className="flex items-center gap-2 mt-1">
            {isPnlPos ? (
              <TrendingUp className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5 text-red-500" />
            )}
            <span className={cn("text-sm font-medium", isPnlPos ? "text-green-600" : "text-red-600")}>
              {isPnlPos ? "+" : "-"}₹{fmt(hs.total_pnl)} ({isPnlPos ? "+" : ""}{hs.total_pnl_pct.toFixed(2)}%)
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Invested ₹{fmt(hs.total_invested)} · {hs.count} stocks
          </div>
          {mf_holdings.length > 0 && (
            <div className="text-xs text-muted-foreground">
              +{mf_holdings.length} mutual funds
            </div>
          )}
        </CardContent>
      </Card>

      {/* Sector exposure */}
      {sectorEntries.length > 0 && (
        <Card>
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <PieChart className="h-4 w-4" /> Sector Exposure
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {sectorEntries.slice(0, 6).map(([sector, data]) => (
              <SectorBar key={sector} sector={sector} value={data.value} pct={data.pct} max={maxPct} />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Top holdings */}
      {holdings.length > 0 && (
        <Card>
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm">Top Holdings</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {holdings.slice(0, 5).map((h: any) => {
              const pnl = h.unrealized_pnl || 0;
              const pos = pnl >= 0;
              return (
                <div key={h.tradingsymbol} className="flex items-center justify-between">
                  <div>
                    <div className="text-xs font-medium">{h.tradingsymbol}</div>
                    <div className="text-[10px] text-muted-foreground">{h.quantity} shares</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-medium">₹{fmt(h.ltp * h.quantity)}</div>
                    <div className={cn("text-[10px]", pos ? "text-green-600" : "text-red-600")}>
                      {pos ? "+" : "-"}₹{fmt(pnl)}
                    </div>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Synced time */}
      {snapshot.as_of && (
        <p className="text-[10px] text-muted-foreground text-center">
          Portfolio data synced {new Date(snapshot.as_of).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
        </p>
      )}
    </div>
  );
}

// ── Chat Bubble ───────────────────────────────────────────────────────────────

function ChatBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}>
      <div className={cn(
        "shrink-0 h-7 w-7 rounded-full flex items-center justify-center mt-1",
        isUser ? "bg-primary text-primary-foreground" : "bg-muted"
      )}>
        {isUser ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
      </div>
      <div className={cn(
        "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm",
        isUser
          ? "bg-primary text-primary-foreground rounded-tr-sm"
          : "bg-muted rounded-tl-sm"
      )}>
        <p className="whitespace-pre-wrap leading-relaxed text-inherit">{msg.content}</p>
        <p className={cn("text-[10px] mt-1", isUser ? "text-primary-foreground/60" : "text-muted-foreground")}>
          {new Date(msg.timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PortfolioChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch portfolio snapshot (reads Redis cache — no API polling)
  const {
    data: snapshot,
    isLoading: snapshotLoading,
    refetch: refetchSnapshot,
  } = useQuery<PortfolioSnapshot>({
    queryKey: ["portfolio-snapshot"],
    queryFn: async () => (await api.get("/api/portfolio-chat/snapshot")).data,
    staleTime: 5 * 60 * 1000, // Don't refetch within 5 min
    refetchOnWindowFocus: false,
  });

  // Fetch last session for flashback card
  const { data: lastSession } = useQuery<LastSession | null>({
    queryKey: ["portfolio-last-session"],
    queryFn: async () => (await api.get("/api/portfolio-chat/session")).data,
    staleTime: Infinity,
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isStreaming) return;
    setInput("");

    const userMsg: Message = { role: "user", content: text.trim(), timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setIsStreaming(true);

    // Placeholder for streaming response
    const assistantMsg: Message = { role: "assistant", content: "", timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, assistantMsg]);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/portfolio-chat/message`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${localStorage.getItem(AUTH_TOKEN_KEY)}`,
          },
          body: JSON.stringify({
            message: text.trim(),
            history: messages.map(m => ({ role: m.role, content: m.content })),
            session_id: sessionId,
          }),
        }
      );

      if (!response.ok || !response.body) throw new Error("Stream failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        const lines = text.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          if (data === "[DONE]") break;
          try {
            const parsed = JSON.parse(data);
            if (parsed.content) {
              accumulated += parsed.content;
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = { ...updated[updated.length - 1], content: accumulated };
                return updated;
              });
            }
          } catch {}
        }
      }
    } catch (e) {
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: "Sorry, I couldn't get a response. Please try again.",
        };
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  const showEmpty = messages.length === 0;

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-[calc(100vh-4rem)] p-4">
      {/* Left panel — portfolio snapshot */}
      <div className="lg:w-72 xl:w-80 shrink-0">
        <ScrollArea className="h-full pr-1">
          <PortfolioPanel
            snapshot={snapshot}
            isLoading={snapshotLoading}
            onRefresh={() => refetchSnapshot()}
          />
        </ScrollArea>
      </div>

      {/* Right panel — chat */}
      <div className="flex-1 flex flex-col min-h-0 rounded-2xl border bg-background overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b flex items-center gap-2 shrink-0">
          <Bot className="h-5 w-5 text-primary" />
          <div>
            <h2 className="text-sm font-semibold">Portfolio AI</h2>
            <p className="text-[10px] text-muted-foreground">Analysis only · No investment advice</p>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 px-4 py-4">
          {showEmpty ? (
            <div className="h-full flex flex-col justify-center gap-6">
              {/* Flashback card */}
              {lastSession && lastSession.summary && (
                <Card className="border-dashed">
                  <CardContent className="p-4 flex gap-3 items-start">
                    <History className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-muted-foreground">Last conversation</p>
                      <p className="text-sm mt-0.5 line-clamp-2">{lastSession.summary}</p>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 mt-1 text-xs"
                        onClick={() => {
                          const restored = (lastSession.messages || []).map(m => ({
                            ...m,
                            role: m.role as "user" | "assistant",
                          }));
                          setMessages(restored);
                          setSessionId(lastSession.id);
                        }}
                      >
                        Continue conversation <ChevronRight className="h-3 w-3" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Starter prompts */}
              <div className="text-center space-y-3">
                <Bot className="h-10 w-10 mx-auto text-muted-foreground" />
                <p className="text-sm font-medium">Ask anything about your portfolio</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {STARTER_PROMPTS.map(p => (
                    <button
                      key={p}
                      onClick={() => sendMessage(p)}
                      className="text-left text-xs rounded-xl border bg-muted/40 px-3 py-2.5 hover:bg-muted transition-colors"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)}
              {isStreaming && messages[messages.length - 1]?.content === "" && (
                <div className="flex gap-2.5">
                  <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                  <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* Input */}
        <div className="px-4 pb-4 pt-2 shrink-0 space-y-2">
          <div className="flex gap-2">
            <Textarea
              rows={1}
              placeholder="Ask about your portfolio…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage(input);
                }
              }}
              className="resize-none text-sm min-h-[40px] max-h-[120px]"
              disabled={isStreaming}
            />
            <Button
              size="icon"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isStreaming}
              className="shrink-0 h-10 w-10"
            >
              {isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <ComplianceDisclaimer variant="footer" />
        </div>
      </div>
    </div>
  );
}
