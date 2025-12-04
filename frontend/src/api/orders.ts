import client from './client';
import type { Order, PaginatedResponse } from '../types';

export const ordersApi = {
  async list(page = 1, size = 10): Promise<PaginatedResponse<Order>> {
    const response = await client.get<PaginatedResponse<Order>>('/orders', {
      params: { page, size },
    });
    return response.data;
  },
};
