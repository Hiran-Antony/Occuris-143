import React from 'react';

export type CaseAttributionState = 'NORMAL' | 'AMBIGUOUS' | 'NO_STRONG_MATCH' | 'INSUFFICIENT_DATA';

interface StateBannerProps {
  state?: CaseAttributionState | string;
  customMessage?: string;
  onDismiss?: () => void;
}

export const StateBanner: React.FC<StateBannerProps> = ({ state, customMessage, onDismiss }) => {
  if (!state || state === 'NORMAL') {
    return null;
  }

  const isAmbiguous = state === 'AMBIGUOUS';
  const isNoMatch = state === 'NO_STRONG_MATCH';

  if (!isAmbiguous && !isNoMatch && !customMessage) {
    return null;
  }

  const bgColor = isAmbiguous
    ? 'rgba(255, 184, 0, 0.15)'
    : 'rgba(255, 51, 102, 0.15)';
  const borderColor = isAmbiguous
    ? 'rgba(255, 184, 0, 0.6)'
    : 'rgba(255, 51, 102, 0.6)';
  const textColor = isAmbiguous
    ? '#ffd166'
    : '#ff6b8b';
  const icon = isAmbiguous ? '⚠️' : '⛔';

  const defaultMessage = isAmbiguous
    ? 'Ambiguous Attribution: Top candidates have overlapping confidence intervals. Additional evidence required.'
    : 'No Strong Source Match: No vessel adequately explains the observed slick under current assumptions.';

  return (
    <div
      id="state-banner"
      role="alert"
      style={{
        width: '100%',
        padding: '10px 20px',
        backgroundColor: bgColor,
        borderBottom: `1px solid ${borderColor}`,
        borderTop: `1px solid ${borderColor}`,
        color: textColor,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '13px',
        fontWeight: 600,
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
        animation: 'fadeIn 0.3s ease-in',
        zIndex: 50,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ fontSize: '16px' }}>{icon}</span>
        <span>{customMessage || defaultMessage}</span>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          style={{
            background: 'transparent',
            border: 'none',
            color: textColor,
            cursor: 'pointer',
            fontSize: '14px',
            padding: '2px 8px',
          }}
          aria-label="Dismiss banner"
        >
          ✕
        </button>
      )}
    </div>
  );
};

export default StateBanner;
