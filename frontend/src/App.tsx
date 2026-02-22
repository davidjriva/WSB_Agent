import './App.css';
import { useAgentData } from './hooks/useAgentData';
import { DashboardHeader } from './components/DashboardHeader';
import { PortfolioStats } from './components/PortfolioStats';
import { SignalFeed } from './components/SignalFeed';
import { AccountChart } from './components/AccountChart';
import { AlertCircle, RefreshCw } from 'lucide-react';

function App() {
  const { signals, portfolio, history, health, loading, error, refresh } = useAgentData();

  if (loading && !health) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
        <RefreshCw className="animate-spin" size={24} color="var(--accent-brand)" />
        <span style={{ fontSize: '1.1rem', fontWeight: 500 }}>Initializing Neural Link...</span>
        <style>{`
          .animate-spin { animation: spin 1s linear infinite; }
          @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        `}</style>
      </div>
    );
  }

  return (
    <div className="app-container">
      <DashboardHeader health={health} />
      
      {error && (
        <div className="glass-panel" style={{ background: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.2)', color: 'var(--accent-sell)', display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem' }}>
          <AlertCircle size={20} />
          <span><strong>API Error:</strong> {error}. Make sure the backend server is running on port 8000.</span>
          <button 
            onClick={refresh}
            style={{ marginLeft: 'auto', background: 'transparent', border: '1px solid currentColor', color: 'inherit', padding: '0.25rem 0.75rem', borderRadius: '4px', cursor: 'pointer', fontSize: '0.875rem' }}
          >
            Retry
          </button>
        </div>
      )}

      <div style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-primary)' }}>Account Valuation History</h2>
        <AccountChart data={history} />
      </div>

      <div className="dashboard-grid">
        <PortfolioStats portfolio={portfolio} />
        <SignalFeed signals={signals} />
      </div>

      <footer style={{ marginTop: 'auto', textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', paddingTop: '2rem' }}>
        WSB Agent Dashboard &bull; AI-Powered Sentiment Intelligence &bull; Experimental Internal Tool
      </footer>
    </div>
  );
}

export default App;
