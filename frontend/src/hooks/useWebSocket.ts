import { useState, useEffect, useCallback, useRef } from 'react';
import type { RankingEntry, WSEvent } from '../types';

// Reconnection configuration
const MAX_RETRIES = 10;
const INITIAL_RETRY_DELAY = 1000; // 1 second
const MAX_RETRY_DELAY = 30000; // 30 seconds

interface WebSocketState {
  rankings: RankingEntry[];
  totalParticipants: number;
  minWinningScore: number;
  maxScore: number;
  myRank: number | null;
  myScore: number | null;
  isWinner: boolean;
  isConnected: boolean;
  isReconnecting: boolean;
  campaignEnded: boolean;
  retryCount: number;
}

export function useWebSocket(campaignId: string | undefined, token: string | null) {
  const [state, setState] = useState<WebSocketState>({
    rankings: [],
    totalParticipants: 0,
    minWinningScore: 0,
    maxScore: 0,
    myRank: null,
    myScore: null,
    isWinner: false,
    isConnected: false,
    isReconnecting: false,
    campaignEnded: false,
    retryCount: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const retryTimeoutRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const campaignEndedRef = useRef(false);

  // Clear all timers
  const clearTimers = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  }, []);

  // Schedule a reconnection with exponential backoff
  const scheduleReconnect = useCallback(() => {
    if (campaignEndedRef.current) {
      console.log('Campaign ended, not reconnecting');
      return;
    }

    if (retryCountRef.current >= MAX_RETRIES) {
      console.error('Max reconnection attempts reached');
      setState((prev) => ({
        ...prev,
        isReconnecting: false,
        retryCount: retryCountRef.current,
      }));
      return;
    }

    const delay = Math.min(
      INITIAL_RETRY_DELAY * Math.pow(2, retryCountRef.current),
      MAX_RETRY_DELAY
    );

    console.log(
      `Scheduling reconnect attempt ${retryCountRef.current + 1}/${MAX_RETRIES} in ${delay}ms`
    );

    setState((prev) => ({
      ...prev,
      isReconnecting: true,
      retryCount: retryCountRef.current,
    }));

    retryTimeoutRef.current = window.setTimeout(() => {
      retryCountRef.current += 1;
      connect();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    if (!campaignId || !token) return;

    // Clear any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    clearTimers();

    // Determine WebSocket URL based on environment
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/${campaignId}?token=${token}`;

    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      // Reset retry count on successful connection
      retryCountRef.current = 0;
      setState((prev) => ({
        ...prev,
        isConnected: true,
        isReconnecting: false,
        retryCount: 0,
      }));

      // Start ping interval (every 30 seconds)
      pingIntervalRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      // Handle pong response
      if (event.data === 'pong') return;

      try {
        const message: WSEvent = JSON.parse(event.data);

        switch (message.event) {
          case 'ranking_update':
            setState((prev) => ({
              ...prev,
              rankings: message.data.top_k,
              totalParticipants: message.data.total_participants,
              minWinningScore: message.data.min_winning_score,
              maxScore: message.data.max_score,
            }));
            break;

          case 'bid_accepted':
            setState((prev) => ({
              ...prev,
              myRank: message.data.rank,
              myScore: message.data.score,
            }));
            break;

          case 'campaign_ended':
            campaignEndedRef.current = true;
            setState((prev) => ({
              ...prev,
              campaignEnded: true,
              isWinner: message.data.is_winner,
              myRank: message.data.final_rank,
              myScore: message.data.final_score,
            }));
            break;
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason);
      clearTimers();

      setState((prev) => ({ ...prev, isConnected: false }));

      // Auto-reconnect if not a normal closure and campaign not ended
      if (event.code !== 1000 && !campaignEndedRef.current) {
        scheduleReconnect();
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }, [campaignId, token, clearTimers, scheduleReconnect]);

  const disconnect = useCallback(() => {
    campaignEndedRef.current = true; // Prevent reconnection
    clearTimers();

    if (wsRef.current) {
      wsRef.current.close(1000, 'User initiated disconnect');
      wsRef.current = null;
    }
  }, [clearTimers]);

  const manualReconnect = useCallback(() => {
    retryCountRef.current = 0;
    campaignEndedRef.current = false;
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Reset campaign ended flag when campaignId changes
  useEffect(() => {
    campaignEndedRef.current = false;
    retryCountRef.current = 0;
  }, [campaignId]);

  return {
    ...state,
    reconnect: manualReconnect,
  };
}
