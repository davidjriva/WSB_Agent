import { useState, useMemo } from 'react';
import { MessageSquare, BadgeCheck, Clock, TrendingUp, TrendingDown, Minus, Info, X, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { Signal } from '../hooks/useAgentData';

interface Props {
  signals: Signal[];
}

export function SignalFeed({ signals }: Props) {
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'timestamp' | 'score' | 'confidence' | 'ticker'>('timestamp');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const sortedSignals = useMemo(() => {
    return [...signals].sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'timestamp') {
        comparison = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
      } else if (sortBy === 'score') {
        comparison = a.score - b.score;
      } else if (sortBy === 'confidence') {
        comparison = a.confidence - b.confidence;
      } else if (sortBy === 'ticker') {
        comparison = a.ticker.localeCompare(b.ticker);
      }
      return sortOrder === 'desc' ? -comparison : comparison;
    });
  }, [signals, sortBy, sortOrder]);

  const toggleSort = (field: typeof sortBy) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder(field === 'ticker' ? 'asc' : 'desc');
    }
  };

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: '1.1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <MessageSquare size={20} color="var(--accent-brand)" />
          Agent's Thoughts & Signal Stream
        </h2>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255, 255, 255, 0.03)', padding: '0.25rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          {[
            { id: 'timestamp', label: 'Time', icon: Clock },
            { id: 'score', label: 'Score', icon: TrendingUp },
            { id: 'confidence', label: 'Conf.', icon: BadgeCheck },
            { id: 'ticker', label: 'Ticker', icon: null }
          ].map((option) => (
            <button
              key={option.id}
              onClick={() => toggleSort(option.id as any)}
              style={{
                background: sortBy === option.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                border: 'none',
                borderRadius: '6px',
                padding: '0.35rem 0.6rem',
                color: sortBy === option.id ? 'var(--accent-brand)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.7rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                transition: 'all 0.2s',
                borderBottom: sortBy === option.id ? '1px solid var(--accent-brand)' : '1px solid transparent'
              }}
            >
              {option.label}
              {sortBy === option.id && (
                sortOrder === 'desc' ? <ArrowDown size={10} /> : <ArrowUp size={10} />
              )}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto', maxHeight: '600px', paddingRight: '0.5rem' }}>
        {sortedSignals.length > 0 ? (
          sortedSignals.map((signal, idx) => (
            <div 
              key={`${signal.ticker}-${idx}`} 
              style={{ 
                padding: '1.25rem', 
                background: 'rgba(255, 255, 255, 0.03)', 
                border: '1px solid var(--border-color)', 
                borderRadius: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                animation: 'slideIn 0.3s ease-out'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '0.05em' }}>
                    ${signal.ticker}
                  </div>
                  <div 
                    style={{ 
                      padding: '0.25rem 0.75rem', 
                      borderRadius: '9999px', 
                      fontSize: '0.75rem', 
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      background: signal.action === 'BUY' ? 'rgba(16, 185, 129, 0.1)' : 
                                 signal.action === 'SELL' ? 'rgba(239, 68, 68, 0.1)' : 
                                 'rgba(107, 114, 128, 0.1)',
                      color: signal.action === 'BUY' ? 'var(--accent-buy)' : 
                             signal.action === 'SELL' ? 'var(--accent-sell)' : 
                             'var(--accent-neutral)',
                      border: `1px solid ${
                        signal.action === 'BUY' ? 'rgba(16, 185, 129, 0.2)' : 
                        signal.action === 'SELL' ? 'rgba(239, 68, 68, 0.2)' : 
                        'rgba(107, 114, 128, 0.2)'
                      }`,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem'
                    }}
                  >
                    {signal.action === 'BUY' && <TrendingUp size={12} />}
                    {signal.action === 'SELL' && <TrendingDown size={12} />}
                    {signal.action === 'HOLD' && <Minus size={12} />}
                    {signal.action}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                  <button
                    onClick={() => setSelectedSignal(signal)}
                    style={{
                      background: 'rgba(59, 130, 246, 0.1)',
                      border: '1px solid rgba(59, 130, 246, 0.2)',
                      borderRadius: '6px',
                      padding: '0.35rem',
                      color: 'var(--accent-brand)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.2s',
                    }}
                    title="View Detailed Analysis"
                  >
                    <Info size={16} />
                  </button>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <BadgeCheck size={16} color="var(--accent-brand)" />
                      {(signal.confidence * 100).toFixed(0)}% Conf.
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Clock size={16} />
                      {formatDistanceToNow(new Date(signal.timestamp), { addSuffix: true })}
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ color: 'var(--text-primary)', fontSize: '0.95rem', lineHeight: 1.6, fontStyle: 'italic', paddingLeft: '0.5rem', borderLeft: '2px solid var(--accent-brand)' }}>
                "{signal.reasoning}"
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.25rem' }}>
                <div style={{ flex: 1, height: '4px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '2px', overflow: 'hidden' }}>
                  <div 
                    style={{ 
                      height: '100%', 
                      width: `${((signal.score + 1) / 2) * 100}%`, 
                      background: signal.score > 0 ? 'var(--accent-buy)' : 'var(--accent-sell)',
                      opacity: 0.6
                    }} 
                  />
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                  SENTIMENT: {signal.score > 0 ? '+' : ''}{signal.score.toFixed(2)}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
            No signals generated yet. The agent is currently scanning WallStreetBets...
          </div>
        )}
      </div>

      {selectedSignal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          backdropFilter: 'blur(8px)',
        }}>
          <div style={{
            background: '#0f172a',
            border: '1px solid var(--border-color)',
            borderRadius: '16px',
            width: '90%',
            maxWidth: '600px',
            maxHeight: '80vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
          }}>
            <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <BadgeCheck size={24} color="var(--accent-brand)" />
                <h3 style={{ margin: 0, fontSize: '1.25rem' }}>Deep Analysis: ${selectedSignal.ticker}</h3>
              </div>
              <button onClick={() => setSelectedSignal(null)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                <X size={24} />
              </button>
            </div>
            <div style={{ padding: '1.5rem', overflowY: 'auto' }}>
              <section style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ color: 'var(--text-secondary)', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>Component Scores</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                  {selectedSignal.components ? Object.entries(selectedSignal.components).map(([key, val]) => {
                    const tooltips: Record<string, string> = {
                      sentiment: "Llama 3.2 NLP analysis. Measures bullish/bearish sentiment in social text. Range: -1 (bearish) to +1 (bullish).",
                      velocity: "Rate of change in mention frequency. High velocity (>10/hr) amplifies the sentiment direction.",
                      volume: "Unusual market trading volume relative to 20d average. Multiplies the conviction of the social signal.",
                      momentum: "5-day historical price momentum. Normalized to 1.0 at +/- 10% price change."
                    };
                    return (
                      <div key={key} style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.35rem', position: 'relative' }}>
                          {key}
                          <span 
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveTooltip(activeTooltip === key ? null : key);
                            }}
                            onMouseEnter={() => setActiveTooltip(key)}
                            onMouseLeave={() => setActiveTooltip(null)}
                            style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                          >
                            <Info size={12} style={{ opacity: 0.5 }} />
                          </span>
                          {activeTooltip === key && (
                            <div style={{
                              position: 'absolute',
                              top: 'calc(100% + 10px)',
                              left: '0',
                              background: 'rgba(15, 23, 42, 0.95)',
                              backdropFilter: 'blur(8px)',
                              border: '1px solid var(--border-color)',
                              padding: '1rem',
                              borderRadius: '10px',
                              zIndex: 9999,
                              width: '240px',
                              fontSize: '0.8rem',
                              color: 'var(--text-secondary)',
                              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.6), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
                              lineHeight: '1.5',
                              textTransform: 'none',
                              pointerEvents: 'auto'
                            }}>
                              {/* Small arrow helper */}
                              <div style={{
                                position: 'absolute',
                                top: '-6px',
                                left: '12px',
                                width: '12px',
                                height: '12px',
                                background: '#1e293b',
                                borderLeft: '1px solid var(--border-color)',
                                borderTop: '1px solid var(--border-color)',
                                transform: 'rotate(45deg)',
                              }} />
                              
                              <div style={{ color: 'var(--accent-brand)', fontWeight: 700, marginBottom: '0.4rem', textTransform: 'uppercase', fontSize: '0.65rem', letterSpacing: '0.05em' }}>
                                {key} Breakdown
                              </div>
                              {tooltips[key]}
                            </div>
                          )}
                        </div>
                        <div style={{ fontSize: '1.1rem', fontWeight: 700, color: val > 0 ? 'var(--accent-buy)' : val < 0 ? 'var(--accent-sell)' : 'var(--text-secondary)' }}>
                          {val > 0 ? '+' : ''}{val.toFixed(2)}
                        </div>
                      </div>
                    );
                  }) : (
                    <div style={{ gridColumn: 'span 2', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>No component breakdown available.</div>
                  )}
                </div>
              </section>

              <section>
                <h4 style={{ color: 'var(--text-secondary)', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
                  {selectedSignal.metadata?.raw_analysis ? "Llama's Inner Monologue" : "Reasoning Trace"}
                </h4>
                <div style={{ 
                  background: '#020617', 
                  padding: '1.25rem', 
                  borderRadius: '12px', 
                  border: '1px solid var(--border-color)',
                  color: '#94a3b8',
                  fontSize: '0.9rem',
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
                }}>
                  {selectedSignal.metadata?.raw_analysis || selectedSignal.reasoning}
                </div>
              </section>
            </div>
            <div style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', textAlign: 'right' }}>
              <button 
                onClick={() => setSelectedSignal(null)} 
                style={{ 
                  padding: '0.5rem 1.5rem', 
                  background: 'var(--accent-brand)', 
                  border: 'none', 
                  borderRadius: '8px', 
                  color: 'white', 
                  fontWeight: 600, 
                  cursor: 'pointer' 
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
