/**
 * StatusBadge.tsx — Evidence state badge.
 * Only four states are allowed. CULPRIT/GUILTY etc are never rendered.
 */
import React from 'react';
import type { EvidenceState } from '../../types/investigation';

const STATE_CONFIG: Record<EvidenceState, { label: string; cls: string }> = {
  SUPPORTED: { label: 'SUPPORTED', cls: 'badge--supported' },
  PARTIALLY_SUPPORTED: { label: 'PARTIALLY SUPPORTED', cls: 'badge--partial' },
  CONTRADICTED: { label: 'CONTRADICTED', cls: 'badge--contradicted' },
  INSUFFICIENT_DATA: { label: 'INSUFFICIENT DATA', cls: 'badge--insufficient' },
};

interface Props {
  state: EvidenceState;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<Props> = ({ state, size = 'md' }) => {
  const cfg = STATE_CONFIG[state];
  return (
    <span className={`status-badge ${cfg.cls} status-badge--${size}`}>
      {cfg.label}
    </span>
  );
};
