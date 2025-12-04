import { useState } from 'react';
import { bidsApi } from '../api/bids';
import type { Bid } from '../types';

interface BidFormProps {
  campaignId: string;
  minPrice: number;
  isActive: boolean;
  onBidSuccess?: (bid: Bid) => void;
}

export default function BidForm({
  campaignId,
  minPrice,
  isActive,
  onBidSuccess,
}: BidFormProps) {
  const [price, setPrice] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastBid, setLastBid] = useState<Bid | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const priceNum = parseFloat(price);
    if (isNaN(priceNum) || priceNum < minPrice) {
      setError(`出價必須至少 $${Number(minPrice).toFixed(2)}`);
      return;
    }

    setIsSubmitting(true);
    try {
      const bid = await bidsApi.submit({
        campaign_id: campaignId,
        price: priceNum,
      });
      setLastBid(bid);
      setPrice('');
      onBidSuccess?.(bid);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || '出價失敗，請稍後再試');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-xl font-bold text-gray-800 mb-4">出價</h2>

      {!isActive && (
        <div className="mb-4 p-4 bg-yellow-100 border border-yellow-300 rounded-lg text-yellow-800">
          活動尚未開始或已結束，無法出價
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label htmlFor="price" className="block text-sm font-medium text-gray-700 mb-1">
            出價金額
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
              $
            </span>
            <input
              type="number"
              id="price"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              min={minPrice}
              step="0.01"
              placeholder={`最低 ${Number(minPrice).toFixed(2)}`}
              disabled={!isActive || isSubmitting}
              className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
          </div>
          <p className="mt-1 text-sm text-gray-500">
            底價: ${Number(minPrice).toFixed(2)}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-300 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={!isActive || isSubmitting}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition"
        >
          {isSubmitting ? '處理中...' : '送出出價'}
        </button>
      </form>

      {lastBid && (
        <div className="mt-4 p-4 bg-green-100 border border-green-300 rounded-lg">
          <h3 className="font-medium text-green-800 mb-2">出價成功!</h3>
          <div className="grid grid-cols-2 gap-2 text-sm text-green-700">
            <div>出價: ${Number(lastBid.price).toFixed(2)}</div>
            <div>積分: {Number(lastBid.score).toFixed(2)}</div>
            <div>排名: #{lastBid.rank}</div>
            <div>反應時間: {(lastBid.time_elapsed_ms / 1000).toFixed(2)}秒</div>
          </div>
        </div>
      )}
    </div>
  );
}
