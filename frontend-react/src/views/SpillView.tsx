/**
 * SpillView.tsx — Spill Investigation (M1/M2).
 * Shows side-by-side SAR image and Predicted Mask for a specific case.
 */
import React from 'react';
import { useDashboardStore } from '../store/dashboardStore';
import { SpillCasePanel } from '../components/spill/SpillCasePanel';
import { CASES } from '../data/cases';

export const SpillView: React.FC = () => {
  const selectedCase = useDashboardStore((s) => s.selectedCase);

  return (
    <div className="view-layout view-layout--spill">
      <div className="view-layout__main split-view">
        {selectedCase === 'all' ? (
          <div className="empty-state">
            <h2>Select a Case</h2>
            <p>Please select a specific case from the top header to view spill analysis.</p>
          </div>
        ) : (
          <>
            <div className="split-view__pane">
              <h3 className="split-view__title">SAR Observation</h3>
              <div className="split-view__image-wrapper">
                <img 
                  src={`/data/images/sar_${selectedCase.split('_')[1]}.png`} 
                  alt="SAR" 
                  className="split-view__image" 
                />
              </div>
            </div>
            <div className="split-view__pane">
              <h3 className="split-view__title">Predicted Mask (M1)</h3>
              <div className="split-view__image-wrapper">
                <img 
                  src={`/data/images/${selectedCase}_pred_mask.png`} 
                  alt="Mask" 
                  className="split-view__image split-view__image--mask" 
                />
              </div>
            </div>
          </>
        )}
      </div>
      <div className="view-layout__side">
        <SpillCasePanel caseId={selectedCase} />
      </div>
    </div>
  );
};
