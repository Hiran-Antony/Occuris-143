/**
 * DataSourceBadge.tsx — Shows data origin: SYNTHETIC REPLAY, LIVE, etc.
 */
import React from 'react';

interface Props {
  mode: string;
  label?: string;
  recordCount?: number;
}

export const DataSourceBadge: React.FC<Props> = ({ mode, label, recordCount }) => {
  const isSynthetic = mode?.toLowerCase().includes('synthetic');
  return (
    <div className={`source-badge${isSynthetic ? ' source-badge--synthetic' : ' source-badge--live'}`}>
      <span className="source-badge__dot" />
      <span>
        {mode.replace(/_/g, ' ')}
        {label && ` · ${label}`}
        {recordCount !== undefined && ` (${recordCount} pings)`}
      </span>
    </div>
  );
};
