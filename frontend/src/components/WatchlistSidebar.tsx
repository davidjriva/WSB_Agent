import React from 'react';
import type { Signal } from '../hooks/useAgentData';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface WatchlistSidebarProps {
  signals: Signal[];
  activeTicker: string | null;
  onTickerSelect: (ticker: string) => void;
}

export const WatchlistSidebar: React.FC<WatchlistSidebarProps> = ({ 
  signals, 
  activeTicker, 
  onTickerSelect 
}) => {
  // Get unique tickers with their latest signal
  const latestByTicker: Record<string, Signal> = {};
  [...signals].reverse().forEach(s => {
    latestByTicker[s.ticker] = s;
  });

  const sortedTickers = Object.values(latestByTicker).sort((a, b) => b.score - a.score);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h3>Intelligence List</h3>
        <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.4)' }}>
          {sortedTickers.length} ASSETS
        </span>
      </div>
      <div className="watchlist-container">
        <table className="watchlist-table">
          <tbody>
            {sortedTickers.map((signal) => (
              <tr 
                key={signal.ticker}
                className={`watchlist-row ${activeTicker === signal.ticker ? 'active' : ''}`}
                onClick={() => onTickerSelect(signal.ticker)}
              >
                <td className="watchlist-cell ticker-label">
                  ${signal.ticker}
                </td>
                <td className={`watchlist-cell ${signal.action === 'BUY' ? 'text-green' : signal.action === 'SELL' ? 'text-red' : ''}`}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    {signal.action === 'BUY' && <TrendingUp size={12} />}
                    {signal.action === 'SELL' && <TrendingDown size={12} />}
                    {signal.action === 'HOLD' && <Minus size={12} />}
                    {signal.action}
                  </div>
                </td>
                <td className="watchlist-cell" style={{ textAlign: 'right', fontWeight: 600 }}>
                  {signal.score.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </aside>
  );
};
