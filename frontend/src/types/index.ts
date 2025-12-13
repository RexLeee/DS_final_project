// User types
export interface User {
  user_id: string;
  email: string;
  username: string;
  weight: number;
  is_admin: boolean;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  username: string;
}

// Product types
export interface Product {
  product_id: string;
  name: string;
  description: string | null;
  image_url: string | null;
  stock: number;
  min_price: number;
  status: 'draft' | 'active';
  created_at: string;
}

export interface ProductCreate {
  name: string;
  description?: string;
  image_url?: string;
  stock: number;
  min_price: number;
}

// Campaign types
export interface Campaign {
  campaign_id: string;
  product_id: string;
  product: Product;
  start_time: string;
  end_time: string;
  alpha: number;
  beta: number;
  gamma: number;
  quota: number;
  status: 'pending' | 'active' | 'ended';
  created_at: string;
  stats?: CampaignStats;
}

export interface CampaignStats {
  total_participants: number;
  max_price: number;
  min_winning_score: number;
}

export interface CampaignCreate {
  product_id: string;
  start_time: string;
  end_time: string;
  alpha?: number;
  beta?: number;
  gamma?: number;
}

// Bid types
export interface Bid {
  bid_id: string;
  campaign_id: string;
  user_id: string;
  product_id: string;
  price: number;
  score: number;
  rank: number;
  time_elapsed_ms: number;
  bid_number: number;
  created_at: string;
}

export interface BidRequest {
  campaign_id: string;
  price: number;
}

// Ranking types
export interface RankingEntry {
  rank: number;
  user_id: string;
  username: string;
  score: number;
  price: number;
}

export interface RankingData {
  campaign_id: string;
  total_participants: number;
  rankings: RankingEntry[];
  min_winning_score: number;
  max_score: number;
  updated_at: string;
}

export interface MyRank {
  campaign_id: string;
  user_id: string;
  rank: number;
  score: number;
  is_winning: boolean;
  total_participants: number;
}

// Order types
export interface Order {
  order_id: string;
  campaign_id: string;
  user_id: string;
  product_id: string;
  final_price: number;
  final_score: number;
  final_rank: number;
  status: 'pending' | 'completed';
  created_at: string;
}

// WebSocket event types
export interface WSRankingUpdate {
  event: 'ranking_update';
  data: {
    campaign_id: string;
    top_k: RankingEntry[];
    total_participants: number;
    min_winning_score: number;
    max_score: number;
    timestamp: string;
  };
}

export interface WSBidAccepted {
  event: 'bid_accepted';
  data: {
    bid_id: string;
    campaign_id: string;
    price: number;
    score: number;
    rank: number;
    time_elapsed_ms: number;
    timestamp: string;
  };
}

export interface WSCampaignEnded {
  event: 'campaign_ended';
  data: {
    campaign_id: string;
    is_winner: boolean;
    final_rank: number;
    final_score: number;
    final_price: number;
  };
}

export type WSEvent = WSRankingUpdate | WSBidAccepted | WSCampaignEnded;

// Pagination types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
