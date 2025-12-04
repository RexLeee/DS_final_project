import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { campaignsApi } from '../api/campaigns';
import type { Campaign } from '../types';
import { useCountdown, formatTimeLeft } from '../hooks/useCountdown';

function CampaignCard({ campaign }: { campaign: Campaign }) {
  const timeLeft = useCountdown(
    campaign.status === 'pending' ? campaign.start_time : campaign.end_time
  );

  const getStatusBadge = () => {
    switch (campaign.status) {
      case 'pending':
        return (
          <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs font-medium">
            即將開始
          </span>
        );
      case 'active':
        return (
          <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
            進行中
          </span>
        );
      case 'ended':
        return (
          <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-medium">
            已結束
          </span>
        );
    }
  };

  return (
    <Link
      to={`/campaigns/${campaign.campaign_id}`}
      className="block bg-white rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition"
    >
      {campaign.product.image_url ? (
        <img
          src={campaign.product.image_url}
          alt={campaign.product.name}
          className="w-full h-48 object-cover"
        />
      ) : (
        <div className="w-full h-48 bg-gray-200 flex items-center justify-center">
          <span className="text-gray-400 text-4xl">📦</span>
        </div>
      )}

      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <h3 className="text-lg font-bold text-gray-800 truncate flex-1">
            {campaign.product.name}
          </h3>
          {getStatusBadge()}
        </div>

        <p className="text-sm text-gray-600 mb-3 line-clamp-2">
          {campaign.product.description || '暫無描述'}
        </p>

        <div className="grid grid-cols-2 gap-2 text-sm mb-3">
          <div>
            <span className="text-gray-500">底價:</span>
            <span className="ml-1 font-medium text-gray-800">
              ${Number(campaign.product.min_price).toFixed(2)}
            </span>
          </div>
          <div>
            <span className="text-gray-500">庫存:</span>
            <span className="ml-1 font-medium text-gray-800">
              {campaign.product.stock} 件
            </span>
          </div>
        </div>

        <div className="border-t pt-3">
          <div className="text-sm text-gray-500">
            {campaign.status === 'pending' ? '開始倒數:' : campaign.status === 'active' ? '結束倒數:' : ''}
          </div>
          <div
            className={`text-lg font-bold ${
              campaign.status === 'active'
                ? timeLeft.total < 60000
                  ? 'text-red-600'
                  : 'text-blue-600'
                : 'text-gray-600'
            }`}
          >
            {campaign.status === 'ended' ? '已結束' : formatTimeLeft(timeLeft)}
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCampaigns = async () => {
      try {
        const response = await campaignsApi.list(1, 20);
        setCampaigns(response.items);
      } catch {
        setError('無法載入活動列表');
      } finally {
        setIsLoading(false);
      }
    };

    fetchCampaigns();
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 text-lg">{error}</div>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          重新載入
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">活動列表</h1>
        <div className="text-sm text-gray-500">共 {campaigns.length} 個活動</div>
      </div>

      {campaigns.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <div className="text-gray-400 text-6xl mb-4">📋</div>
          <div className="text-gray-600">目前沒有活動</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {campaigns.map((campaign) => (
            <CampaignCard key={campaign.campaign_id} campaign={campaign} />
          ))}
        </div>
      )}
    </div>
  );
}
