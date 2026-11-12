import { useEffect, useRef, useState } from 'react';
import { getAuthToken } from '@/lib/api';

export type DocumentStatus = 'processing' | 'ready' | 'error';

export interface DocumentStatusUpdate {
    document_id: string;
    status: DocumentStatus;
    error_message?: string;
    total_chunks?: number;
    total_pages?: number;
}

interface UseDocumentStatusOptions {
    enabled?: boolean;
    pollingInterval?: number; // Fallback polling interval in ms
    onStatusUpdate?: (update: DocumentStatusUpdate) => void;
}

/**
 * Custom hook for real-time document status updates
 * Attempts to use WebSocket/SSE if available, falls back to polling
 */
export function useDocumentStatus(options: UseDocumentStatusOptions = {}) {
    const {
        enabled = true,
        pollingInterval = 3000,
        onStatusUpdate,
    } = options;

    const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const [usePolling, setUsePolling] = useState(false);

    // Cleanup function
    const cleanup = () => {
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }
    };

    // Try to connect via WebSocket
    const connectWebSocket = async () => {
        if (!enabled) return;

        try {
            const token = await getAuthToken();
            if (!token) {
                // If unauthenticated, do not establish socket connection
                setUsePolling(true);
                return;
            }

            // Get WebSocket URL from environment or construct from API URL (no token in query params)
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsHost = process.env.NEXT_PUBLIC_WS_URL ||
                `${wsProtocol}//${window.location.hostname}:8000`;
            const wsUrl = `${wsHost}/ws/documents/status`;

            setConnectionStatus('connecting');
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                setConnectionStatus('connected');
                setUsePolling(false);

                // Send authentication message securely via WebSocket frame
                ws.send(JSON.stringify({ type: 'auth', token }));
            };

            ws.onmessage = (event) => {
                try {
                    const update: DocumentStatusUpdate = JSON.parse(event.data);
                    onStatusUpdate?.(update);
                } catch (error) {
                    // Silently handle parsing errors
                }
            };

            ws.onerror = (error) => {
                setConnectionStatus('disconnected');
            };

            ws.onclose = () => {
                setConnectionStatus('disconnected');
                wsRef.current = null;

                // Attempt to reconnect after 5 seconds
                if (enabled) {
                    reconnectTimeoutRef.current = setTimeout(() => {
                        connectWebSocket();
                    }, 5000);
                }
            };
        } catch (error) {
            setConnectionStatus('disconnected');
            setUsePolling(true);
        }
    };

    // Initialize connection
    useEffect(() => {
        if (!enabled) {
            cleanup();
            return;
        }

        // Try WebSocket first
        connectWebSocket();

        // Set a timeout to fall back to polling if WebSocket doesn't connect
        const fallbackTimeout = setTimeout(() => {
            if (connectionStatus !== 'connected') {
                setUsePolling(true);
                cleanup();
            }
        }, 5000);

        return () => {
            clearTimeout(fallbackTimeout);
            cleanup();
        };
    }, [enabled]);

    // Polling fallback
    useEffect(() => {
        if (!enabled || !usePolling) {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
            return;
        }

        // Using polling for document status updates

        // Note: The actual polling logic should be implemented in the component
        // This hook just manages the connection state
        // The component will use the `usePolling` state to decide whether to poll

        return () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
        };
    }, [enabled, usePolling, pollingInterval]);

    return {
        connectionStatus,
        usePolling,
        isConnected: connectionStatus === 'connected',
    };
}
