/**
 * SyntheticBanner.tsx
 * Persistent, non-dismissible data provenance banner.
 * Shown whenever provenance.is_synthetic === true (default in MVP).
 */
import React from 'react';
import { useDashboardStore } from '../../store/dashboardStore';

export const SyntheticBanner: React.FC = () => {
  const isSynthetic = useDashboardStore((s) => s.isSynthetic);
  if (!isSynthetic) return null;
  return (
    <div className="synthetic-banner">
      <span className="synthetic-banner__icon">⚠</span>
      <span>
        <strong>DATA STATUS: MVP / SYNTHETIC TEST DATA</strong>
        {' '}— This investigation is based on synthetic test data and must not be used as actual forensic evidence.
      </span>
    </div>
  );
};
