import type { RankingEntry } from '../types';

interface RankingBoardProps {
  rankings: RankingEntry[];
  totalParticipants: number;
  minWinningScore: number;
  maxScore: number;
  currentUserId?: string;
  myRank?: number | null;
  myScore?: number | null;
  stock: number;
  isConnected: boolean;
}

export default function RankingBoard({
  rankings,
  totalParticipants,
  minWinningScore,
  maxScore,
  currentUserId,
  myRank,
  myScore,
  stock,
  isConnected,
}: RankingBoardProps) {
  const isWinningPosition = (rank: number) => rank <= stock;

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-gray-800">即時排名</h2>
        <div className="flex items-center space-x-2">
          <span
            className={`w-3 h-3 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-sm text-gray-500">
            {isConnected ? '即時連線中' : '連線中斷'}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-sm text-gray-500">參與人數</div>
          <div className="text-2xl font-bold text-gray-800">{totalParticipants}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-sm text-gray-500">最高積分</div>
          <div className="text-2xl font-bold text-blue-600">{Number(maxScore).toFixed(2)}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-sm text-gray-500">得標門檻 (第{stock}名)</div>
          <div className="text-2xl font-bold text-orange-600">{Number(minWinningScore).toFixed(2)}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-sm text-gray-500">可得標名額</div>
          <div className="text-2xl font-bold text-green-600">{stock}</div>
        </div>
      </div>

      {/* My Rank */}
      {myRank !== null && myRank !== undefined && (
        <div
          className={`mb-4 p-4 rounded-lg ${
            isWinningPosition(myRank)
              ? 'bg-green-100 border border-green-300'
              : 'bg-yellow-100 border border-yellow-300'
          }`}
        >
          <div className="flex justify-between items-center">
            <div>
              <span className="text-sm font-medium">我的排名</span>
              <span
                className={`ml-2 text-2xl font-bold ${
                  isWinningPosition(myRank) ? 'text-green-700' : 'text-yellow-700'
                }`}
              >
                #{myRank}
              </span>
            </div>
            <div>
              <span className="text-sm font-medium">我的積分</span>
              <span className="ml-2 text-xl font-bold text-gray-800">
                {myScore != null ? Number(myScore).toFixed(2) : '-'}
              </span>
            </div>
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                isWinningPosition(myRank)
                  ? 'bg-green-200 text-green-800'
                  : 'bg-yellow-200 text-yellow-800'
              }`}
            >
              {isWinningPosition(myRank) ? '暫定得標' : '未得標'}
            </span>
          </div>
        </div>
      )}

      {/* Rankings Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="px-4 py-3 text-sm font-medium text-gray-500">排名</th>
              <th className="px-4 py-3 text-sm font-medium text-gray-500">用戶</th>
              <th className="px-4 py-3 text-sm font-medium text-gray-500 text-right">出價</th>
              <th className="px-4 py-3 text-sm font-medium text-gray-500 text-right">積分</th>
              <th className="px-4 py-3 text-sm font-medium text-gray-500 text-center">狀態</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {rankings.map((entry) => {
              const isCurrentUser = entry.user_id === currentUserId;
              const isWinning = isWinningPosition(entry.rank);

              return (
                <tr
                  key={entry.user_id}
                  className={`
                    ${isCurrentUser ? 'bg-blue-50' : ''}
                    ${isWinning ? 'bg-green-50' : ''}
                    ${isCurrentUser && isWinning ? 'bg-green-100' : ''}
                    hover:bg-gray-50 transition
                  `}
                >
                  <td className="px-4 py-3">
                    <span
                      className={`
                        inline-flex items-center justify-center w-8 h-8 rounded-full
                        ${entry.rank === 1 ? 'bg-yellow-400 text-yellow-900' : ''}
                        ${entry.rank === 2 ? 'bg-gray-300 text-gray-700' : ''}
                        ${entry.rank === 3 ? 'bg-orange-400 text-orange-900' : ''}
                        ${entry.rank > 3 ? 'bg-gray-100 text-gray-600' : ''}
                        font-bold text-sm
                      `}
                    >
                      {entry.rank}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`font-medium ${isCurrentUser ? 'text-blue-600' : 'text-gray-800'}`}>
                      {entry.username}
                      {isCurrentUser && ' (你)'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-800">
                    ${Number(entry.price).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-blue-600">
                    {Number(entry.score).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`
                        px-2 py-1 rounded-full text-xs font-medium
                        ${isWinning ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}
                      `}
                    >
                      {isWinning ? '暫定得標' : '未得標'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {rankings.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            尚無出價記錄
          </div>
        )}
      </div>
    </div>
  );
}
