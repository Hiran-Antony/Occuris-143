/**
 * CrossingFeed.tsx — Real-time virtual gateway crossing feed.
 */
import React, { useEffect, useState } from 'react';
import { fetchGatewayEvents, type GatewayEvent } from '../../services/maritimeApi';

export const CrossingFeed: React.FC = () => {
  const [events, setEvents] = useState<GatewayEvent[]>([]);

  useEffect(() => {
    // In MVP, we fetch once. In real app, could poll or use WebSockets
    fetchGatewayEvents().then((data) => setEvents(data));
  }, []);

  return (
    <div className="panel crossing-feed">
      <div className="panel__header">
        <h2 className="panel__title">GATEWAY FEED</h2>
        <div className="panel__subtitle">Virtual Corridor Monitor (M5)</div>
      </div>
      <div className="panel__content" style={{ padding: 0 }}>
        {events.length === 0 ? (
          <div className="panel__content--empty">No gateway crossings detected.</div>
        ) : (
          <ul className="crossing-list">
            {events.map((ev, i) => (
              <li key={i} className="crossing-item">
                <div className={`crossing-icon crossing-icon--${ev.event_type.toLowerCase()}`}>
                  {ev.event_type === 'ENTRY' ? '↳' : '↱'}
                </div>
                <div className="crossing-details">
                  <div className="crossing-header">
                    <span className="crossing-vessel">{ev.vessel_name}</span>
                    <span className="crossing-time">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="crossing-sub">
                    {ev.event_type} {ev.gateway_id} · {ev.speed.toFixed(1)} kn
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
