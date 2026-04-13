import { useEffect, useRef, useState, useCallback } from 'react';
import { useBroker } from '@/contexts/BrokerContext';
import { AUTH_TOKEN_KEY } from '@/lib/api';

interface WebSocketMessage {
    type: string;
    data?: any;
    instrument?: string;
    timestamp?: string;
}

interface UseWebSocketOptions {
    onMessage?: (message: WebSocketMessage) => void;
    autoConnect?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
    const { isConnected: isBrokerConnected } = useBroker();
    const wsRef = useRef<WebSocket | null>(null);
    const [isWsConnected, setIsWsConnected] = useState(false);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

    const connect = useCallback(() => {
        // Need a token to connect
        const token = localStorage.getItem(AUTH_TOKEN_KEY);

        // Only connect if we have a token. 
        // We don't strictly enforce isBrokerConnected because WS might be used for other things,
        // but for price streaming it makes sense.
        if (!token) return;

        // Close existing connection if any
        if (wsRef.current) {
            if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
                wsRef.current.close();
            }
        }

        try {
            // Derive WS URL from API URL
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            // Handle relative URLs if VITE_API_URL is just '/api'
            const baseUrl = apiUrl.startsWith('http') ? apiUrl : window.location.origin + apiUrl;

            const urlObj = new URL(baseUrl);
            urlObj.protocol = urlObj.protocol === 'https:' ? 'wss:' : 'ws:';
            urlObj.pathname = '/api/ws/prices';
            urlObj.searchParams.set('token', token);

            const wsUrl = urlObj.toString();

            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                setIsWsConnected(true);
                if (reconnectTimeoutRef.current) {
                    clearTimeout(reconnectTimeoutRef.current);
                    reconnectTimeoutRef.current = undefined;
                }

                // Auto-subscribe to positions on connect
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ action: 'subscribe_positions' }));
                }
            };

            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    options.onMessage?.(message);
                } catch (err) {
                    console.error('WebSocket message parse error:', err);
                }
            };

            ws.onclose = () => {
                setIsWsConnected(false);
                wsRef.current = null;

                // Auto-reconnect after 3s if supposed to be connected
                if (options.autoConnect !== false) {
                    reconnectTimeoutRef.current = setTimeout(() => {
                        connect();
                    }, 3000);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket Error:', error);
                ws.close();
            };

            wsRef.current = ws;

        } catch (err) {
            console.error('WebSocket connection failed:', err);
        }
    }, [options.onMessage]); // Removed options dependency to avoid loops if options object is unstable

    const sendMessage = useCallback((message: any) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(message));
        }
    }, []);

    const subscribePositions = useCallback(() => {
        sendMessage({ action: 'subscribe_positions' });
    }, [sendMessage]);

    useEffect(() => {
        if (options.autoConnect !== false && isBrokerConnected) {
            connect();
        }
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, [connect, options.autoConnect, isBrokerConnected]);

    return {
        connect,
        sendMessage,
        subscribePositions,
        isConnected: isWsConnected
    };
}
