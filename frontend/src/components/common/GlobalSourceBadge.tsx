import React, { useState, useEffect } from 'react';

interface GlobalSourceBadgeProps {
  sourceMode?: string;
}

export const GlobalSourceBadge: React.FC<GlobalSourceBadgeProps> = ({ sourceMode = 'SYNTHETIC_REPLAY' }) => {
  const [utcTime, setUtcTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const timeStr = now.toISOString().substring(11, 19);
      setUtcTime(timeStr);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const isLive = sourceMode === 'LIVE_FEED';
  const label = isLive ? 'LIVE' : 'REPLAY';
  const sourceText = isLive ? 'Real-time Terrestrial & Satellite AIS' : 'Synthetic AIS Replay';
  const dotColor = isLive ? 'var(--green, #00ff88)' : 'var(--amber, #ffb800)';

  return (
    <div
      id="global-source-badge"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '5px 12px',
        background: 'rgba(6, 18, 36, 0.85)',
        border: '1px solid rgba(0, 212, 255, 0.25)',
        borderRadius: '6px',
        fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
        fontSize: '11px',
        color: 'var(--text-secondary, #a8d5e5)',
        letterSpacing: '0.4px',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.4)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        userSelect: 'none',
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: dotColor,
          boxShadow: `0 0 8px ${dotColor}`,
          animation: 'badgePulse 2s infinite ease-in-out',
        }}
      />
      <span style={{ fontWeight: 700, color: '#ffffff' }}>{label}</span>
      <span style={{ color: 'rgba(255, 255, 255, 0.3)' }}>|</span>
      <span>AIS Source: <strong style={{ color: 'var(--text-primary, #ffffff)', fontWeight: 600 }}>{sourceText}</strong></span>
      <span style={{ color: 'rgba(255, 255, 255, 0.3)' }}>|</span>
      <span>Time: <strong style={{ color: 'var(--cyan, #00d4ff)', fontWeight: 600 }}>{utcTime || '--:--:--'}</strong> UTC</span>
      <style>{`
        @keyframes badgePulse {
          0% { transform: scale(0.95); opacity: 0.7; }
          50% { transform: scale(1.15); opacity: 1; }
          100% { transform: scale(0.95); opacity: 0.7; }
        }
      `}</style>
    </div>
  );
};

export default GlobalSourceBadge;
