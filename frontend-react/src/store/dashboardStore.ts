/**
 * dashboardStore.ts — Zustand global state for the Occuris dashboard.
 * Manages: active view, selected case, replay time, provenance status.
 */
import { create } from 'zustand';
import type { ViewId, CaseId } from '../types/investigation';

interface DashboardState {
  // Navigation
  activeView: ViewId;
  setActiveView: (view: ViewId) => void;

  // Case selection
  selectedCase: CaseId;
  setSelectedCase: (caseId: CaseId) => void;

  // Replay timeline (epoch ms)
  replayTime: number;
  setReplayTime: (t: number) => void;
  isPlaying: boolean;
  setIsPlaying: (v: boolean) => void;
  replaySpeed: 1 | 3 | 8;
  setReplaySpeed: (s: 1 | 3 | 8) => void;

  // Vessel selection (Maritime Memory view)
  selectedVessel: string | 'all';
  setSelectedVessel: (v: string | 'all') => void;

  // Synthetic data flag (from provenance)
  isSynthetic: boolean;
  setIsSynthetic: (v: boolean) => void;

  // Sidebar collapsed state
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  activeView: 'monitoring',
  setActiveView: (view) => set({ activeView: view }),

  selectedCase: 'all',
  setSelectedCase: (caseId) => set({ selectedCase: caseId }),

  // Default replay time: case_01 SAR timestamp
  replayTime: new Date('2024-03-15T06:30:00Z').getTime(),
  setReplayTime: (t) => set({ replayTime: t }),
  isPlaying: false,
  setIsPlaying: (v) => set({ isPlaying: v }),
  replaySpeed: 1,
  setReplaySpeed: (s) => set({ replaySpeed: s }),

  selectedVessel: 'all',
  setSelectedVessel: (v) => set({ selectedVessel: v }),

  // All MVP data is synthetic — default to true
  isSynthetic: true,
  setIsSynthetic: (v) => set({ isSynthetic: v }),

  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
