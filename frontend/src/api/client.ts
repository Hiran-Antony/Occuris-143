import axios from 'axios';
import type {
  Vessel, VesselTrack, TimelineEvent, BehaviourEvent,
  Journey, GatewayCrossing
} from '../types';

const api = axios.create({ baseURL: 'http://localhost:8080' });

export const regionApi = {
  getRegion: () => api.get('/api/region').then(r => r.data),
  getGateways: () => api.get('/api/region/gateways').then(r => r.data),
};

export const dashboardApi = {
  stats: (): Promise<any> => api.get('/api/dashboard/summary').then(r => r.data),
  gatewayCrossings: (limit = 50): Promise<any[]> => api.get(`/api/dashboard/gateway-crossings?limit=${limit}`).then(r => r.data),
};

export const caseApi = {
  list: () => api.get('/api/cases').then(r => r.data),
  get: (caseId: string) => api.get(`/api/cases/${caseId}`).then(r => r.data),
  getMap: (caseId: string) => api.get(`/api/cases/${caseId}/map`).then(r => r.data),
  getSpill: (caseId: string) => api.get(`/api/cases/${caseId}/spill`).then(r => r.data),
  getOriginZone: (caseId: string) => api.get(`/api/cases/${caseId}/origin-zone`).then(r => r.data),
  getDrift: (caseId: string) => api.get(`/api/cases/${caseId}/drift`).then(r => r.data),
  getVessels: (caseId: string) => api.get(`/api/cases/${caseId}/vessels`).then(r => r.data),
  getVesselTrack: (caseId: string, vesselId: string) => api.get(`/api/cases/${caseId}/vessels/${vesselId}/track`).then(r => r.data),
  getGatewayEvents: (caseId: string) => api.get(`/api/cases/${caseId}/gateway-events`).then(r => r.data),
  getInvestigation: (caseId: string) => api.get(`/api/cases/${caseId}/investigation`).then(r => r.data),
  getCandidates: (caseId: string) => api.get(`/api/cases/${caseId}/candidates`).then(r => r.data),
  getEvidenceGraph: (caseId: string) => api.get(`/api/cases/${caseId}/evidence-graph`).then(r => r.data),
  generateReport: (caseId: string) => api.post(`/api/cases/${caseId}/report`).then(r => r.data),
};

// Legacy stubs (if parts of the UI still use these directly before refactoring)
export const vesselApi = {
  list: (): Promise<Vessel[]> => api.get('/api/cases/case_01/vessels').then(r => r.data).catch(() => []),
  get: (_mmsi: string): Promise<Vessel> => api.get(`/api/cases/case_01/vessels`).then(r => r.data[0]).catch(() => null),
  getTrack: (mmsi: string): Promise<VesselTrack> => api.get(`/api/cases/case_01/vessels/${mmsi}/track`).then(r => r.data).catch(() => null),
  getTimeline: (_mmsi: string): Promise<TimelineEvent[]> => Promise.resolve([]),
  getEvents: (_mmsi: string): Promise<BehaviourEvent[]> => Promise.resolve([]),
  recentCrossings: (_limit = 30): Promise<GatewayCrossing[]> => Promise.resolve([]),
};

export const forensicsApi = {
  getIncidents: async () => api.get('/api/cases').then(r => r.data).catch(() => []),
  getSuspects: async (incidentId: string) => api.get(`/api/cases/${incidentId}/candidates`).then(r => r.data).catch(() => []),
  getSarImages: async (): Promise<any> => ({ images: ['sar_01.png', 'sar_02.png', 'sar_03.png'] }),
  processSarImage: async (_filename: string): Promise<any> => ({ status: 'success', incident: null }),
};

export const journeyApi = {
  list: (): Promise<Journey[]> => Promise.resolve([]),
};
