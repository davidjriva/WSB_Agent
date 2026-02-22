import React, { useState } from 'react';
import './App.css';
import { DashboardHeader } from './components/DashboardHeader';
import { AccountChart } from './components/AccountChart';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { useAgentData } from './hooks/useAgentData';
import { WatchlistSidebar } from './components/WatchlistSidebar';
import { IntelligencePanel } from './components/IntelligencePanel';

function App() {
  const { signals, portfolio, history, health, loading, error, refresh } = useAgentData();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  // If no ticker selected, select the first one from signals when they load
  React.useEffect(() => {
    if (signals.length > 0 && !selectedTicker) {
      setSelectedTicker(signals[0].ticker);
    }
  }, [signals, selectedTicker]);

  return (
    <div className="app-container">
      <DashboardHeader health={health} />
      
      {error && (
        <div className="error-banner">
          <AlertCircle /> 
          <span><strong>API Error:</strong> {error}. Make sure the backend server is running on port 8000.</span>
          <button onClick={refresh} style={{ marginLeft: 'auto' }}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}

      {!loading && signals && portfolio && history && health ? (
        <React.Fragment>
          {/* Top Summary Section (Full Width) */}
          <div style={{ padding: '20px 30px', borderBottom: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div className="portfolio-stats">
                <h3 style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>
                  Portfolio Equity
                </h3>
                <p style={{ fontSize: '2.5rem', color: 'var(--money-green)', fontWeight: 800, fontFamily: 'Outfit' }}>
                  ${portfolio.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
            </div>

            <AccountChart data={history} />
          </div>

          <div className="main-layout">
            <WatchlistSidebar 
              signals={signals} 
              activeTicker={selectedTicker} 
              onTickerSelect={setSelectedTicker} 
            />
            
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <IntelligencePanel ticker={selectedTicker} />
            </div>
          </div>
        </React.Fragment>
      ) : (
        <div className="loading-container">
          <div className="spinner" />
          <p>{loading ? 'Initializing Neural Link...' : 'Waiting for Agent...'}</p>
        </div>
      )}
    </div>
  );
}

export default App;
