import axios from 'axios';
import axiosRetry from 'axios-retry';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000, // 10 seconds timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Configure axios-retry with exponential backoff
axiosRetry(client, {
  retries: 3,
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => {
    // Retry on network errors, idempotent request errors, rate limits, and server errors
    return (
      axiosRetry.isNetworkOrIdempotentRequestError(error) ||
      error.response?.status === 429 || // Rate limit
      (error.response?.status !== undefined && error.response.status >= 500) // Server errors
    );
  },
  onRetry: (retryCount, error, requestConfig) => {
    console.warn(
      `Retry attempt ${retryCount} for ${requestConfig.url}: ${error.message}`
    );
  },
});

// Request interceptor to add auth token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
// Note: 401 errors are handled by AuthContext, not here
// This avoids race conditions during page refresh
client.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

export default client;
