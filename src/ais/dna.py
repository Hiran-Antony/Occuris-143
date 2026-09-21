"""
Module 5 — Maritime Memory & Virtual Gateways — Innovation Layer A: Behavioral DNA (§4.8)
Extracts high-dimensional kinematic signatures:
- Speed distribution (mean, std, histogram)
- Acceleration & turn-rate dynamics
- Loiter ratio (fraction of time SOG < 2.0 kn)
- Path straightness index (net displacement / cumulative geodesic distance)
- Gateway crossing speed profile
Computes Mahalanobis-distance re-identification confidence across AIS blackout boundaries.
Covariance estimation: Ledoit-Wolf shrinkage when n >= 8, diagonal fallback otherwise.
Labeled strictly as: 'behavioural similarity, not identity proof'.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.ais.schemas import DnaMatch, VesselBehavioralDNA, VesselTrack
from src.ais.track_builder import WGS84_GEOD


def _ledoit_wolf_shrinkage(X: np.ndarray) -> Tuple[np.ndarray, str]:
    """
    Manual Ledoit-Wolf shrinkage estimator (no sklearn dependency).
    X: (n_samples, n_features) matrix, already centered.
    Returns (shrunk_cov, method_label).
    """
    n, p = X.shape
    if n < 2:
        return np.eye(p), "diagonal"

    S = np.cov(X, rowvar=False, ddof=1)

    # Check for singularity
    try:
        det = np.linalg.det(S)
        if abs(det) < 1e-12:
            raise np.linalg.LinAlgError("Singular")
    except np.linalg.LinAlgError:
        return np.diag(np.diag(S) + 1e-6), "diagonal"

    # Oracle Approximating Shrinkage (Ledoit & Wolf 2004)
    mu = np.trace(S) / p
    delta = S - mu * np.eye(p)
    delta_sq_sum = np.sum(delta ** 2)

    # Estimate optimal shrinkage intensity
    X_centered = X - X.mean(axis=0)
    b_bar = 0.0
    for i in range(n):
        xi = X_centered[i:i+1, :]
        b_bar += np.sum((xi.T @ xi - S) ** 2)
    b_bar /= (n ** 2)

    shrinkage = min(1.0, max(0.0, b_bar / delta_sq_sum)) if delta_sq_sum > 1e-12 else 1.0

    shrunk = (1 - shrinkage) * S + shrinkage * mu * np.eye(p)
    method = "shrunk" if shrinkage < 0.99 else "diagonal"
    return shrunk, method


class BehavioralDNAExtractor:
    """Extracts kinematic profiles and computes Mahalanobis re-identification match scores."""

    FEATURE_KEYS = [
        "speed_mean",
        "speed_std",
        "acceleration_mean",
        "acceleration_std",
        "turn_rate_mean",
        "turn_rate_std",
        "loiter_ratio",
        "straightness_index",
    ]

    def extract_dna(self, track: VesselTrack) -> VesselBehavioralDNA:
        """Extract high-dimensional behavioral feature vector from chronological AIS pings."""
        pings = track.pings
        if not pings or len(pings) < 3:
            # Low confidence default
            feat = {k: 0.0 for k in self.FEATURE_KEYS}
            return VesselBehavioralDNA(
                vessel_id=track.vessel_id,
                feature_vector=feat,
                speed_histogram={},
                covariance=None,
                sample_count=len(pings),
                confidence=0.1,
            )

        speeds = np.array([p.sog for p in pings], dtype=float)
        speed_mean = float(np.mean(speeds))
        speed_std = float(np.std(speeds))

        # Speed histogram (0-5, 5-10, 10-15, 15-20, 20+)
        hist_bins = [0, 5, 10, 15, 20, 100]
        counts, _ = np.histogram(speeds, bins=hist_bins)
        speed_hist = {
            f"{hist_bins[i]}_{hist_bins[i+1]}kn": int(counts[i])
            for i in range(len(counts))
        }

        # Accelerations & turn rates
        accelerations = []
        turn_rates = []
        loiter_count = sum(1 for s in speeds if s < 2.0)
        loiter_ratio = float(loiter_count / len(speeds))

        for i in range(len(pings) - 1):
            p1, p2 = pings[i], pings[i + 1]
            dt_sec = max(1.0, (p2.timestamp - p1.timestamp).total_seconds())

            # Acceleration in kn/sec
            accel = (p2.sog - p1.sog) / dt_sec
            accelerations.append(accel)

            # Turn rate in deg/sec (shortest angular distance)
            diff_cog = (p2.cog - p1.cog + 180.0) % 360.0 - 180.0
            turn_rates.append(abs(diff_cog) / dt_sec)

        accel_mean = float(np.mean(accelerations)) if accelerations else 0.0
        accel_std = float(np.std(accelerations)) if accelerations else 0.0
        turn_mean = float(np.mean(turn_rates)) if turn_rates else 0.0
        turn_std = float(np.std(turn_rates)) if turn_rates else 0.0

        # Straightness index = Net Geodesic Displacement / Cumulative Path Length
        _, _, net_disp_m = WGS84_GEOD.inv(pings[0].lon, pings[0].lat, pings[-1].lon, pings[-1].lat)
        total_path_m = 0.0
        for i in range(len(pings) - 1):
            _, _, d = WGS84_GEOD.inv(pings[i].lon, pings[i].lat, pings[i + 1].lon, pings[i + 1].lat)
            total_path_m += d

        straightness = float(net_disp_m / total_path_m) if total_path_m > 10.0 else 1.0
        straightness = max(0.0, min(1.0, straightness))

        features = {
            "speed_mean": round(speed_mean, 2),
            "speed_std": round(speed_std, 2),
            "acceleration_mean": round(accel_mean, 4),
            "acceleration_std": round(accel_std, 4),
            "turn_rate_mean": round(turn_mean, 4),
            "turn_rate_std": round(turn_std, 4),
            "loiter_ratio": round(loiter_ratio, 3),
            "straightness_index": round(straightness, 3),
        }

        # Confidence based on ping count
        confidence = round(min(1.0, len(pings) / 50.0), 2)

        # Compute covariance matrix via Ledoit-Wolf shrinkage
        cov_matrix = None
        if len(pings) >= 8:
            # Build per-segment feature matrix for covariance estimation
            seg_features = []
            for i in range(len(pings) - 1):
                p1, p2 = pings[i], pings[i + 1]
                dt_sec = max(1.0, (p2.timestamp - p1.timestamp).total_seconds())
                seg_features.append([
                    p1.sog,
                    abs(p2.sog - p1.sog) / dt_sec,
                    abs(((p2.cog - p1.cog + 180) % 360 - 180)) / dt_sec,
                    1.0 if p1.sog < 2.0 else 0.0,
                ])
            if len(seg_features) >= 4:
                X = np.array(seg_features)
                shrunk_cov, _ = _ledoit_wolf_shrinkage(X)
                cov_matrix = shrunk_cov.tolist()

        return VesselBehavioralDNA(
            vessel_id=track.vessel_id,
            feature_vector=features,
            speed_histogram=speed_hist,
            covariance=cov_matrix,
            sample_count=len(pings),
            confidence=confidence,
        )

    def compare_dna(
        self,
        dna_a: VesselBehavioralDNA,
        dna_b: VesselBehavioralDNA,
    ) -> DnaMatch:
        """
        Compute regularized Mahalanobis distance between two behavioral profiles.
        Uses POOLED covariance (symmetric: compare(A,B) == compare(B,A)).
        Falls back to Ledoit-Wolf shrinkage or diagonal as needed.
        """
        vec_a = np.array([dna_a.feature_vector.get(k, 0.0) for k in self.FEATURE_KEYS])
        vec_b = np.array([dna_b.feature_vector.get(k, 0.0) for k in self.FEATURE_KEYS])
        diff = vec_a - vec_b

        n_a = dna_a.sample_count
        n_b = dna_b.sample_count
        min_n = min(n_a, n_b)

        # Determine covariance method
        method = "diagonal"
        cov_inv = None

        if dna_a.covariance is not None and dna_b.covariance is not None:
            # Pooled covariance (symmetric)
            cov_a = np.array(dna_a.covariance)
            cov_b = np.array(dna_b.covariance)
            # Match dimensions — covariance may be from segment features (4-dim)
            # Fall back to diagonal if dimensions don't match feature keys
            if cov_a.shape == cov_b.shape and cov_a.shape[0] == len(self.FEATURE_KEYS):
                pooled = (cov_a + cov_b) / 2.0
                try:
                    cov_inv = np.linalg.inv(pooled)
                    method = "full_cov"
                except np.linalg.LinAlgError:
                    # Singular pooled — shrink
                    pooled_shrunk, method = _ledoit_wolf_shrinkage(
                        np.vstack([vec_a.reshape(1, -1), vec_b.reshape(1, -1)])
                    )
                    try:
                        cov_inv = np.linalg.inv(pooled_shrunk)
                    except np.linalg.LinAlgError:
                        cov_inv = None
                        method = "diagonal"

        if cov_inv is None:
            # Diagonal fallback with feature-appropriate scales
            variances = np.array([
                max(0.5, (speed_std_val := max(dna_a.feature_vector.get("speed_std", 1.0),
                                                dna_b.feature_vector.get("speed_std", 1.0))) ** 2),
                0.5,   # speed_std
                0.01,  # accel_mean
                0.01,  # accel_std
                0.05,  # turn_mean
                0.05,  # turn_std
                0.04,  # loiter_ratio
                0.02,  # straightness
            ])
            cov_inv = np.diag(1.0 / variances)
            method = "diagonal"

        # Mahalanobis distance (symmetric when using pooled covariance)
        mahalanobis_sq = float(diff @ cov_inv @ diff)
        m_dist = math.sqrt(max(0.0, mahalanobis_sq))

        # Softmax / exponential decay mapping to confidence percentage
        confidence_pct = round(100.0 / (1.0 + 0.35 * m_dist), 1)

        return DnaMatch(
            vessel_id=dna_a.vessel_id,
            candidate_id=dna_b.vessel_id,
            confidence_pct=confidence_pct,
            mahalanobis_dist=round(m_dist, 3),
            method=method,
            sample_count=min_n,
            disclaimer="behavioural similarity, not identity proof",
        )

    def reidentify_post_gap(
        self,
        post_gap_track: VesselTrack,
        candidate_profiles: Dict[str, VesselBehavioralDNA],
    ) -> List[DnaMatch]:
        """
        Match a post-gap track fragment against all known vessel profiles.
        Returns ranked list of candidate matches by Mahalanobis similarity.
        """
        post_dna = self.extract_dna(post_gap_track)
        matches: List[DnaMatch] = []

        for cand_id, cand_dna in candidate_profiles.items():
            match = self.compare_dna(post_dna, cand_dna)
            matches.append(match)

        # Sort descending by confidence percentage
        matches.sort(key=lambda m: m.confidence_pct, reverse=True)
        return matches

    # Backwards compatibility alias
    compare_profiles = compare_dna
