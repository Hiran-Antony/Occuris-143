/**
 * MaritimePlayback — AIS Replay timeline controls.
 *
 * The playback range is derived dynamically from the actual loaded AIS tracks.
 * No dates are hardcoded here. If the dataset changes, the timeline updates automatically.
 *
 * Labels this as "AIS REPLAY" (not "LIVE") because the data source is CSV-based test data.
 */
import { useEffect, useMemo, useCallback, useRef } from 'react';
import { Play, Pause } from 'lucide-react';
import type { VesselTrack } from './VesselLayer';

interface Props {
  tracks: VesselTrack[];
  currentTimestamp: Date;
  isPlaying: boolean;
  onTimestampChange: (ts: Date | ((prev: Date) => Date)) => void;
  onPlayingChange: (playing: boolean) => void;
}

/**
 * Derive min/max timestamps from all vessel tracks.
 * This is the only place the replay range is calculated — from real AIS data.
 */
function deriveTimeRange(tracks: VesselTrack[]): { start: Date; end: Date } | null {
  let minMs = Infinity;
  let maxMs = -Infinity;

  for (const track of tracks) {
    for (const ping of track.positions) {
      const ms = new Date(ping.timestamp).getTime();
      if (ms < minMs) minMs = ms;
      if (ms > maxMs) maxMs = ms;
    }
  }

  if (minMs === Infinity || maxMs === -Infinity) return null;
  return { start: new Date(minMs), end: new Date(maxMs) };
}

function formatUTC(d: Date) {
  return d.toISOString().slice(11, 16) + ' UTC';
}

// 1 real second = 2 demo-minutes of AIS time (smooth replay speed)
const REPLAY_SPEED_MS_PER_REAL_MS = 120;

export default function MaritimePlayback({
  tracks,
  currentTimestamp,
  isPlaying,
  onTimestampChange,
  onPlayingChange,
}: Props) {
  const timeRange = useMemo(() => deriveTimeRange(tracks), [tracks]);
  const animRef = useRef<number | null>(null);
  const lastRealRef = useRef<number>(0);

  // Animation loop — advances timestamp by replay speed factor
  const animate = useCallback(
    (now: number) => {
      if (!timeRange) return;
      if (lastRealRef.current === 0) lastRealRef.current = now;
      const elapsed = now - lastRealRef.current;
      lastRealRef.current = now;

      onTimestampChange((prev: Date) => {
        const nextMs = prev.getTime() + elapsed * REPLAY_SPEED_MS_PER_REAL_MS;
        if (nextMs >= timeRange.end.getTime()) {
          onPlayingChange(false);
          return timeRange.end;
        }
        return new Date(nextMs);
      });
      animRef.current = requestAnimationFrame(animate);
    },
    [timeRange, onTimestampChange, onPlayingChange]
  );

  useEffect(() => {
    if (isPlaying) {
      lastRealRef.current = 0;
      animRef.current = requestAnimationFrame(animate);
    } else {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    }
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, animate]);

  if (!timeRange) {
    return (
      <div style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
        Loading AIS data...
      </div>
    );
  }

  const totalMs = timeRange.end.getTime() - timeRange.start.getTime();
  const progressFrac = totalMs > 0
    ? Math.min(1, (currentTimestamp.getTime() - timeRange.start.getTime()) / totalMs)
    : 0;
  const sliderVal = Math.round(progressFrac * 1000);

  const onSlider = (v: number) => {
    const ts = new Date(timeRange.start.getTime() + (v / 1000) * totalMs);
    onTimestampChange(ts);
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      {/* AIS REPLAY label */}
      <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', letterSpacing: '0.1em', color: '#00d4ff', background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.25)', borderRadius: 4, padding: '3px 8px', fontWeight: 700, whiteSpace: 'nowrap' }}>
        AIS REPLAY
      </div>

      {/* Play/Pause */}
      <button
        onClick={() => onPlayingChange(!isPlaying)}
        style={{
          background: isPlaying ? 'rgba(255,51,102,0.2)' : 'rgba(0,255,136,0.2)',
          border: `1px solid ${isPlaying ? '#ff3366' : '#00ff88'}`,
          color: isPlaying ? '#ff3366' : '#00ff88',
          borderRadius: 8,
          padding: '5px 14px',
          cursor: 'pointer',
          fontSize: 12,
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: 5,
        }}
      >
        {isPlaying ? <><Pause size={12} /> Pause</> : <><Play size={12} /> Play</>}
      </button>

      {/* Start time */}
      <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', whiteSpace: 'nowrap' }}>
        {formatUTC(timeRange.start)}
      </span>

      {/* Slider */}
      <input
        type="range"
        min={0}
        max={1000}
        value={sliderVal}
        onChange={e => onSlider(Number(e.target.value))}
        style={{ width: 200, accentColor: 'var(--cyan)' }}
      />

      {/* End time */}
      <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono', whiteSpace: 'nowrap' }}>
        {formatUTC(timeRange.end)}
      </span>

      {/* Current time display */}
      <div style={{ fontSize: 13, fontFamily: 'JetBrains Mono', color: 'var(--cyan)', background: 'var(--bg-card)', padding: '5px 12px', borderRadius: 8, border: '1px solid var(--border)', whiteSpace: 'nowrap' }}>
        {currentTimestamp.toISOString().slice(11, 16)} UTC
      </div>
    </div>
  );
}
