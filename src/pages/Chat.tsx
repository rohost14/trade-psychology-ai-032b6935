import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send,
  Bot,
  User,
  Sparkles,
  Link2,
  Trash2,
  RefreshCw,
  BookmarkPlus,
  Check,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Shield,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import { api, fetchWithAuth } from '@/lib/api';
import DOMPurify from 'dompurify';
import ComplianceDisclaimer from '@/components/ComplianceDisclaimer';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  saved?: boolean;
}

interface Snapshot {
  trades_today: number;
  pnl_today: number;
  active_alerts: number;
  risk_state: 'safe' | 'caution' | 'danger';
}

const INITIAL_CHIPS = [
  "What's my biggest trading mistake?",
  "What patterns are hurting my P&L the most?",
  "Analyze my recent trading patterns",
  "What time of day am I most profitable?",
  "What does my journal say about my emotions?",
  "Why do I keep overtrading?",
];

function getContextChips(lastMessage: string): string[] {
  const lower = lastMessage.toLowerCase();
  const chips: string[] = [];

  if (lower.includes('revenge') || lower.includes('impulsive') || lower.includes('emotional')) {
    chips.push('Give me a rule to stop revenge trading');
  }
  if (lower.includes('loss') || lower.includes('losing') || lower.includes('down')) {
    chips.push('How do I bounce back from a losing streak?');
  }
  if (lower.includes('overtrad') || lower.includes('too many')) {
    chips.push('How many trades should I take per day?');
  }
  if (lower.includes('pattern') || lower.includes('habit') || lower.includes('behavior')) {
    chips.push("What's my highest-cost pattern?");
  }
  if (
    lower.includes('banknifty') ||
    lower.includes('nifty') ||
    lower.includes('option') ||
    lower.includes('symbol')
  ) {
    chips.push('Analyze my options trading');
  }
  if (lower.includes('win rate') || lower.includes('profitable') || lower.includes('best')) {
    chips.push('What setup has my best win rate?');
  }

  const fallbacks = ['Tell me more', 'What should I do next?', 'Give me a specific action'];
  for (const fb of fallbacks) {
    if (chips.length >= 3) break;
    chips.push(fb);
  }
  return chips.slice(0, 3);
}

function formatMessage(content: string): JSX.Element {
  const lines = content.split('\n');
  return (
    <div className="space-y-1.5">
      {lines.map((line, idx) => {
        const formattedLine = line.replace(
          /\*\*(.*?)\*\*/g,
          '<strong class="font-semibold text-foreground">$1</strong>'
        );

        if (line.trim().startsWith('- ') || line.trim().startsWith('• ')) {
          return (
            <div key={idx} className="flex gap-2 ml-2">
              <span className="text-primary mt-0.5 flex-shrink-0">•</span>
              <span
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(formattedLine.replace(/^[-•]\s*/, '')),
                }}
              />
            </div>
          );
        }

        const numberedMatch = line.trim().match(/^(\d+)[.)]\s*(.*)/);
        if (numberedMatch) {
          const lineContent = numberedMatch[2].replace(
            /\*\*(.*?)\*\*/g,
            '<strong class="font-semibold">$1</strong>'
          );
          return (
            <div key={idx} className="flex gap-2 ml-2">
              <span className="text-primary font-medium flex-shrink-0">{numberedMatch[1]}.</span>
              <span dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(lineContent) }} />
            </div>
          );
        }

        if (!line.trim()) return <div key={idx} className="h-1.5" />;

        return (
          <p key={idx} className="text-inherit" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(formattedLine) }} />
        );
      })}
    </div>
  );
}

