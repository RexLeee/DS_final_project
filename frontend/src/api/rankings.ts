import client from './client';
import type { RankingData, MyRank } from '../types';

export const rankingsApi = {
  async get(campaignId: string): Promise<RankingData> {
    const response = await client.get<RankingData>(`/rankings/${campaignId}`);
    return response.data;
  },

  async getMyRank(campaignId: string): Promise<MyRank> {
    const response = await client.get<MyRank>(`/rankings/${campaignId}/me`);
    return response.data;
  },
};
