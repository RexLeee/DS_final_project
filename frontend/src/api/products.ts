import client from './client';
import type { Product, ProductCreate, PaginatedResponse } from '../types';

export const productsApi = {
  async list(page = 1, size = 10): Promise<PaginatedResponse<Product>> {
    const response = await client.get<PaginatedResponse<Product>>('/products', {
      params: { page, size },
    });
    return response.data;
  },

  async get(productId: string): Promise<Product> {
    const response = await client.get<Product>(`/products/${productId}`);
    return response.data;
  },

  async create(data: ProductCreate): Promise<Product> {
    const response = await client.post<Product>('/products', data);
    return response.data;
  },
};
