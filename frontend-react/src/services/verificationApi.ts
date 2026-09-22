/**
 * verificationApi.ts — Wrapper for M6 verification and M8 evidence endpoints.
 */
import type { InvestigationReportBundle, EvidenceGraph } from '../types/investigation';

const BASE = '';

async function safeFetch<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

export async function fetchInvestigationBundle(
  caseId: string
): Promise<InvestigationReportBundle | null> {
  return safeFetch<InvestigationReportBundle>(`${BASE}/api/investigation/${caseId}/bundle`);
}

export async function fetchEvidenceGraph(caseId: string): Promise<EvidenceGraph | null> {
  return safeFetch<EvidenceGraph>(`${BASE}/api/investigation/${caseId}/graph`);
}
