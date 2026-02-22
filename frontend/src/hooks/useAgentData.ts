import { useState, useEffect } from 'react';

export interface Signal {
    ticker: string;
    score: number;
    action: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    reasoning: string;
    components: Record<string, number>;
    metadata: Record<string, any>;
    timestamp: string;
}

export interface Portfolio {
    balance: number;
    open_positions: string[];
}

export interface Health {
    status: string;
    version: string;
    database_connected: boolean;
    broker_type: string;
}

export type ValuationEntry = {
    total_equity: number;
    cash: number;
    timestamp: string;
};

const API_BASE_URL = 'http://localhost:8000';

export function useAgentData() {
    const [signals, setSignals] = useState<Signal[]>([]);
    const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
    const [history, setHistory] = useState<ValuationEntry[]>([]);
    const [health, setHealth] = useState<Health | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = async () => {
        try {
            const [signalsRes, portfolioRes, historyRes, healthRes] = await Promise.all([
                fetch(`${API_BASE_URL}/signals`),
                fetch(`${API_BASE_URL}/portfolio`),
                fetch(`${API_BASE_URL}/portfolio/history`),
                fetch(`${API_BASE_URL}/health`),
            ]);

            if (!signalsRes.ok || !portfolioRes.ok || !historyRes.ok || !healthRes.ok) {
                throw new Error('Failed to fetch data from API');
            }

            const [signalsData, portfolioData, historyData, healthData] = await Promise.all([
                signalsRes.json(),
                portfolioRes.json(),
                historyRes.json(),
                healthRes.json(),
            ]);

            setSignals(signalsData);
            setPortfolio(portfolioData);
            setHistory(historyData.history);
            setHealth(healthData);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000); // Poll every 5 seconds
        return () => clearInterval(interval);
    }, []);

    return { signals, portfolio, history, health, loading, error, refresh: fetchData };
}
