/**
 * SpillSplitView.tsx — M4 Source Hypothesis Testing view.
 */
import React, { useEffect, useState } from 'react';
import { useDashboardStore } from '../store/dashboardStore';
import { SpillSplitPanel } from '../components/spill/SpillSplitPanel';
import { OccurisMap } from '../map/OccurisMap';
import { SourceZoneLayer } from '../map/layers/SourceZoneLayer';
import type { SpillSplitResult } from '../types/investigation';
import { CASES } from '../data/cases';

export const SpillSplitView: React.FC = () => {
  const selectedCase = useDashboardStore((s) => s.selectedCase);
  const [data, setData] = useState<SpillSplitResult | null>(null);

  useEffect(() => {
    if (selectedCase === 'all') {
      setData(null);
      return;
    }
    
    fetch(`/data/processed/${selectedCase}_spillsplit.json`)
      .then(res => res.json())
      .then(d => setData(d))
      .catch(err => {
        console.error("Failed to fetch spillsplit for", selectedCase, err);
        setData(null);
      });
  }, [selectedCase]);

  return (
    <div className="view-layout view-layout--spillsplit">
      <div className="view-layout__main">
        {selectedCase === 'all' ? (
           <div className="empty-state">
             <h2>Select a Case</h2>
             <p>Select a case from the top header to evaluate multiple source hypotheses.</p>
           </div>
        ) : (
          <div className="view-layout__map-container">
            <OccurisMap center={CASES[selectedCase]?.spill_center ? [CASES[selectedCase].spill_center.lon, CASES[selectedCase].spill_center.lat] : undefined} zoom={7}>
              {data && (
                <SourceZoneLayer 
                  caseId={selectedCase} 
                  sourceZones={data.source_zones} 
                />
              )}
            </OccurisMap>
          </div>
        )}
      </div>
      <div className="view-layout__side">
        {selectedCase !== 'all' && <SpillSplitPanel data={data} />}
      </div>
    </div>
  );
};
