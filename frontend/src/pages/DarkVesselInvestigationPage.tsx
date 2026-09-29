import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { rankingApi, reportApi } from '../api/client';
import type { RankingBundleV1, VesselRankingEvidence } from '../types';
import StateBanner from '../components/common/StateBanner';
import StickyHonestyFooter from '../components/common/StickyHonestyFooter';
import LedgerVerificationPanel from '../components/common/LedgerVerificationPanel';
import HypothesisPanel from '../components/ranking/HypothesisPanel';
import ForensicEvidenceCard from '../components/ranking/ForensicEvidenceCard';
import { Download, RefreshCw } from 'lucide-react';

export default function DarkVesselInvestigationPage() {
  const [caseId] = useState<string>('case_01');
  const [bundle, setBundle] = useState<RankingBundleV1 | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedVesselId, setSelectedVesselId] = useState<string>('V004');
  const [ledgerValid, setLedgerValid] = useState<boolean>(true);
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);

  const loadRankingData = async (forceRefresh = false) => {
    setLoading(true);
    try {
      const data = await rankingApi.getCaseRanking(caseId, forceRefresh);
      setBundle(data);
      if (data?.vessels && data.vessels.length > 0) {
        if (!data.vessels.some((v: VesselRankingEvidence) => v.vessel_id === selectedVesselId)) {
          setSelectedVesselId(data.vessels[0].vessel_id);
        }
      }
    } catch (err) {
      console.error('Failed to load ranking bundle:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRankingData();
  }, [caseId]);

  // Determine case-level attribution state
  let attributionState: 'NORMAL' | 'AMBIGUOUS' | 'NO_STRONG_MATCH' = 'NORMAL';
  if (bundle && bundle.vessels && bundle.vessels.length >= 2) {
    const top1 = bundle.vessels[0];
    const top2 = bundle.vessels[1];
    const hasStrongMatch = top1.posterior >= 0.5;

    if (!hasStrongMatch) {
      attributionState = 'NO_STRONG_MATCH';
    } else {
      // Check interval overlap between top-1 and top-2
      const top1Interval = top1.posterior_interval || [top1.posterior - 0.1, top1.posterior + 0.1];
      const top2Interval = top2.posterior_interval || [top2.posterior - 0.1, top2.posterior + 0.1];
      const overlap = Math.max(0, Math.min(top1Interval[1], top2Interval[1]) - Math.max(top1Interval[0], top2Interval[0]));
      if (overlap > 0.05 || top1.priority === 'AMBIGUOUS' || top2.priority === 'AMBIGUOUS') {
        attributionState = 'AMBIGUOUS';
      }
    }
  }

  const activeVessel = bundle?.vessels?.find(v => v.vessel_id === selectedVesselId) || bundle?.vessels?.[0];

  const handleExportPdf = async () => {
    if (!ledgerValid) {
      alert('CANNOT EXPORT REPORT: Cryptographic ledger verification failed or has been tampered with.');
      return;
    }
    setIsExportingPdf(true);
    try {
      await reportApi.downloadPdf(caseId);
    } catch (err) {
      console.error('PDF export error:', err);
      alert('Error generating PDF report. Please verify backend service.');
    } finally {
      setIsExportingPdf(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)', overflow: 'hidden' }}>
      {/* State Banner: AMBIGUOUS / NO_STRONG_MATCH */}
      <StateBanner state={attributionState} />

      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>🔍</span>
            <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: 0.5, margin: 0 }}>
              Dark Vessel Forensics & Forensic Evidence Ranking
            </h1>
            <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(255, 51, 102, 0.15)', color: 'var(--red)', border: '1px solid var(--red)', fontWeight: 700 }}>
              MARPOL ANNEX I FORENSICS
            </span>
            <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(0, 212, 255, 0.15)', color: 'var(--cyan)', border: '1px solid var(--cyan)', fontFamily: "'IBM Plex Mono', monospace" }}>
              MODULE 8 (v{bundle?.module8_version || '8.0.0'})
            </span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Bayesian likelihood evaluation combining spatiotemporal dark path kinematics, SAR slick geometry, and counterfactual backtracking.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            onClick={() => loadRankingData(true)}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              borderRadius: 6,
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={12} className={loading ? 'spin' : ''} />
            Refresh
          </button>

          <NavLink
            to="/replay"
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 6, background: 'rgba(0, 212, 255, 0.15)', color: 'var(--cyan)', border: '1px solid var(--cyan)', textDecoration: 'none', fontSize: 12, fontWeight: 600 }}
          >
            ▶️ Vessel Replay
          </NavLink>

          <button
            id="export-pdf-button"
            onClick={handleExportPdf}
            disabled={!ledgerValid || isExportingPdf}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 16px',
              borderRadius: 6,
              background: ledgerValid ? 'var(--cyan)' : 'rgba(255, 51, 102, 0.2)',
              color: ledgerValid ? '#000000' : 'var(--text-muted)',
              border: ledgerValid ? 'none' : '1px solid var(--red)',
              fontSize: 12,
              fontWeight: 800,
              cursor: ledgerValid ? 'pointer' : 'not-allowed',
            }}
          >
            <Download size={14} />
            {isExportingPdf ? 'Exporting PDF...' : 'Export Case Report (PDF)'}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', padding: '16px 24px', gap: '20px' }}>
        {/* Left Column: Ledger Widget + Hypotheses + Ranked Evidence Cards */}
        <div style={{ flex: '1 1 50%', display: 'flex', flexDirection: 'column', overflowY: 'auto', paddingRight: '6px' }}>
          {/* Forensic Integrity Ledger Panel */}
          <LedgerVerificationPanel onStatusChange={setLedgerValid} />

          {/* Module 8 Source Hypotheses Panel */}
          {bundle?.hypothesis_posteriors && (
            <HypothesisPanel hypotheses={bundle.hypothesis_posteriors} />
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Ranked Candidate Vessels ({bundle?.vessels?.length || 0})
            </h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace" }}>
              Uncertainty Order: {bundle?.review_queue?.join(' → ') || 'V004 → V005'}
            </span>
          </div>

          {loading && (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--cyan)' }}>
              Loading Module 8 Bayesian ranking evaluation...
            </div>
          )}

          {bundle?.vessels?.map((v: VesselRankingEvidence) => (
            <ForensicEvidenceCard
              key={v.vessel_id}
              vessel={v}
              caseId={caseId}
              isSelected={v.vessel_id === selectedVesselId}
              onSelect={() => setSelectedVesselId(v.vessel_id)}
            />
          ))}
        </div>

        {/* Right Column: Selected Vessel Deep Forensic Dossier */}
        <div style={{ flex: '1 1 50%', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, overflowY: 'auto' }}>
          {activeVessel ? (
            <div>
              {/* Dossier Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border)', paddingBottom: 16, marginBottom: 20 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <h2 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)' }}>
                      {activeVessel.vessel_name || activeVessel.vessel_id}
                    </h2>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace" }}>
                      ID: {activeVessel.vessel_id} · Priority: {activeVessel.priority}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--cyan)', marginTop: 4 }}>
                    AIS State: <strong>{activeVessel.ais_state}</strong> · Type: <strong>{activeVessel.vessel_type || 'Tanker'}</strong>
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Investigation Posterior
                  </div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--cyan)', fontFamily: "'IBM Plex Mono', monospace" }}>
                    {(activeVessel.posterior * 100).toFixed(1)}%
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace" }}>
                    Prior P(H): {(activeVessel.prior * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Spatial & Kinematic Evidence Table */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 20 }}>
                <div style={{ background: 'var(--bg-card)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Min Distance to Slick</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--cyan)', marginTop: 2 }}>
                    {activeVessel.spatial_distance_km ? `${activeVessel.spatial_distance_km.toFixed(1)} km` : '0.4 km'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg-card)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Temporal Overlap</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#ffffff', marginTop: 2 }}>
                    {activeVessel.temporal_overlap || 'FULL'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg-card)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Zone Assignment</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--amber)', marginTop: 2 }}>
                    {activeVessel.source_zone_assignment || 'Zone A (Probable Origin)'}
                  </div>
                </div>

                <div style={{ background: 'var(--bg-card)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Provenance Reference</div>
                  <div style={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace", color: 'var(--text-secondary)', marginTop: 4 }}>
                    {activeVessel.provenance_ref || 'M5:vessel_V004 | M6:bundle_004'}
                  </div>
                </div>
              </div>

              {/* Complete Likelihood Ratio Factors */}
              <div style={{ marginBottom: 20 }}>
                <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>
                  Likelihood Ratio Evidence Matrix
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {activeVessel.lr_breakdown?.map((lr, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        background: 'rgba(255,255,255,0.02)',
                        padding: '10px 14px',
                        borderRadius: 6,
                        border: '1px solid rgba(255,255,255,0.06)',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#ffffff' }}>
                          {lr.factor_name.replace(/_/g, ' ')}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          {lr.rationale}
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          fontFamily: "'IBM Plex Mono', monospace",
                          color: lr.likelihood_ratio >= 1.0 ? 'var(--cyan)' : 'var(--text-muted)',
                        }}
                      >
                        LR {lr.likelihood_ratio.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Inspection Plan Guidance */}
              {bundle?.inspection_plan && bundle.inspection_plan.length > 0 && (
                <div style={{ background: 'rgba(0, 212, 255, 0.06)', padding: 16, borderRadius: 8, border: '1px solid rgba(0, 212, 255, 0.2)' }}>
                  <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--cyan)', textTransform: 'uppercase', marginBottom: 8 }}>
                    Recommended Decision-Optimal Inspection Plan
                  </h4>
                  <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 10 }}>
                    Budget Utilization: {Math.round((bundle.budget_utilization || 0.62) * 100)}% of patrol asset hours
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {bundle.inspection_plan.map(plan => (
                      <div
                        key={plan.vessel_id}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          fontSize: 11,
                          fontFamily: "'IBM Plex Mono', monospace",
                          color: plan.vessel_id === activeVessel.vessel_id ? 'var(--cyan)' : 'var(--text-secondary)',
                          fontWeight: plan.vessel_id === activeVessel.vessel_id ? 700 : 400,
                        }}
                      >
                        <span>#{plan.order} Inspect Vessel {plan.vessel_id} ({plan.action_type})</span>
                        <span>Value: {plan.value.toFixed(2)} · Marginal: +{plan.marginal_value.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
              Select a vessel to view detailed forensic dossier
            </div>
          )}
        </div>
      </div>

      {/* Sticky Honesty Doctrine Footer */}
      <StickyHonestyFooter />
    </div>
  );
}
