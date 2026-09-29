import React from 'react';
import type { HypothesisPosterior } from '../../types';

interface HypothesisPanelProps {
  hypotheses: HypothesisPosterior[];
}

export const HypothesisPanel: React.FC<HypothesisPanelProps> = ({ hypotheses }) => {
  if (!hypotheses || hypotheses.length === 0) {
    return null;
  }

  const getHypothesisTitle = (h: HypothesisPosterior) => {
    if (h.hypothesis_id === 'H1') return 'H1: Single-Source Discharge';
    if (h.hypothesis_id === 'H2') return 'H2: Coordinated Two-Source Discharge';
    if (h.hypothesis_id === 'H3') return 'H3: Atmospheric Deposition / Natural Seep';
    if (h.hypothesis_id === 'H4') return 'H4: False Alarm / Biogenic Slicks';
    if (h.hypothesis_id === 'H5') return 'H5: Multi-Vessel Uncoordinated Spill';
    return h.description || h.hypothesis_id;
  };

  return (
    <div
      id="source-hypotheses-panel"
      style={{
        background: 'var(--bg-secondary, rgba(5, 20, 45, 0.5))',
        border: '1px solid var(--border, rgba(0, 212, 255, 0.2))',
        borderRadius: '8px',
        padding: '16px 20px',
        marginBottom: '20px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <h3 style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase', color: 'var(--cyan, #00d4ff)' }}>
            Source Hypotheses Evaluation (Bayesian Model Selection)
          </h3>
          <p style={{ fontSize: '11px', color: 'var(--text-muted, #7da0b4)', marginTop: '2px' }}>
            Multi-source hypothesis testing penalized by Bayesian Information Criterion (BIC)
          </p>
        </div>
        <span
          style={{
            fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
            fontSize: '10px',
            color: 'var(--text-muted, #7da0b4)',
            background: 'rgba(0, 212, 255, 0.08)',
            padding: '3px 8px',
            borderRadius: '4px',
            border: '1px solid rgba(0, 212, 255, 0.15)',
          }}
        >
          Occuris M8 Hypotheses
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
        {hypotheses.map(h => {
          const pct = Math.round(h.posterior * 100);
          const isPreferred = h.posterior >= 0.5;
          const isInsufficient = h.status === 'INSUFFICIENT_DATA';

          return (
            <div
              key={h.hypothesis_id}
              style={{
                background: isPreferred ? 'rgba(0, 212, 255, 0.08)' : 'var(--bg-card, rgba(10, 30, 60, 0.35))',
                border: `1px solid ${isPreferred ? 'rgba(0, 212, 255, 0.4)' : 'rgba(255, 255, 255, 0.06)'}`,
                borderRadius: '6px',
                padding: '12px 14px',
                position: 'relative',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: isPreferred ? '#ffffff' : 'var(--text-secondary, #a8d5e5)' }}>
                  {getHypothesisTitle(h)}
                </span>
                <span
                  style={{
                    fontSize: '14px',
                    fontWeight: 800,
                    fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
                    color: isPreferred ? 'var(--cyan, #00d4ff)' : 'var(--text-muted, #7da0b4)',
                  }}
                >
                  {isInsufficient ? 'N/A' : `${(h.posterior * 100).toFixed(1)}%`}
                </span>
              </div>

              {/* Progress bar */}
              <div
                style={{
                  height: '5px',
                  width: '100%',
                  background: 'rgba(255, 255, 255, 0.1)',
                  borderRadius: '3px',
                  overflow: 'hidden',
                  marginBottom: '8px',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.max(pct, isPreferred ? 5 : 0)}%`,
                    background: isPreferred ? 'var(--cyan, #00d4ff)' : 'var(--text-muted, #7da0b4)',
                    borderRadius: '3px',
                    transition: 'width 0.4s ease-out',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted, #7da0b4)' }}>
                <span>BIC Penalty: {h.bic_penalty ? h.bic_penalty.toFixed(2) : '0.00'}</span>
                <span
                  style={{
                    color: isInsufficient ? 'var(--amber, #ffb800)' : (isPreferred ? 'var(--green, #00ff88)' : 'inherit'),
                    fontWeight: 600,
                  }}
                >
                  {isInsufficient ? 'INSUFFICIENT_DATA' : (isPreferred ? 'PREFERRED HYPOTHESIS' : 'REJECTED')}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default HypothesisPanel;
