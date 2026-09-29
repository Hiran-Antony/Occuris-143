import React, { useState } from 'react';
import type { VesselRankingEvidence } from '../../types';
import { rankingApi } from '../../api/client';

interface ForensicEvidenceCardProps {
  vessel: VesselRankingEvidence;
  caseId: string;
  isSelected?: boolean;
  onSelect?: () => void;
  onDecisionLogged?: (vesselId: string, decision: string) => void;
}

export const ForensicEvidenceCard: React.FC<ForensicEvidenceCardProps> = ({
  vessel,
  caseId,
  isSelected = false,
  onSelect,
  onDecisionLogged,
}) => {
  const [decisionModalOpen, setDecisionModalOpen] = useState<boolean>(false);
  const [selectedDecision, setSelectedDecision] = useState<'follow_up' | 'reject_with_reason' | 'ambiguous' | 'insufficient' | null>(null);
  const [analystNote, setAnalystNote] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [loggedDecision, setLoggedDecision] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const lowerBound = vessel.posterior_interval ? vessel.posterior_interval[0] : Math.max(0, vessel.posterior - 0.15);
  const upperBound = vessel.posterior_interval ? vessel.posterior_interval[1] : Math.min(1, vessel.posterior + 0.15);
  const meanVal = vessel.posterior;

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'HIGH':
        return { bg: 'rgba(255, 51, 102, 0.18)', border: 'var(--red, #ff3366)', color: 'var(--red, #ff3366)', label: 'HIGH PRIORITY' };
      case 'MEDIUM':
        return { bg: 'rgba(255, 184, 0, 0.18)', border: 'var(--amber, #ffb800)', color: 'var(--amber, #ffb800)', label: 'MEDIUM PRIORITY' };
      case 'AMBIGUOUS':
        return { bg: 'rgba(255, 136, 0, 0.18)', border: '#ff8800', color: '#ff8800', label: 'AMBIGUOUS ATTRIBUTION' };
      case 'INSUFFICIENT_DATA':
        return { bg: 'rgba(125, 160, 180, 0.18)', border: 'var(--text-muted, #7da0b4)', color: 'var(--text-muted, #7da0b4)', label: 'INSUFFICIENT DATA' };
      default:
        return { bg: 'rgba(0, 212, 255, 0.12)', border: 'var(--cyan, #00d4ff)', color: 'var(--cyan, #00d4ff)', label: 'LOW PRIORITY' };
    }
  };

  const getStateChip = (state: string) => {
    switch (state) {
      case 'AIS_GAP_DARK':
        return { bg: 'rgba(255, 51, 102, 0.2)', color: 'var(--red, #ff3366)', label: 'AIS_GAP_DARK' };
      case 'REPORTING_ANOMALY':
        return { bg: 'rgba(255, 184, 0, 0.2)', color: 'var(--amber, #ffb800)', label: 'REPORTING_ANOMALY' };
      case 'AMBIGUOUS':
        return { bg: 'rgba(255, 136, 0, 0.2)', color: '#ff8800', label: 'AMBIGUOUS' };
      default:
        return { bg: 'rgba(0, 255, 136, 0.15)', color: 'var(--green, #00ff88)', label: 'NORMAL AIS' };
    }
  };

  const priorityBadge = getPriorityBadge(vessel.priority);
  const stateChip = getStateChip(vessel.ais_state);

  const handleOpenDecisionModal = (decision: 'follow_up' | 'reject_with_reason' | 'ambiguous' | 'insufficient', e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedDecision(decision);
    setAnalystNote('');
    setDecisionModalOpen(true);
  };

  const handleSubmitDecision = async () => {
    if (!selectedDecision) return;
    setSubmitting(true);
    try {
      await rankingApi.submitAnalystDecision({
        vessel_id: vessel.vessel_id,
        case_id: caseId,
        decision: selectedDecision,
        note: analystNote,
        analyst_id: 'forensic_officer_01',
      });
      setLoggedDecision(selectedDecision);
      setDecisionModalOpen(false);
      setToastMessage(`Disposition '${selectedDecision}' logged for ${vessel.vessel_id}`);
      if (onDecisionLogged) {
        onDecisionLogged(vessel.vessel_id, selectedDecision);
      }
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err) {
      console.error('Failed to submit analyst decision', err);
      alert('Error recording analyst disposition. Check backend status.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      id={`evidence-card-${vessel.vessel_id}`}
      onClick={onSelect}
      style={{
        background: isSelected ? 'rgba(0, 212, 255, 0.08)' : 'var(--bg-card, rgba(10, 30, 60, 0.35))',
        border: `1px solid ${isSelected ? 'var(--cyan, #00d4ff)' : 'var(--border, rgba(0, 212, 255, 0.18))'}`,
        borderRadius: '10px',
        padding: '16px 20px',
        marginBottom: '14px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        boxShadow: isSelected ? '0 0 16px rgba(0, 212, 255, 0.2)' : 'none',
        position: 'relative',
      }}
    >
      {/* Toast Alert */}
      {toastMessage && (
        <div
          role="status"
          style={{
            position: 'absolute',
            top: '-12px',
            right: '20px',
            background: 'var(--green, #00ff88)',
            color: '#000000',
            fontSize: '11px',
            fontWeight: 700,
            padding: '4px 10px',
            borderRadius: '4px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
            zIndex: 10,
          }}
        >
          ✓ {toastMessage}
        </div>
      )}

      {/* Card Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <h4 style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #ffffff)', margin: 0 }}>
              {vessel.vessel_name || vessel.vessel_id}
            </h4>
            <span
              style={{
                fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
                fontSize: '11px',
                color: 'var(--text-muted, #7da0b4)',
              }}
            >
              ID: {vessel.vessel_id}
            </span>
            <span
              style={{
                fontSize: '10px',
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: '4px',
                backgroundColor: stateChip.bg,
                color: stateChip.color,
                fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
              }}
            >
              {stateChip.label}
            </span>
          </div>

          <div style={{ fontSize: '11px', color: 'var(--text-secondary, #a8d5e5)', display: 'flex', gap: '14px' }}>
            <span>Type: <strong>{vessel.vessel_type || 'Tanker'}</strong></span>
            <span>Origin Distance: <strong>{vessel.spatial_distance_km ? `${vessel.spatial_distance_km.toFixed(1)} km` : '0.4 km'}</strong></span>
            <span>Temporal Overlap: <strong>{vessel.temporal_overlap || 'FULL'}</strong></span>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <span
            style={{
              fontSize: '11px',
              fontWeight: 800,
              padding: '3px 8px',
              borderRadius: '4px',
              backgroundColor: priorityBadge.bg,
              border: `1px solid ${priorityBadge.border}`,
              color: priorityBadge.color,
              fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
              letterSpacing: '0.4px',
            }}
          >
            {priorityBadge.label}
          </span>
          {loggedDecision && (
            <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--green, #00ff88)', fontWeight: 600 }}>
              ✓ Decision: {loggedDecision.toUpperCase()}
            </div>
          )}
        </div>
      </div>

      {/* Posterior Interval Bar */}
      <div style={{ marginBottom: '14px', background: 'rgba(0,0,0,0.25)', padding: '10px 14px', borderRadius: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary, #a8d5e5)' }}>
            Posterior Probability & Sensitivity Interval [P(Source | Evidence)]:
          </span>
          <span
            style={{
              fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
              fontSize: '12px',
              fontWeight: 700,
              color: 'var(--cyan, #00d4ff)',
            }}
          >
            {(meanVal * 100).toFixed(1)}% <span style={{ color: 'var(--text-muted, #7da0b4)', fontSize: '10px' }}>[{ (lowerBound * 100).toFixed(1) }% – { (upperBound * 100).toFixed(1) }%]</span>
          </span>
        </div>

        {/* Visual Interval Track */}
        <div
          style={{
            position: 'relative',
            height: '10px',
            background: 'rgba(255, 255, 255, 0.08)',
            borderRadius: '5px',
            overflow: 'hidden',
          }}
        >
          {/* Shaded Interval Range */}
          <div
            style={{
              position: 'absolute',
              left: `${Math.max(0, lowerBound * 100)}%`,
              width: `${Math.min(100, (upperBound - lowerBound) * 100)}%`,
              height: '100%',
              background: 'rgba(0, 212, 255, 0.4)',
              borderRadius: '3px',
            }}
          />
          {/* Mean marker line/dot */}
          <div
            style={{
              position: 'absolute',
              left: `calc(${meanVal * 100}% - 4px)`,
              top: '1px',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#ffffff',
              boxShadow: '0 0 6px var(--cyan, #00d4ff)',
            }}
          />
        </div>
      </div>

      {/* Likelihood Ratio (LR) Breakdown Chips */}
      {vessel.lr_breakdown && vessel.lr_breakdown.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-muted, #7da0b4)', textTransform: 'uppercase', marginBottom: '5px', letterSpacing: '0.4px' }}>
            Top Likelihood Ratio Factors (Bayes Evidence Strength):
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {vessel.lr_breakdown.slice(0, 3).map((lr, idx) => (
              <span
                key={idx}
                title={lr.rationale}
                style={{
                  fontSize: '10px',
                  fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
                  background: 'rgba(0, 212, 255, 0.1)',
                  border: '1px solid rgba(0, 212, 255, 0.25)',
                  color: 'var(--cyan, #00d4ff)',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  cursor: 'help',
                }}
              >
                {lr.factor_name.replace(/_/g, ' ')}: <strong>LR {lr.likelihood_ratio.toFixed(1)}</strong>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Sensitivity Breakdown Bars */}
      {vessel.sensitivity && vessel.sensitivity.length > 0 && (
        <div style={{ marginBottom: '14px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-muted, #7da0b4)', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.4px' }}>
            Leave-One-Out Sensitivity Analysis (Factor Contribution):
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {vessel.sensitivity.slice(0, 2).map((sens, idx) => {
              const influenceColor = sens.influence === 'HIGH' ? 'var(--red, #ff3366)' : (sens.influence === 'MEDIUM' ? 'var(--amber, #ffb800)' : 'var(--cyan, #00d4ff)');
              return (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px' }}>
                  <span style={{ width: '130px', color: 'var(--text-secondary, #a8d5e5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {sens.factor_name}
                  </span>
                  <div style={{ flex: 1, height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.min(100, Math.max(10, sens.delta * 120))}%`,
                        background: influenceColor,
                      }}
                    />
                  </div>
                  <span style={{ fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace", color: influenceColor, fontWeight: 700 }}>
                    Δ {sens.delta.toFixed(3)} ({sens.influence})
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Analyst Decision Loop Action Bar */}
      <div
        style={{
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          paddingTop: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: '11px', color: 'var(--text-muted, #7da0b4)', fontWeight: 600 }}>
          Analyst Review Action:
        </span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={(e) => handleOpenDecisionModal('follow_up', e)}
            style={{
              background: 'rgba(0, 212, 255, 0.15)',
              border: '1px solid var(--cyan, #00d4ff)',
              color: 'var(--cyan, #00d4ff)',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Follow Up
          </button>
          <button
            onClick={(e) => handleOpenDecisionModal('reject_with_reason', e)}
            style={{
              background: 'rgba(255, 51, 102, 0.15)',
              border: '1px solid var(--red, #ff3366)',
              color: 'var(--red, #ff3366)',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Reject
          </button>
          <button
            onClick={(e) => handleOpenDecisionModal('ambiguous', e)}
            style={{
              background: 'rgba(255, 184, 0, 0.15)',
              border: '1px solid var(--amber, #ffb800)',
              color: 'var(--amber, #ffb800)',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Mark Ambiguous
          </button>
          <button
            onClick={(e) => handleOpenDecisionModal('insufficient', e)}
            style={{
              background: 'rgba(125, 160, 180, 0.15)',
              border: '1px solid var(--text-muted, #7da0b4)',
              color: 'var(--text-muted, #7da0b4)',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Insufficient
          </button>
        </div>
      </div>

      {/* Decision Modal */}
      {decisionModalOpen && (
        <div
          role="dialog"
          aria-labelledby="decision-dialog-title"
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              background: 'var(--bg-secondary, #0a1b33)',
              border: '1px solid var(--border, rgba(0, 212, 255, 0.3))',
              borderRadius: '10px',
              padding: '24px',
              width: '90%',
              maxWidth: '460px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.8)',
            }}
          >
            <h3 id="decision-dialog-title" style={{ fontSize: '15px', fontWeight: 800, color: '#ffffff', marginBottom: '8px' }}>
              Confirm Analyst Decision: {selectedDecision?.replace('_', ' ').toUpperCase()}
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary, #a8d5e5)', marginBottom: '14px' }}>
              Target Vessel: <strong>{vessel.vessel_name || vessel.vessel_id}</strong> (Case: {caseId})
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted, #7da0b4)', marginBottom: '4px' }}>
                Operational Rationale & Forensic Notes (Optional):
              </label>
              <textarea
                value={analystNote}
                onChange={(e) => setAnalystNote(e.target.value)}
                placeholder="e.g., Vessel AIS gap matches radar corridor; schedule port state inspection at destination..."
                rows={4}
                style={{
                  width: '100%',
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid var(--border, rgba(0, 212, 255, 0.2))',
                  borderRadius: '6px',
                  color: '#ffffff',
                  padding: '8px 10px',
                  fontSize: '12px',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setDecisionModalOpen(false)}
                disabled={submitting}
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.2)',
                  color: 'var(--text-secondary, #a8d5e5)',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitDecision}
                disabled={submitting}
                style={{
                  background: 'var(--cyan, #00d4ff)',
                  border: 'none',
                  color: '#000000',
                  padding: '6px 16px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {submitting ? 'Recording...' : 'Submit Decision'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ForensicEvidenceCard;
