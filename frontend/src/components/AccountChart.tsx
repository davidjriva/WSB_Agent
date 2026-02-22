import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer
} from 'recharts';
import { format } from 'date-fns';
import { Download } from 'lucide-react';
import type { ValuationEntry } from '../hooks/useAgentData';

interface AccountChartProps {
    data: ValuationEntry[];
}

export function AccountChart({ data = [] }: AccountChartProps) {
    // Sort chronological and take last 50
    const sortedData = (Array.isArray(data) ? [...data] : [])
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        .slice(-50);

    const formatXAxis = (tickItem: string) => {
        try {
            return format(new Date(tickItem), 'HH:mm');
        } catch {
            return tickItem;
        }
    };

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0,
        }).format(value);
    };

    const exportToCSV = () => {
        const headers = ['Timestamp', 'Total Equity', 'Cash'];
        const rows = data.map(entry => [
            entry.timestamp,
            entry.total_equity,
            entry.cash
        ]);

        const csvContent = [
            headers.join(','),
            ...rows.map(row => row.join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `portfolio_history_${format(new Date(), 'yyyy-MM-dd')}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    if (data.length === 0) {
        return (
            <div className="h-64 flex items-center justify-center text-slate-500 bg-slate-900/50 rounded-xl border border-slate-800">
                <p>Waiting for valuation telemetry...</p>
            </div>
        );
    }

    return (
        <div className="relative">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>ACCOUNT VALUATION HISTORY</div>
                <button
                    onClick={exportToCSV}
                    style={{
                        background: 'rgba(59, 130, 246, 0.1)',
                        border: '1px solid rgba(59, 130, 246, 0.2)',
                        borderRadius: '6px',
                        padding: '0.4rem 0.8rem',
                        color: 'var(--accent-brand)',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        transition: 'all 0.2s',
                    }}
                >
                    <Download size={14} />
                    EXPORT DATA
                </button>
            </div>
            <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sortedData}>
                    <defs>
                        <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis 
                        dataKey="timestamp" 
                        tickFormatter={formatXAxis} 
                        stroke="#64748b" 
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                    />
                    <YAxis 
                        domain={['auto', 'auto']} 
                        tickFormatter={formatCurrency}
                        stroke="#64748b"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        width={80}
                    />
                    <Tooltip 
                        contentStyle={{ 
                            backgroundColor: '#0f172a', 
                            border: '1px solid #1e293b',
                            borderRadius: '8px',
                            color: '#f8fafc' 
                        }}
                        formatter={(value: any) => {
                            if (value === undefined || value === null) return [formatCurrency(0), 'Equity'];
                            const val = Array.isArray(value) ? Number(value[0]) : Number(value);
                            return [formatCurrency(val), 'Equity'];
                        }}
                        labelFormatter={(label) => format(new Date(label), 'MMM d, HH:mm:ss')}
                    />
                    <Area 
                        type="monotone" 
                        dataKey="total_equity" 
                        stroke="#3b82f6" 
                        strokeWidth={2}
                        fillOpacity={1} 
                        fill="url(#colorEquity)" 
                        isAnimationActive={true}
                    />
                </AreaChart>
            </ResponsiveContainer>
            </div>
        </div>
    );
}
