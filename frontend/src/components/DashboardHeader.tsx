import { Radio } from 'lucide-react';
import type { Health } from '../hooks/useAgentData';

interface Props {
  health: Health | null;
}

export function DashboardHeader({ health }: Props) {
  const isOnline = health?.status === 'active';

  return (
    <div className="title-section">
      <h1>
        <div style={{ 
          width: '80px', 
          height: '80px', 
          background: 'radial-gradient(circle, rgba(16, 185, 129, 0.4) 0%, rgba(16, 185, 129, 0.1) 70%, transparent 100%)',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '8px',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          flexShrink: 0
        }}>
          <img src="/logo.svg" alt="WSB Agent Logo" style={{ width: '60px', height: '60px', filter: 'drop-shadow(0 0 15px rgba(16, 185, 129, 0.8))' }} />
        </div>
        WSB Agent <span style={{ opacity: 0.5, fontWeight: 300 }}>v{health?.version || '2.1.0'}</span>
      </h1>
      <div className={`status-badge ${!isOnline ? 'offline' : ''}`}>
        <Radio size={16} />
        <div className="dot" />
        {isOnline ? 'System Live' : 'System Offline'}
      </div>
    </div>
  );
}
