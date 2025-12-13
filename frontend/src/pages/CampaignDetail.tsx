import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { campaignsApi } from '../api/campaigns';
import { useAuth } from '../contexts/AuthContext';
import { useWebSocket } from '../hooks/useWebSocket';
import { useCountdown, formatTimeLeft } from '../hooks/useCountdown';
import type { Campaign } from '../types';
import RankingBoard from '../components/RankingBoard';
import BidForm from '../components/BidForm';

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, token, isAuthenticated } = useAuth();

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const wsState = useWebSocket(id, token);
  const timeLeft = useCountdown(
    campaign?.status === 'pending' ? campaign?.start_time : campaign?.end_time
  );

  useEffect(() => {
    const fetchCampaign = async () => {
      if (!id) return;

      try {
        const data = await campaignsApi.get(id);
        setCampaign(data);
      } catch {
        setError('無法載入活動資訊');
      } finally {
        setIsLoading(false);
      }
    };

    fetchCampaign();
  }, [id]);

  // Refresh campaign status when WebSocket indicates campaign ended
  useEffect(() => {
    if (wsState.campaignEnded && id) {
      campaignsApi.get(id).then(setCampaign);
    }
  }, [wsState.campaignEnded, id]);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 text-lg">{error || '活動不存在'}</div>
        <button
          onClick={() => navigate('/')}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          返回活動列表
        </button>
      </div>
    );
  }

  const getStatusBanner = () => {
    switch (campaign.status) {
      case 'pending':
        return (
          <div className="bg-yellow-100 border border-yellow-300 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-yellow-600 text-2xl mr-3">⏳</span>
                <div>
                  <div className="font-medium text-yellow-800">活動即將開始</div>
                  <div className="text-sm text-yellow-700">
                    開始時間: {new Date(campaign.start_time).toLocaleString('zh-TW')}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-yellow-700">開始倒數</div>
                <div className="text-2xl font-bold text-yellow-800">{formatTimeLeft(timeLeft)}</div>
              </div>
            </div>
          </div>
        );
      case 'active':
        return (
          <div className="bg-green-100 border border-green-300 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-green-600 text-2xl mr-3">🔥</span>
                <div>
                  <div className="font-medium text-green-800">活動進行中</div>
                  <div className="text-sm text-green-700">快來參與競標!</div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-green-700">結束倒數</div>
                <div
                  className={`text-2xl font-bold ${
                    timeLeft.total < 60000 ? 'text-red-600' : 'text-green-800'
                  }`}
                >
                  {formatTimeLeft(timeLeft)}
                </div>
              </div>
            </div>
          </div>
        );
      case 'ended':
        return (
          <div className="bg-gray-100 border border-gray-300 rounded-lg p-4 mb-6">
            <div className="flex items-center">
              <span className="text-gray-600 text-2xl mr-3">✅</span>
              <div>
                <div className="font-medium text-gray-800">活動已結束</div>
                <div className="text-sm text-gray-600">
                  結束時間: {new Date(campaign.end_time).toLocaleString('zh-TW')}
                </div>
              </div>
              {wsState.isWinner && (
                <div className="ml-auto">
                  <span className="px-4 py-2 bg-green-500 text-white rounded-lg font-medium">
                    🎉 恭喜得標!
                  </span>
                </div>
              )}
            </div>
          </div>
        );
    }
  };

  return (
    <div>
      {/* Back button */}
      <button
        onClick={() => navigate('/')}
        className="mb-4 text-gray-600 hover:text-gray-800 flex items-center"
      >
        ← 返回活動列表
      </button>

      {/* Status banner */}
      {getStatusBanner()}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Product info & Bid form */}
        <div className="lg:col-span-1 space-y-6">
          {/* Product card */}
          <div className="bg-white rounded-lg shadow-lg overflow-hidden">
            {campaign.product.image_url ? (
              <img
                src={campaign.product.image_url}
                alt={campaign.product.name}
                className="w-full h-48 object-cover"
              />
            ) : (
              <div className="w-full h-48 bg-gray-200 flex items-center justify-center">
                <span className="text-gray-400 text-6xl">📦</span>
              </div>
            )}

            <div className="p-4">
              <h1 className="text-xl font-bold text-gray-800 mb-2">
                {campaign.product.name}
              </h1>
              <p className="text-gray-600 text-sm mb-4">
                {campaign.product.description || '暫無描述'}
              </p>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-gray-500">底價</div>
                  <div className="text-lg font-bold text-gray-800">
                    ${Number(campaign.product.min_price).toFixed(2)}
                  </div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-gray-500">可得標名額</div>
                  <div className="text-lg font-bold text-gray-800">
                    {campaign.quota} 件
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bid form */}
          {isAuthenticated ? (
            <BidForm
              campaignId={campaign.campaign_id}
              minPrice={campaign.product.min_price}
              isActive={campaign.status === 'active'}
            />
          ) : (
            <div className="bg-white rounded-lg shadow-lg p-6 text-center">
              <p className="text-gray-600 mb-4">請先登入以參與競標</p>
              <button
                onClick={() => navigate('/login')}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition"
              >
                登入
              </button>
            </div>
          )}

          {/* Parameters */}
          <div className="bg-white rounded-lg shadow-lg p-4">
            <h3 className="font-medium text-gray-800 mb-3">積分計算參數</h3>
            <div className="text-sm text-gray-600 space-y-2">
              <div className="flex justify-between">
                <span>價格權重 (α)</span>
                <span className="font-medium">{campaign.alpha}</span>
              </div>
              <div className="flex justify-between">
                <span>時間權重 (β)</span>
                <span className="font-medium">{campaign.beta}</span>
              </div>
              <div className="flex justify-between">
                <span>會員權重 (γ)</span>
                <span className="font-medium">{campaign.gamma}</span>
              </div>
            </div>
            <div className="mt-3 p-2 bg-gray-50 rounded text-xs text-gray-500">
              Score = α×P + β/(T+1) + γ×W
            </div>
          </div>
        </div>

        {/* Right column - Ranking board */}
        <div className="lg:col-span-2">
          <RankingBoard
            rankings={wsState.rankings}
            totalParticipants={wsState.totalParticipants}
            minWinningScore={wsState.minWinningScore}
            maxScore={wsState.maxScore}
            currentUserId={user?.user_id}
            myRank={wsState.myRank}
            myScore={wsState.myScore}
            stock={campaign.quota}
            isConnected={wsState.isConnected}
            isEnded={campaign.status === 'ended'}
          />
        </div>
      </div>
    </div>
  );
}
