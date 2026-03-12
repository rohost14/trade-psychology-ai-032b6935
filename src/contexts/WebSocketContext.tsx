/**
 * WebSocketContext — single WebSocket connection per browser tab.
 *
 * Features:
 *   - ONE shared connection (no duplicate connections per component)
 *   - Event replay on reconnect: sends last_event_id → backend replays missed events
 *   - Handles: prices, trade updates, alert updates, position updates, margin updates
 *   - Persists last_event_id in localStorage so app open → closed → open gets full context
 *   - Exposes margins state — updated via WebSocket (no polling)
 *
 * Event replay flow:
 *   App closed → trade executes → stream:events + stream:{account_id} written
 *   App opens → WebSocket connects with ?since=last_event_id
 *   Backend: XREAD stream:{account_id} since last_event_id → sends replay messages
 *   Frontend: processes replay → refetches fresh data → UI up to date immediately
 */

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useBroker } from './BrokerContext';
import { api } from '@/lib/api';

const AUTH_TOKEN_KEY = 'tradementor_auth_token';
const LAST_EVENT_KEY_PREFIX = 'tradementor_last_event_';  // + account_id

interface PriceData {
  last_price: number;
  change?: number;
  change_percent?: number;
  instrument_token?: number;
}

interface TradeEvent {
  order_id?: string;
  status?: string;
  timestamp: string;
}

interface AlertEvent {
  count: number;
  has_danger: boolean;
  behavior_state?: string;
  timestamp: string;
}

interface WebSocketContextValue {
  prices: Record<string, PriceData>;
  margins: Record<string, unknown> | null;
  lastTradeEvent: TradeEvent | null;
  lastAlertEvent: AlertEvent | null;
  isConnected: boolean;
  subscribe: (instruments: string[]) => void;
  subscribeToPositions: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue>({
  prices: {},
  margins: null,
  lastTradeEvent: null,
  lastAlertEvent: null,
  isConnected: false,
  subscribe: () => {},
  subscribeToPositions: () => {},
});

export function useWebSocket() {
  return useContext(WebSocketContext);
}

const WS_RECONNECT_BASE = 3000;
const WS_RECONNECT_MAX = 60000;
const PING_INTERVAL = 30000;

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { account, isTokenExpired } = useBroker();
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [margins, setMargins] = useState<Record<string, unknown> | null>(null);
  const [lastTradeEvent, setLastTradeEvent] = useState<TradeEvent | null>(null);
  const [lastAlertEvent, setLastAlertEvent] = useState<AlertEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(WS_RECONNECT_BASE);
  const mountedRef = useRef(true);
  const pendingSubscriptions = useRef<string[]>([]);

  // last_event_id stored per account in localStorage for replay across app restarts
  const getLastEventId = useCallback((accountId: string) => {
    return localStorage.getItem(`${LAST_EVENT_KEY_PREFIX}${accountId}`) || '';
  }, []);

  const setLastEventId = useCallback((accountId: string, eventId: string) => {
    if (eventId) {
      localStorage.setItem(`${LAST_EVENT_KEY_PREFIX}${accountId}`, eventId);
    }
  }, []);