export default function Chat() {
  const { isConnected, account } = useBroker();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const loadingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Tracks IDs of messages loaded from DB on session restore — skip their mount animation
  const restoredIdsRef = useRef<Set<string>>(new Set());

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  }, [input]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup on unmount: cancel any in-flight stream and pending timeout
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);
    };
  }, []);

  // Restore today's session + snapshot on mount
  useEffect(() => {
    if (!isConnected || !account) return;

    const restore = async () => {
      try {
        const { data } = await api.get('/api/coach/session/today');
        if (data.messages?.length > 0) {
          const restored = data.messages.map(
            (m: { role: string; content: string; ts?: string }, i: number) => ({
              id: m.ts || `restored-${i}`,
              role: m.role as 'user' | 'assistant',
              content: m.content,
              timestamp: new Date(m.ts || Date.now()),
            })
          );
          restoredIdsRef.current = new Set(restored.map((m: Message) => m.id));
          setMessages(restored);
        }
        if (data.snapshot) {
          setSnapshot(data.snapshot);
        }
      } catch {
        // Non-critical — start fresh
      }
    };

    restore();
  }, [isConnected, account?.id]);

  // Focus textarea on connect
  useEffect(() => {
    if (isConnected) {
      textareaRef.current?.focus();
    }
  }, [isConnected]);

  const handleSend = useCallback(
    async (content: string) => {
      if (!content.trim() || !account || isLoading) return;

      if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);
      // Cancel any in-progress stream before starting a new one
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: content.trim(),
        timestamp: new Date(),
      };

      const aiMessageId = `ai-${Date.now()}`;
      const aiMessage: Message = {
        id: aiMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMessage, aiMessage]);
      setInput('');
      setIsLoading(true);

      // 30s hard timeout
      loadingTimeoutRef.current = setTimeout(() => {
        setIsLoading(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMessageId && m.isStreaming
              ? {
                  ...m,
                  isStreaming: false,
                  content: m.content || 'Request timed out. Please try again.',
                }
              : m
          )
        );
      }, 30000);

      try {
        // Cap history to last 10 messages before sending
        const history = messages
          .slice(-10)
          .map((m) => ({ role: m.role, content: m.content }));

        const response = await fetchWithAuth(`${API_URL}/api/coach/chat/stream`, {
          method: 'POST',
          signal: abortControllerRef.current.signal,
          body: JSON.stringify({ message: content.trim(), history }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulated = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const raw = decoder.decode(value, { stream: true });
          for (const line of raw.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6).trim();
            if (data === '[DONE]') break;
            try {
              const parsed = JSON.parse(data);
              const text = parsed.text || '';
              if (text) {
                accumulated += text;
                setMessages((prev) =>
                  prev.map((m) => (m.id === aiMessageId ? { ...m, content: accumulated } : m))
                );
              }
            } catch {
              // Ignore malformed SSE chunks
            }
          }
        }

        setMessages((prev) =>
          prev.map((m) => (m.id === aiMessageId ? { ...m, isStreaming: false } : m))
        );
      } catch (error) {
        // AbortError = intentional cancel (unmount or new request) — don't show error UI
        if (error instanceof Error && error.name === 'AbortError') return;
        console.error('Stream error:', error);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMessageId
              ? {
                  ...m,
                  isStreaming: false,
                  content: m.content || 'Sorry, I had trouble processing that. Please try again.',
                }
              : m
          )
        );
      } finally {
        if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);
        setIsLoading(false);
        textareaRef.current?.focus();
      }
    },
    [account, isLoading, messages]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  const handleSaveInsight = async (message: Message) => {
    if (message.saved) return;
    try {
      await api.post('/api/coach/save-insight', { content: message.content });
      setMessages((prev) => prev.map((m) => (m.id === message.id ? { ...m, saved: true } : m)));
    } catch {
      // Silently fail
    }
  };

  const handleClearChat = async () => {
    setMessages([]);
    try {
      await api.delete('/api/coach/session/today');
    } catch {
      // Non-critical — local state already cleared
    }
  };

  const lastAIMessage = messages.findLast((m) => m.role === 'assistant' && !m.isStreaming);
  const contextChips = lastAIMessage ? getContextChips(lastAIMessage.content) : INITIAL_CHIPS;

  if (!isConnected || !account) {
    return (
      <div className="max-w-3xl mx-auto h-[calc(100vh-8rem)]">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">AI Coach</h1>
          <p className="text-sm text-muted-foreground">
            Get personalized trading advice based on your behavior
          </p>
        </div>
        <div className="flex flex-col items-center justify-center h-[60%] bg-card rounded-xl border border-border shadow-sm">
          <div className="p-5 rounded-full bg-primary/10 mb-6 shadow-inner">
            <Link2 className="h-12 w-12 text-primary" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">Connect Your Broker</h2>
          <p className="text-muted-foreground text-center max-w-md mb-6">
            Connect your Zerodha account to chat with your AI trading coach.
          </p>
          <Link to="/settings">
            <Button size="lg" className="gap-2">
              <Link2 className="h-5 w-5" />
              Connect Zerodha
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Bot className="h-6 w-6 text-primary" />
            AI Coach
          </h1>
          <p className="text-sm text-muted-foreground">
            Personalized guidance from your real trading data
          </p>
        </div>
        {messages.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleClearChat}
            className="gap-2 text-muted-foreground hover:text-foreground"
          >
            <Trash2 className="h-4 w-4" />
            Clear
          </Button>
        )}
      </div>

      {/* Chat Container */}
      <div className="bg-card rounded-xl shadow-sm border border-border flex flex-col h-[calc(100%-4rem)] overflow-hidden">

        {/* Session Snapshot Bar */}
        {snapshot && (
          <div className="px-4 py-2 border-b border-border/60 bg-muted/20 flex items-center gap-3 text-xs flex-wrap">
            <span className="font-medium text-muted-foreground">Today</span>
            <span
              className={cn(
                'font-semibold flex items-center gap-0.5',
                snapshot.pnl_today >= 0 ? 'text-green-500' : 'text-red-500'
              )}
            >
              {snapshot.pnl_today >= 0 ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {snapshot.pnl_today >= 0 ? '+' : ''}₹{Math.abs(snapshot.pnl_today).toFixed(0)}
            </span>
            <span className="text-muted-foreground">
              {snapshot.trades_today} trade{snapshot.trades_today !== 1 ? 's' : ''}
            </span>
            {snapshot.active_alerts > 0 && (
              <span className="text-amber-500 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                {snapshot.active_alerts} alert{snapshot.active_alerts !== 1 ? 's' : ''}
              </span>
            )}
            <span
              className={cn(
                'ml-auto px-2 py-0.5 rounded-full font-medium flex items-center gap-1',
                snapshot.risk_state === 'safe'
                  ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                  : snapshot.risk_state === 'caution'
                    ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                    : 'bg-red-500/10 text-red-600 dark:text-red-400'
              )}
            >
              <Shield className="h-3 w-3" />
              {snapshot.risk_state}
            </span>
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="p-5 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 shadow-inner mb-5">
                <Sparkles className="h-10 w-10 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Ask your AI Trading Coach
              </h3>
              <p className="text-sm text-muted-foreground mb-6 max-w-sm">
                I have access to your real trades, P&L, patterns, and journal. Ask me anything.
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {INITIAL_CHIPS.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => handleSend(question)}
                    className="px-3 py-2 text-sm bg-muted hover:bg-primary/10 text-foreground hover:text-primary rounded-lg transition-all border border-border hover:border-primary/40 hover:shadow-sm"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                  <div
                    key={message.id}
                    className={cn(
                      'flex gap-3 group',
                      !restoredIdsRef.current.has(message.id) && 'animate-fade-in-up',
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    )}
                  >
                    {/* AI avatar */}
                    {message.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-xl bg-primary/10 border border-primary/20 flex-shrink-0 flex items-center justify-center mt-0.5">
                        <Bot className="h-4 w-4 text-primary" />
                      </div>
                    )}

                    <div
                      className={cn(
                        'flex flex-col gap-1',
                        message.role === 'user'
                          ? 'items-end max-w-[78%]'
                          : 'items-start max-w-[85%]'
                      )}
                    >
                      {/* Bubble */}
                      <div
                        className={cn(
                          'px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm',
                          message.role === 'user'
                            ? 'bg-primary text-primary-foreground rounded-tr-sm'
                            : 'bg-card border border-zinc-200 dark:border-zinc-700 text-foreground rounded-tl-sm'
                        )}
                      >
                        {message.role === 'assistant' ? (
                          <>
                            {formatMessage(message.content)}
                            {message.isStreaming && (
                              <span className="inline-flex gap-0.5 ml-1 align-middle">
                                <span className="w-1 h-1 bg-primary/50 rounded-full animate-bounce" />
                                <span className="w-1 h-1 bg-primary/50 rounded-full animate-bounce [animation-delay:0.1s]" />
                                <span className="w-1 h-1 bg-primary/50 rounded-full animate-bounce [animation-delay:0.2s]" />
                              </span>
                            )}
                          </>
                        ) : (
                          <p className="text-inherit">{message.content}</p>
                        )}
                      </div>

                      {/* Message footer: timestamp + save button (visible on hover) */}
                      <div
                        className={cn(
                          'flex items-center gap-2 px-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150',
                          message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                        )}
                      >
                        <span className="text-[10px] text-muted-foreground">
                          {message.timestamp.toLocaleTimeString('en-IN', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                        {message.role === 'assistant' &&
                          !message.isStreaming &&
                          message.content && (
                            <button
                              onClick={() => handleSaveInsight(message)}
                              className={cn(
                                'flex items-center gap-1 text-[10px] transition-colors',
                                message.saved
                                  ? 'text-green-500 cursor-default'
                                  : 'text-muted-foreground hover:text-primary cursor-pointer'
                              )}
                            >
                              {message.saved ? (
                                <>
                                  <Check className="h-3 w-3" />
                                  Saved
                                </>
                              ) : (
                                <>
                                  <BookmarkPlus className="h-3 w-3" />
                                  Save to Journal
                                </>
                              )}
                            </button>
                          )}
                      </div>
                    </div>

                    {/* User avatar */}
                    {message.role === 'user' && (
                      <div className="w-8 h-8 rounded-xl bg-secondary border border-border flex-shrink-0 flex items-center justify-center mt-0.5">
                        <User className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                ))}

              {/* Stand-alone typing indicator (only before first stream chunk arrives) */}
              {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-xl bg-primary/10 border border-primary/20 flex-shrink-0 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                  <div className="bg-muted border border-border px-4 py-3 rounded-2xl rounded-tl-sm">
                    <div className="flex gap-1.5 items-center h-4">
                      <span className="w-1.5 h-1.5 bg-muted-foreground/40 rounded-full animate-bounce" />
                      <span className="w-1.5 h-1.5 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0.15s]" />
                      <span className="w-1.5 h-1.5 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0.3s]" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Context-aware follow-up chips */}
        {messages.length > 0 && lastAIMessage && !isLoading && (
          <div className="px-4 pb-2 pt-1">
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
              {contextChips.map((chip, idx) => (
                <button
                  key={`${lastAIMessage.id}-${idx}`}
                  onClick={() => handleSend(chip)}
                  disabled={isLoading}
                  className="px-3 py-1.5 text-xs bg-muted hover:bg-primary/10 text-muted-foreground hover:text-primary rounded-full transition-all border border-border hover:border-primary/40 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="p-4 border-t border-border/60 bg-muted/10">
          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your trading patterns…"
              aria-label="Message to AI coach"
              rows={1}
              className="flex-1 px-4 py-2.5 bg-muted rounded-xl text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none overflow-y-auto min-h-[42px] max-h-[160px] leading-relaxed disabled:opacity-60"
              disabled={isLoading}
            />
            <Button
              onClick={() => handleSend(input)}
              disabled={!input.trim() || isLoading}
              size="icon"
              aria-label={isLoading ? 'Sending…' : 'Send message'}
              className="h-[42px] w-[42px] rounded-xl flex-shrink-0 shadow-sm"
            >
              {isLoading ? (
                <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="h-4 w-4" aria-hidden="true" />
              )}
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground mt-1.5 text-right select-none">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Compliance disclaimer */}
      <ComplianceDisclaimer className="mt-3" />
    </div>
  );
}
