import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { productsApi } from '../../api/products';
import { campaignsApi } from '../../api/campaigns';

export default function CreateCampaign() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Product form state
  const [productName, setProductName] = useState('');
  const [productDescription, setProductDescription] = useState('');
  const [minPrice, setMinPrice] = useState('100');
  const [stock, setStock] = useState('10');
  const [imageUrl, setImageUrl] = useState('');

  // Campaign form state
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [alpha, setAlpha] = useState('1.0');
  const [beta, setBeta] = useState('1000.0');
  const [gamma, setGamma] = useState('50.0');

  // UI state
  const [step, setStep] = useState<'product' | 'campaign'>('product');
  const [productId, setProductId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  if (!isAuthenticated || !user?.is_admin) {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 text-lg">您沒有權限訪問此頁面</div>
        <button
          onClick={() => navigate('/')}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          返回首頁
        </button>
      </div>
    );
  }

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const product = await productsApi.create({
        name: productName,
        description: productDescription || undefined,
        min_price: parseFloat(minPrice),
        stock: parseInt(stock, 10),
        image_url: imageUrl || undefined,
      });
      setProductId(product.product_id);
      setStep('campaign');
      setSuccess('商品建立成功！請繼續設定活動。');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || '建立商品失敗');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsLoading(true);

    if (!productId) {
      setError('請先建立商品');
      setIsLoading(false);
      return;
    }

    try {
      const campaign = await campaignsApi.create({
        product_id: productId,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        alpha: parseFloat(alpha),
        beta: parseFloat(beta),
        gamma: parseFloat(gamma),
      });
      setSuccess(`活動建立成功！活動 ID: ${campaign.campaign_id}`);
      setTimeout(() => {
        navigate(`/campaigns/${campaign.campaign_id}`);
      }, 2000);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || '建立活動失敗');
    } finally {
      setIsLoading(false);
    }
  };

  // Format date to Taiwan time (UTC+8) for datetime-local input
  const formatToTaiwanTime = (d: Date) => {
    // Create a formatter for Taiwan timezone
    const year = d.toLocaleString('en-CA', { timeZone: 'Asia/Taipei', year: 'numeric' });
    const month = d.toLocaleString('en-CA', { timeZone: 'Asia/Taipei', month: '2-digit' });
    const day = d.toLocaleString('en-CA', { timeZone: 'Asia/Taipei', day: '2-digit' });
    const hour = d.toLocaleString('en-GB', { timeZone: 'Asia/Taipei', hour: '2-digit', hour12: false });
    const minute = d.toLocaleString('en-GB', { timeZone: 'Asia/Taipei', minute: '2-digit' });
    return `${year}-${month}-${day}T${hour}:${minute}`;
  };

  // Set default times (start: now, end: start + 30 min) in Taiwan time
  const setDefaultTimes = () => {
    const now = new Date();
    const end = new Date(now.getTime() + 30 * 60 * 1000);

    setStartTime(formatToTaiwanTime(now));
    setEndTime(formatToTaiwanTime(end));
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">建立新活動</h1>

      {/* Progress indicator */}
      <div className="flex items-center mb-8">
        <div
          className={`flex items-center justify-center w-8 h-8 rounded-full ${
            step === 'product' ? 'bg-blue-600 text-white' : 'bg-green-500 text-white'
          }`}
        >
          {productId ? '✓' : '1'}
        </div>
        <div className="flex-1 h-1 mx-2 bg-gray-200">
          <div
            className={`h-full ${productId ? 'bg-green-500' : 'bg-gray-200'}`}
            style={{ width: productId ? '100%' : '0%' }}
          ></div>
        </div>
        <div
          className={`flex items-center justify-center w-8 h-8 rounded-full ${
            step === 'campaign' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
          }`}
        >
          2
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-100 border border-red-300 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-4 bg-green-100 border border-green-300 rounded-lg text-green-700">
          {success}
        </div>
      )}

      {step === 'product' && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">步驟 1: 建立商品</h2>

          <form onSubmit={handleCreateProduct}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                商品名稱 *
              </label>
              <input
                type="text"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="例: iPhone 15 Pro"
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                商品描述
              </label>
              <textarea
                value={productDescription}
                onChange={(e) => setProductDescription(e.target.value)}
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="商品詳細描述..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  底價 *
                </label>
                <input
                  type="number"
                  value={minPrice}
                  onChange={(e) => setMinPrice(e.target.value)}
                  required
                  min="0"
                  step="0.01"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  庫存數量 (K) *
                </label>
                <input
                  type="number"
                  value={stock}
                  onChange={(e) => setStock(e.target.value)}
                  required
                  min="1"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                商品圖片 URL
              </label>
              <input
                type="url"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="https://example.com/image.jpg"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium py-2 px-4 rounded-lg transition"
            >
              {isLoading ? '建立中...' : '建立商品'}
            </button>
          </form>
        </div>
      )}

      {step === 'campaign' && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">步驟 2: 設定活動</h2>

          <form onSubmit={handleCreateCampaign}>
            <div className="mb-4">
              <div className="flex justify-between items-center mb-1">
                <label className="block text-sm font-medium text-gray-700">
                  活動時間 *
                </label>
                <button
                  type="button"
                  onClick={setDefaultTimes}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  使用預設時間
                </button>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">開始時間</label>
                  <input
                    type="datetime-local"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    required
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">結束時間</label>
                  <input
                    type="datetime-local"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    required
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                積分計算參數
              </label>
              <div className="p-3 bg-gray-50 rounded-lg mb-3 text-sm text-gray-600">
                Score = α × P + β/(T+1) + γ × W
                <br />
                <span className="text-xs">P=價格, T=時間(ms), W=會員權重</span>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">α (價格權重)</label>
                  <input
                    type="number"
                    value={alpha}
                    onChange={(e) => setAlpha(e.target.value)}
                    required
                    step="0.1"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">β (時間權重)</label>
                  <input
                    type="number"
                    value={beta}
                    onChange={(e) => setBeta(e.target.value)}
                    required
                    step="0.1"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">γ (會員權重)</label>
                  <input
                    type="number"
                    value={gamma}
                    onChange={(e) => setGamma(e.target.value)}
                    required
                    step="0.1"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => setStep('product')}
                className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded-lg transition"
              >
                返回上一步
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium py-2 px-4 rounded-lg transition"
              >
                {isLoading ? '建立中...' : '建立活動'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
