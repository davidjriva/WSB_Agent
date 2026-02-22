import { Wallet, Briefcase, TrendingUp } from 'lucide-react';
import type { Portfolio } from '../hooks/useAgentData';

interface Props {
  portfolio: Portfolio | null;
}

export function PortfolioStats({ portfolio }: Props) {
  const balance = portfolio?.balance || 0;
  const positions = portfolio?.open_positions || [];

  return (
    <div className="glass-panel" style={{ height: 'fit-content' }}>
      <h2 style={{ fontSize: '1.1rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Briefcase size={20} color="var(--accent-brand)" />
        Portfolio Overview
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div>
          <label style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', display: 'block', marginBottom: '0.5rem' }}>
            Total Equity
          </label>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-buy)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Wallet size={24} />
            ${balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        <div>
          <label style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', display: 'block', marginBottom: '1rem' }}>
            Open Positions ({positions.length})
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {positions.length > 0 ? (
              positions.map((ticker) => (
                <div
                  key={ticker}
                  style={{
                    padding: '0.5rem 1rem',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                  }}
                >
                  <TrendingUp size={14} color="var(--accent-buy)" />
                  {ticker}
                </div>
              ))
            ) : (
              <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem', fontStyle: 'italic' }}>No active positions</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
