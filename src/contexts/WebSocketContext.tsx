/**
 * WebSocketContext — single WebSocket connection per browser tab.
 *
 * Why a shared context:
 *   Previously usePriceStream was used directly in components.
 *   Multiple components → multiple WebSocket connections → wasteful.
 *   This context provides ONE connection shared across the entire app.
 *
 * What it handles:
 *   - Live prices (from KiteTicker via backend)
 *   - Trade update events (Celery → Redis → WebSocket → here)
 *   - Alert update events (BehaviorEngine → Redis → WebSocket → here)
 *   - Position update events
 *
 * How consumers use it:
 *   const { prices, lastTradeEvent, lastAlertEvent, isConnected } = useWebSocket();
 */

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useBroker } from './BrokerContext';

const AUTH_TOKEN_KEY = 'tradementor_auth_token';

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
  lastTradeEvent: TradeEvent | null;
  lastAlertEvent: AlertEvent | null;
  isConnected: boolean;
  subscribe: (instruments: string[]) => void;
  subscribeToPositions: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue>({
  prices: {},
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
  const [lastTradeEvent, setLastTradeEvent] = useState<TradeEvent | null>(null);
  const [lastAlertEvent, setLastAlertEvent] = useState<AlertEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(WS_RECONNECT_BASE);
  const mountedRef = useRef(true);
  const pendingSubscriptions = useRef<string[]>([]);

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
      // Queue for when connection opens
      pendingSubscriptions.current = [
        ...pendingSubscriptions.current,
        ...instruments,
      ];
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

      const ws = new WebSocket(url.toString());
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        reconnectDelayRef.current = WS_RECONNECT_BASE; // reset backoff

        // Start ping
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'ping' }));
          }
        }, PING_INTERVAL);

        // Auto-subscribe to positions on connect
        ws.send(JSON.stringify({ action: 'subscribe_positions' }));

        // Flush pending subscriptions
        if (pendingSubscriptions.current.length > 0) {
          ws.send(JSON.stringify({
            action: 'subscribe',
            instruments: pendingSubscriptions.current,
          }));
          pendingSubscriptions.current = [];
        }
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const msg = JSON.parse(event.data);
          const ts = new Date().toISOString();

          switch (msg.type) {
            case 'price':
              if (msg.instrument && msg.data) {
                setPrices(prev => ({ ...prev, [msg.instrument]: msg.data }));
              }
              break;

            case 'trade':
            case 'trade_update':
              // Celery processed a trade → Dashboard should re-fetch
              setLastTradeEvent({ ...msg.data, timestamp: ts });
              break;

            case 'alert':
            case 'alert_update':
              // BehaviorEngine fired an alert → AlertContext should re-fetch
              setLastAlertEvent({ ...msg.data, timestamp: ts });
              break;

            case 'position_update':
              // Position changed → trigger trade+position refresh
              setLastTradeEvent({ ...msg.data, timestamp: ts });
              break;

            // ignore: pong, subscribed, error
          }
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        if (pingRef.current) clearInterval(pingRef.current);

        // Reconnect with backoff (unless clean close or auth failure)
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

      ws.onerror = () => {
        // onclose fires after onerror, handles reconnection
      };

    } catch {
      // Malformed URL or no token — don't connect
    }
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
