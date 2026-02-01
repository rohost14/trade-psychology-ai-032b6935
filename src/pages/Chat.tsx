import { useState } from 'react';
import { Send, Bot, User, Sparkles, Link2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useBroker } from '@/contexts/BrokerContext';
import { api } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const suggestedQuestions = [
  "What's my biggest trading mistake?",
  "How can I improve my win rate?",
  "Analyze my recent trading patterns",
  "What time should I avoid trading?",
];

export default function Chat() {
  const { isConnected, account } = useBroker();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async (content: string) => {
    if (!content.trim() || !account) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Build chat history for context
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await api.post('/api/coach/chat', {
        message: content.trim(),
        broker_account_id: account.id,
        history,
      });

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I had trouble processing that. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  // Not connected state
  if (!isConnected || !account) {
    return (
      <div className="max-w-3xl mx-auto h-[calc(100vh-8rem)]">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">AI Coach</h1>
          <p className="text-sm text-muted-foreground">
            Get personalized trading advice based on your behavior
          </p>
        </div>
        <div className="flex flex-col items-center justify-center h-[60%] bg-card rounded-lg border border-border">
          <div className="p-4 rounded-full bg-primary/10 mb-6">
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
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">AI Coach</h1>
        <p className="text-sm text-muted-foreground">
          Get personalized trading advice based on your behavior
        </p>
      </div>

      {/* Chat Container */}
      <div className="bg-card rounded-lg shadow-sm border border-border flex flex-col h-[calc(100%-5rem)]">
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="p-4 rounded-full bg-primary/10 mb-4">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Ask your AI Trading Coach
              </h3>
              <p className="text-sm text-muted-foreground mb-6 max-w-md">
                I analyze your trading patterns and provide personalized insights to help you
                trade better.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {suggestedQuestions.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => handleSend(question)}
                    className="px-3 py-2 text-sm bg-muted hover:bg-muted/80 text-foreground rounded-lg transition-colors border border-border"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  'flex gap-3',
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                {message.role === 'assistant' && (
                  <div className="p-2 rounded-lg bg-primary/10 h-fit">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                <div
                  className={cn(
                    'max-w-[80%] p-4 rounded-lg',
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  )}
                >
                  <p className="text-sm">{message.content}</p>
                </div>
                {message.role === 'user' && (
                  <div className="p-2 rounded-lg bg-muted h-fit">
                    <User className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
            ))
          )}
          {isLoading && (
            <div className="flex gap-3 justify-start">
              <div className="p-2 rounded-lg bg-primary/10 h-fit">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <div className="bg-muted p-4 rounded-lg">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:0.1s]" />
                  <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:0.2s]" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <form onSubmit={handleSubmit} className="p-4 border-t border-border">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your trading patterns..."
              className="flex-1 px-4 py-2.5 bg-muted rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={isLoading}
            />
            <Button type="submit" disabled={!input.trim() || isLoading} className="gap-2">
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">Send</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
