/**
 * KpiStrip.tsx — Top row of metric cards for the Monitoring View.
 * Dynamically computes values from actual case/module data.
 * No hardcoded values allowed.
 */
import React, { useEffect, useState } from 'react';
import { MetricCard } from '../common/MetricCard';
import { CASE_LIST } from '../../data/cases';

export const KpiStrip: React.FC = () => {
  const [totalSpillArea, setTotalSpillArea] = useState<number | null>(null);
  const [avgIou, setAvgIou] = useState<number | null>(null);
  const [lookAlikePass, setLookAlikePass] = useState<number | null>(null);
  
  // Real active cases count from actual loaded config
  const activeCases = CASE_LIST.length;

  useEffect(() => {
    // Fetch geometry for all cases to compute dynamic KPIs
    async function fetchKpis() {
      try {
        let areaSum = 0;
        let passCount = 0;
        let casesLoaded = 0;

        for (const c of CASE_LIST) {
          const res = await fetch(`/data/processed/${c.id}_geometry.json`);
          if (res.ok) {
            const data = await res.json();
            if (data.geometry?.area_km2) areaSum += data.geometry.area_km2;
            if (data.look_alike?.passed) passCount += 1;
            casesLoaded += 1;
          }
        }

        if (casesLoaded > 0) {
          setTotalSpillArea(Number(areaSum.toFixed(2)));
          setLookAlikePass(passCount);
        }

        // For MVP M8 Evidence average IoU could be fetched similarly
        // Mocking dynamic fetch logic for avgIou since M8 bundle fetching isn't done here yet
        // In real app, fetch /api/investigation/all/bundle
        setAvgIou(null); // Explicitly setting null to show INSUFFICIENT DATA until M8 is fully wired for aggregate

      } catch (err) {
        console.error("Failed to fetch KPI data", err);
      }
    }
    fetchKpis();
  }, []);

  return (
    <div className="kpi-strip">
      <MetricCard 
        label="Active Cases" 
        value={activeCases} 
        icon="📡"
      />
      <MetricCard 
        label="Look-Alike Pass" 
        value={lookAlikePass} 
        icon="✓"
      />
      <MetricCard 
        label="Total Spill Area" 
        value={totalSpillArea} 
        unit="km²" 
        caveat="PROVISIONAL GEOSPATIAL SCALE"
        highlight
        icon="🛢"
      />
      <MetricCard 
        label="Avg Confidence (IoU)" 
        value={avgIou} 
        icon="🎯"
      />
    </div>
  );
};
