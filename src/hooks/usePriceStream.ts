/**
 * WebSocket Price Stream Hook
 *
 * Provides real-time price updates for subscribed instruments.
 * Uses JWT token for WebSocket authentication.
 *
 * Usage:
 *   const { prices, subscribe, unsubscribe, isConnected } = usePriceStream(brokerAccountId);
 *
 *   // Subscribe to specific instruments
 *   subscribe(['RELIANCE', 'NIFTY 50']);
 *
 *   // Or subscribe to all positions
 *   subscribeToPositions();
 *
 *   // Access latest prices
 *   const reliancePrice = prices['RELIANCE']?.last_price;
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AUTH_TOKEN_KEY } from '@/lib/api';

interface PriceData {
  last_price: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  change?: number;
  change_percent?: number;
  bid?: number;
  ask?: number;
  oi?: number;
  oi_change?: number;
  timestamp?: string;
}

interface TradeUpdate {
  order_id: string;
  status: string;
  tradingsymbol: string;
  transaction_type: string;
  quantity: number;
  price: number;
}

interface AlertData {
  id: string;
  pattern_type: string;
  severity: string;
  message: string;
}

interface WebSocketMessage {
  type: 'price' | 'trade' | 'alert' | 'subscribed' | 'unsubscribed' | 'pong' | 'error';
  instrument?: string;
  data?: PriceData | TradeUpdate | AlertData;
  instruments?: string[];
  message?: string;
  timestamp?: string;
}

interface UsePriceStreamReturn {
  prices: Record<string, PriceData>;
  isConnected: boolean;
  error: string | null;
  subscribe: (instruments: string[]) => void;
  unsubscribe: (instruments: string[]) => void;
  subscribeToPositions: () => void;
  lastTrade: TradeUpdate | null;
  lastAlert: AlertData | null;
}

const WS_RECONNECT_DELAY = 3000;
const WS_MAX_RECONNECT_DELAY = 60000; // cap at 60s — stops log spam when Kite key not configured
const PING_INTERVAL = 30000;

export function usePriceStream(brokerAccountId?: string): UsePriceStreamReturn {
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectDelayRef = useRef(WS_RECONNECT_DELAY);
  const [lastTrade, setLastTrade] = useState<TradeUpdate | null>(null);
  const [lastAlert, setLastAlert] = useState<AlertData | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!brokerAccountId) {
      return;
    }

    // Get JWT token for WebSocket authentication
    const authToken = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!authToken) {
      setError('Not authenticated');
      return;
    }

    // Determine WebSocket URL
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      // Handle relative URLs if VITE_API_URL is just '/api'
      const baseUrl = apiUrl.startsWith('http') ? apiUrl : window.location.origin + apiUrl;

      const urlObj = new URL(baseUrl);
      urlObj.protocol = urlObj.protocol === 'https:' ? 'wss:' : 'ws:';
      urlObj.pathname = '/api/ws/prices';
      urlObj.searchParams.set('token', authToken);

      const wsUrl = urlObj.toString();
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setError(null);
        reconnectDelayRef.current = WS_RECONNECT_DELAY; // reset backoff on success

        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'ping' }));
          }
        }, PING_INTERVAL);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;

        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          switch (message.type) {
            case 'price':
              if (message.instrument && message.data) {
                setPrices((prev) => ({
                  ...prev,
                  [message.instrument!]: {
                    ...(message.data as PriceData),
                    timestamp: message.timestamp,
                  },
                }));
              }
              break;

            case 'trade':
              setLastTrade(message.data as TradeUpdate);
              break;

            case 'alert':
              setLastAlert(message.data as AlertData);
              break;

            case 'subscribed':
              break;

            case 'unsubscribed':
              break;

            case 'error':
              console.error('WebSocket error:', message.message);
              setError(message.message || 'Unknown error');
              break;

            case 'pong':
              break;
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onerror = () => {
        setError('Connection error');
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;

        setIsConnected(false);

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }

        // Attempt reconnection with exponential backoff (unless clean close or auth failure)
        if (event.code !== 1000 && event.code !== 4001) {
          const delay = reconnectDelayRef.current;
          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
              // Double the delay each attempt, cap at 60s
              reconnectDelayRef.current = Math.min(delay * 2, WS_MAX_RECONNECT_DELAY);
              connect();
            }
          }, delay);
        }
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      setError('Failed to connect');
    }
  }, [brokerAccountId]);

  // Connect on mount (only when brokerAccountId is available)
  useEffect(() => {
    mountedRef.current = true;

    if (brokerAccountId) {
      connect();
    }

    return () => {
      mountedRef.current = false;

      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      if (wsRef.current) {
        wsRef.current.close(1000);
      }
    };
  }, [connect, brokerAccountId]);

  const subscribe = useCallback((instruments: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: 'subscribe',
          instruments,
        })
      );
    }
  }, []);

  const unsubscribe = useCallback((instruments: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: 'unsubscribe',
          instruments,
        })
      );

      setPrices((prev) => {
        const next = { ...prev };
        instruments.forEach((i) => delete next[i]);
        return next;
      });
    }
  }, []);

  const subscribeToPositions = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: 'subscribe_positions',
        })
      );
    }
  }, []);

  return {
    prices,
    isConnected,
    error,
    subscribe,
    unsubscribe,
    subscribeToPositions,
    lastTrade,
    lastAlert,
  };
}

export default usePriceStream;