  const sendMessage = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const subscribe = useCallback((instruments: string[]) => {
    if (instruments.length === 0) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      sendMessage({ action: 'subscribe', instruments });
    } else {
      pendingSubscriptions.current = [...pendingSubscriptions.current, ...instruments];
    }
  }, [sendMessage]);

  const subscribeToPositions = useCallback(() => {
    sendMessage({ action: 'subscribe_positions' });
  }, [sendMessage]);

  const connect = useCallback(() => {
    if (!account?.id || isTokenExpired) return;

    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) return;

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const base = apiUrl.startsWith('http') ? apiUrl : window.location.origin + apiUrl;
      const url = new URL(base);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      url.pathname = '/api/ws/prices';
      url.searchParams.set('token', token);

      // Send last_event_id for replay — backend sends all missed events
      const lastEventId = getLastEventId(account.id);
      if (lastEventId) {
        url.searchParams.set('since', lastEventId);
      }

      const ws = new WebSocket(url.toString());
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        reconnectDelayRef.current = WS_RECONNECT_BASE;

        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'ping' }));
          }
        }, PING_INTERVAL);

        // Auto-subscribe to open position instruments
        ws.send(JSON.stringify({ action: 'subscribe_positions' }));

        // Flush pending subscriptions
        if (pendingSubscriptions.current.length > 0) {
          ws.send(JSON.stringify({ action: 'subscribe', instruments: pendingSubscriptions.current }));
          pendingSubscriptions.current = [];
        }
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const msg = JSON.parse(event.data);
          const ts = new Date().toISOString();

          switch (msg.type) {
            // ── Live price tick ───────────────────────────────────────────
            case 'price':
              if (msg.instrument && msg.data) {
                setPrices(prev => ({ ...prev, [msg.instrument]: msg.data }));
              }
              break;

            // ── Trade / position changed ──────────────────────────────────
            case 'trade':
            case 'trade_update':
            case 'position_update':
              setLastTradeEvent({ ...msg.data, timestamp: ts });
              if (msg.event_id && account?.id) {
                setLastEventId(account.id, msg.event_id);
              }
              break;

            // ── Alert fired ───────────────────────────────────────────────
            case 'alert':
            case 'alert_update':
              setLastAlertEvent({ ...msg.data, timestamp: ts });
              if (msg.event_id && account?.id) {
                setLastEventId(account.id, msg.event_id);
              }
              break;

            // ── Margin update (no polling needed) ─────────────────────────
            case 'margin_update':
              if (msg.data) {
                setMargins(msg.data);
              }
              if (msg.event_id && account?.id) {
                setLastEventId(account.id, msg.event_id);
              }
              break;

            // ── Replay: events missed while app was closed ────────────────
            case 'replay': {
              // Process each replayed event — same handling as live events
              const replayType = msg.event_type;
              if (replayType === 'trade_update' || replayType === 'position_update') {
                setLastTradeEvent({ ...msg.data, timestamp: ts });
              } else if (replayType === 'alert_update') {
                setLastAlertEvent({ ...msg.data, timestamp: ts });
              } else if (replayType === 'margin_update' && msg.data) {
                setMargins(msg.data);
              }
              // Track the latest replayed event ID
              if (msg.event_id && account?.id) {
                setLastEventId(account.id, msg.event_id);
              }
              break;
            }

            case 'replay_complete':
              // All missed events delivered — update cursor to latest
              if (msg.last_event_id && account?.id) {
                setLastEventId(account.id, msg.last_event_id);
              }
              break;

            // ignore: pong, subscribed, unsubscribed, error
          }
        } catch {
          // Malformed message — ignore
        }
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        if (pingRef.current) clearInterval(pingRef.current);

        if (event.code !== 1000 && event.code !== 4001) {
          const delay = reconnectDelayRef.current;
          reconnectRef.current = setTimeout(() => {
            if (mountedRef.current) {
              reconnectDelayRef.current = Math.min(delay * 2, WS_RECONNECT_MAX);
              connect();
            }
          }, delay);
        }
      };

    } catch {
      // Malformed URL or missing token
    }
  }, [account?.id, isTokenExpired, getLastEventId, setLastEventId]);

  // Fetch initial margins on mount (from Redis cache on backend, not live API)
  useEffect(() => {
    if (!account?.id || isTokenExpired) return;
    api.get('/api/zerodha/margins')
      .then(res => setMargins(res.data))
      .catch(() => {}); // non-fatal, WebSocket will update on next trade
  }, [account?.id, isTokenExpired]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (pingRef.current) clearInterval(pingRef.current);
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close(1000);
    };
  }, [connect]);

  return (
    <WebSocketContext.Provider value={{
      prices,
      margins,
      lastTradeEvent,
      lastAlertEvent,
      isConnected,
      subscribe,
      subscribeToPositions,
    }}>
      {children}
    </WebSocketContext.Provider>
  );
}
