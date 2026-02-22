import React, { useState, useEffect } from 'react';
import type { Signal } from '../hooks/useAgentData';
import { format } from 'date-fns';
import { Brain, Info, History } from 'lucide-react';

interface IntelligencePanelProps {
  ticker: string | null;
}

export const IntelligencePanel: React.FC<IntelligencePanelProps> = ({ ticker }) => {
  const [history, setHistory] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    
    const fetchTickerHistory = async () => {
      setLoading(true);
      try {
        const res = await fetch(`http://localhost:8000/signals/${ticker}`);
        const data = await res.json();
        setHistory(data);
      } catch (err) {
        console.error("Error fetching ticker history:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchTickerHistory();
  }, [ticker]);

  if (!ticker) {
    return (
      <div className="detail-panel" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <Brain size={48} style={{ opacity: 0.2, marginBottom: '20px' }} />
        <h2 style={{ opacity: 0.4 }}>Select a Ticker for Deep Analysis</h2>
      </div>
    );
  }

  const latest = history[0];

  return (
    <div className="detail-panel">
      <div className="ticker-hero">
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Selected Asset</span>
          <h1 className="ticker-title">${ticker}</h1>
        </div>
        <div className="score-badge">
          Average Score: <span className="text-green">{latest?.score.toFixed(2) || '---'}</span>
        </div>
      </div>

      <div className="intelligence-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '15px' }}>
            <Brain size={18} className="text-green" /> Latest Extraction
          </h3>
          <p style={{ lineHeight: 1.6, opacity: 0.9 }}>
            {latest?.reasoning || 'No analysis available for this ticker.'}
          </p>
        </div>
        
        <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '15px' }}>
            <Info size={18} className="text-green" /> Confidence Level
          </h3>
          <div style={{ fontSize: '2rem', fontWeight: 800 }}>
            {(latest?.confidence || 0 * 100).toFixed(0)}%
          </div>
          <div style={{ width: '100%', height: '8px', background: 'var(--bg-accent)', borderRadius: '4px', marginTop: '10px' }}>
            <div style={{ width: `${(latest?.confidence || 0) * 100}%`, height: '100%', background: 'var(--money-green)', borderRadius: '4px' }} />
          </div>
        </div>
      </div>

      <div>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '15px' }}>
          <History size={18} className="text-green" /> Signals Timeline
        </h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Action</th>
              <th>Score</th>
              <th>Confidence</th>
              <th>Reasoning Preview</th>
            </tr>
          </thead>
          <tbody>
            {history.map((s, idx) => (
              <tr key={idx}>
                <td style={{ color: 'var(--text-secondary)' }}>
                  {format(new Date(s.timestamp), 'MMM d, HH:mm:ss')}
                </td>
                <td style={{ fontWeight: 600 }} className={s.action === 'BUY' ? 'text-green' : s.action === 'SELL' ? 'text-red' : ''}>
                  {s.action}
                </td>
                <td style={{ fontFamily: 'monospace' }}>{s.score.toFixed(2)}</td>
                <td>{(s.confidence * 100).toFixed(0)}%</td>
                <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', opacity: 0.7 }}>
                  {s.reasoning}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
