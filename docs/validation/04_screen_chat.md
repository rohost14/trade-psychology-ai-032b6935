# Screen 04: Chat (AI Coach)
*Route: `/chat` | File: `src/pages/Chat.tsx`*

---

## Purpose
Conversational AI trading coach. Trader asks questions about their own trading data — the AI has full context (today's P&L, open positions, active alerts, risk state) and responds with specific, personalized advice. Not generic financial advice; grounded in the trader's actual session.

---

## Layout

```
┌────────────────────────────────────────────────────────┐
│  Header: "AI Trading Coach" + persona indicator        │
├────────────────────────────────────────────────────────┤
│                                                        │
│  [Chat messages area — scrollable]                     │
│                                                        │
│  [AI message] "You've had 3 losses in a row..."       │
│  [User message] "Should I keep trading?"               │
│  [AI message — streaming] "Given your current..."      │
│                                                        │
├────────────────────────────────────────────────────────┤
│  Suggested follow-up chips (context-aware)             │
│  [What's my win rate?] [Any revenge trades?]           │
├────────────────────────────────────────────────────────┤
│  [Text input] [Send button]                            │
└────────────────────────────────────────────────────────┘
```

---

## Features

### Session Restore
- **API**: `GET /api/coach/session/today` → `{messages: [{role, content}], snapshot}`
- On mount: loads today's session from DB (`CoachSession` model)
- If no session today: fresh start with AI greeting using today's trading snapshot
- **Snapshot** injected into system prompt: P&L, trade count, active alerts, risk state, open positions count
- **Validation**: ✅ Session boundary is IST date (not UTC)

### Streaming Responses
- **API**: `POST /api/coach/chat/stream` → Server-Sent Events stream
- Frontend uses `EventSource` / fetch with `ReadableStream`
- AI response streams token by token (not buffered)
- **Model**: Claude Haiku via OpenRouter (fast, cheap, capable)
- **Validation**: ✅ Stream aborted on component unmount (no dangling connections)

### Context-Aware Follow-up Chips
- Generated after each AI response
- Examples: "Tell me more about this pattern", "What should I do now?", "Show me my worst trade"
- Click a chip → auto-populates input and sends
- **Validation**: ✅ Chips reset after each exchange

### Save to Journal
- Any AI message has a "Save insight" button
- **API**: `POST /api/coach/save-insight` → saves to `JournalEntry` with `notes=<ai_message>`
- **Validation**: ✅ Saved insights retrievable in journal entries

### AI Persona
Configured in Settings → Profile → AI Persona:
- `strict_mentor` — Direct, no sugar-coating
- `supportive_coach` — Empathetic, encourages
- `data_analyst` — Numbers-focused, minimal emotion
- `zen_master` — Calm, philosophical

7 absolute rules injected regardless of persona:
1. Never give buy/sell recommendations
2. Never promise future returns
3. Always refer to the user's actual data
4. Flag when user is in DANGER zone explicitly
5. Never diagnose mental health conditions
6. Stay within trading psychology scope
7. No legal/tax advice

---

## APIs Called

| Endpoint | When | Purpose |
|----------|------|---------|
| `GET /api/coach/session/today` | Mount | Load/restore today's chat |
| `POST /api/coach/chat/stream` | Send message | Streaming AI response |
| `POST /api/coach/save-insight` | Save button | Save AI message to journal |
| `GET /api/coach/insights` | Optional | List saved insights |

---

## AI Context Injected into System Prompt

```
Today's session (IST):
- Trades: {count} ({wins}W / {losses}L)
- Realized P&L: ₹{realized_pnl}
- Open positions: {open_count}
- Active alerts: {alert_count} ({highest_severity})
- Risk state: {safe|caution|danger}
- Consecutive losses: {n}
- Active cooldown: {yes/no, minutes remaining}
- Trader profile: {experience_level}, {risk_tolerance}, {capital}
- AI persona: {persona}
```

---

## State Management

```
Local component:
  messages: Message[]        — chat history
  input: string              — current text
  isStreaming: boolean        — SSE in progress
  suggestedChips: string[]   — follow-up suggestions
BrokerContext: brokerAccountId
```

---

## Validation Checklist

- [x] Session restores correctly on page revisit (today's messages preserved)
- [x] Streaming displays tokens progressively, not all at once
- [x] AI never gives buy/sell advice (7 absolute rules in system prompt)
- [x] AI grounded in actual trading data — not generic responses
- [x] Persona setting from Settings actually changes tone/style
- [x] Save insight writes to journal (not lost)
- [x] Stream aborts cleanly on unmount / navigation away
- [x] IST session boundary (new session starts at midnight IST, not UTC)
- [x] No trade data leakage to other accounts (auth-scoped)
