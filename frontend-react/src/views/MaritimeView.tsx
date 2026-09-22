/**
 * MaritimeView.tsx — Maritime Memory (M5).
 * Shows the AIS tracks, virtual gateways, and crossing events.
 */
import React, { useEffect, useState } from 'react';
import { OccurisMap } from '../map/OccurisMap';
import { VesselTrackLayer } from '../map/layers/VesselTrackLayer';
import { GatewayLayer } from '../map/layers/GatewayLayer';
import { VesselInspector } from '../components/maritime/VesselInspector';
import { CrossingFeed } from '../components/maritime/CrossingFeed';
import { useDashboardStore } from '../store/dashboardStore';
import { fetchVesselTrack } from '../services/maritimeApi';
import type { VesselTrack } from '../types/investigation';
import { MAP_DEFAULT_CENTER, MAP_DEFAULT_ZOOM } from '../data/cases';

const MOCK_VESSELS = ['V001', 'V002', 'V003', 'V004', 'V005']; // the 5 vessels in MVP

export const MaritimeView: React.FC = () => {
  const selectedVessel = useDashboardStore((s) => s.selectedVessel);
  const [tracks, setTracks] = useState<VesselTrack[]>([]);

  useEffect(() => {
    // Fetch all tracks initially
    Promise.all(MOCK_VESSELS.map(v => fetchVesselTrack(v)))
      .then((results) => {
        setTracks(results.filter((x): x is VesselTrack => x !== null));
      });
  }, []);

  const visibleTracks = selectedVessel === 'all' 
    ? tracks 
    : tracks.filter(t => t.vessel_id === selectedVessel);

  return (
    <div className="view-layout view-layout--maritime">
      <div className="view-layout__main">
        <div className="view-layout__map-container">
          <OccurisMap center={MAP_DEFAULT_CENTER} zoom={MAP_DEFAULT_ZOOM}>
            <GatewayLayer />
            <VesselTrackLayer tracks={visibleTracks} />
          </OccurisMap>
        </div>
      </div>
      <div className="view-layout__side">
        <VesselInspector />
        <CrossingFeed />
      </div>
    </div>
  );
};
