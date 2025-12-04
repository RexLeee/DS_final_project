import client from './client';
import type { User, LoginResponse, RegisterRequest } from '../types';

export const authApi = {
  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await client.post<LoginResponse>('/auth/login', {
      email,
      password,
    });
    return response.data;
  },

  async register(data: RegisterRequest): Promise<User> {
    const response = await client.post<User>('/auth/register', data);
    return response.data;
  },

  async getMe(): Promise<User> {
    const response = await client.get<User>('/auth/me');
    return response.data;
  },
};
