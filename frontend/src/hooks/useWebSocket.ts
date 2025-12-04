import { useState, useEffect, useCallback, useRef } from 'react';
import type { RankingEntry, WSEvent } from '../types';

interface WebSocketState {
  rankings: RankingEntry[];
  totalParticipants: number;
  minWinningScore: number;
  maxScore: number;
  myRank: number | null;
  myScore: number | null;
  isWinner: boolean;
  isConnected: boolean;
  campaignEnded: boolean;
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
    campaignEnded: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (!campaignId || !token) return;

    // Determine WebSocket URL based on environment
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/${campaignId}?token=${token}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setState((prev) => ({ ...prev, isConnected: true }));

      // Start ping interval
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

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setState((prev) => ({ ...prev, isConnected: false }));

      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }, [campaignId, token]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    ...state,
    reconnect: connect,
  };
}
