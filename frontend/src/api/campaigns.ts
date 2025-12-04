import client from './client';
import type { Campaign, CampaignCreate, PaginatedResponse } from '../types';

// Backend response type for campaign list
interface CampaignListResponse {
  campaigns: Campaign[];
  total: number;
}

export const campaignsApi = {
  async list(page = 1, size = 10): Promise<PaginatedResponse<Campaign>> {
    const skip = (page - 1) * size;
    const response = await client.get<CampaignListResponse>('/campaigns', {
      params: { skip, limit: size },
    });
    // Transform backend response to frontend format
    return {
      items: response.data.campaigns,
      total: response.data.total,
      page,
      size,
      pages: Math.ceil(response.data.total / size),
    };
  },

  async get(campaignId: string): Promise<Campaign> {
    const response = await client.get<Campaign>(`/campaigns/${campaignId}`);
    return response.data;
  },

  async create(data: CampaignCreate): Promise<Campaign> {
    const response = await client.post<Campaign>('/campaigns', data);
    return response.data;
  },
};
