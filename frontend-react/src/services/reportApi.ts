/**
 * reportApi.ts — PDF report generation via FastAPI + WeasyPrint backend.
 * React never generates its own investigation conclusions.
 * The PDF uses the actual Module 8 InvestigationReportBundle.
 */
const BASE = '';

export async function generateCaseReport(caseId: string): Promise<Blob | null> {
  try {
    const res = await fetch(`${BASE}/api/report/${caseId}`, { method: 'POST' });
    if (!res.ok) return null;
    return res.blob();
  } catch {
    return null;
  }
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
