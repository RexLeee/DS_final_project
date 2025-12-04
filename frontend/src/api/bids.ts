import client from './client';
import type { Bid, BidRequest } from '../types';

export const bidsApi = {
  async submit(data: BidRequest): Promise<Bid> {
    const response = await client.post<Bid>('/bids', data);
    return response.data;
  },

  async getHistory(campaignId: string): Promise<Bid[]> {
    const response = await client.get<Bid[]>(`/bids/${campaignId}/history`);
    return response.data;
  },
};
