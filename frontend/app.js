/* ═══════════════════════════════════════════════════════════════════════════
   Occuris Dashboard — app.js
   Handles: Leaflet map, layer switcher, case pills, navigation, UTC clock
   ═══════════════════════════════════════════════════════════════════════════ */

// ─── UTC Clock ───────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const h = String(now.getUTCHours()).padStart(2, '0');
  const m = String(now.getUTCMinutes()).padStart(2, '0');
  document.getElementById('clock').textContent = `${h}:${m}`;
}
setInterval(updateClock, 1000);
updateClock();

// ─── Case data (from Module 1 & 2 outputs) ───────────────────────────────────
const CASES = {
  case_01: {
    id: 'case_01',
    title: 'Case 01 — Al-Mahra Corridor',
    lat: 14.958, lon: 53.248,
    area_km2: 3.916,
    iou: 0.8991,
    f1: 0.9469,
    ratio: 0.5803,
    orientation: 64.82,
    major_km: 1.5682,
    minor_km: 1.324,
    timestamp: '2024-03-15T06:30:00Z',
    color: '#ff5252',
    radiusKm: 12,
  },
  case_02: {
    id: 'case_02',
    title: 'Case 02 — Lakshadweep Passage',
    lat: 17.489, lon: 69.034,
    area_km2: 5.206,
    iou: 0.8985,
    f1: 0.9465,
    ratio: 0.4795,
    orientation: 82.28,
    major_km: 1.4747,
    minor_km: 1.1803,
    timestamp: '2024-04-02T09:15:00Z',
    color: '#ff6b35',
    radiusKm: 14,
  },
  case_03: {
    id: 'case_03',
    title: 'Case 03 — Oman Basin',
    lat: 21.183, lon: 61.611,
    area_km2: 4.29,
    iou: 0.8975,
    f1: 0.9460,
    ratio: 0.5699,
    orientation: 54.58,
    major_km: 1.587,
    minor_km: 1.1616,
    timestamp: '2024-04-18T04:45:00Z',
    color: '#ffd740',
    radiusKm: 13,
  },
};

// ─── Gateway definitions ──────────────────────────────────────────────────────
// Single virtual gateway bounding box covering the Arabian Sea (58–75°E, 14–25°N)
const GATEWAYS = [
  {
    name: 'Virtual Gateway — Arabian Sea Monitoring Zone',
    color: '#00e5ff',
    coords: [[14, 58], [14, 75], [25, 75], [25, 58]],  // [lat, lon] corners
  },
];

// ─── Map layers ───────────────────────────────────────────────────────────────
const TILE_LAYERS = {
  sentinel: L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { attribution: '© Esri World Imagery', maxZoom: 18 }
  ),
  dark: L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    { attribution: '© Esri Dark Gray Base', maxZoom: 19 }
  ),
  street: L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    { attribution: '© OpenStreetMap', maxZoom: 19 }
  ),
};

// ─── Init Leaflet map ─────────────────────────────────────────────────────────
const map = L.map('map', {
  center: [18, 62],
  zoom: 5,
  zoomControl: true,
  attributionControl: true,
});

// Start with dark marine layer
let activeLayer = TILE_LAYERS.dark;
activeLayer.addTo(map);

// ─── Draw gateways ────────────────────────────────────────────────────────────
GATEWAYS.forEach(gw => {
  // Swap coords to [lat,lon] already in correct format
  const poly = L.polygon(gw.coords, {
    color: gw.color,
    weight: 2,
    fillColor: gw.color,
    fillOpacity: 0.07,
    dashArray: '6 4',
  }).addTo(map);
  poly.bindTooltip(gw.name, {
    permanent: false,
    direction: 'center',
    className: 'leaflet-tooltip',
  });
});

// ─── Draw spill zones ─────────────────────────────────────────────────────────
const spillLayers = {};

function popupContent(c) {
  return `
    <div class="popup-title">${c.title}</div>
    <div class="popup-row"><span>Area</span><span>${c.area_km2} km²*</span></div>
    <div class="popup-row"><span>IoU</span><span>${c.iou}</span></div>
    <div class="popup-row"><span>Contrast Ratio</span><span>${c.ratio}</span></div>
    <div class="popup-row"><span>Orientation</span><span>${c.orientation}°</span></div>
    <div class="popup-row"><span>Major Axis</span><span>${c.major_km} km</span></div>
    <div class="popup-row"><span>Timestamp</span><span>${c.timestamp.replace('T',' ').replace('Z',' UTC')}</span></div>
    <div class="popup-pass">▲ Look-Alike: PASS — Darker than local background</div>
  `;
}

Object.values(CASES).forEach(c => {
  const group = L.layerGroup();

  // Spill ellipse approximation
  const radiusDeg = c.radiusKm / 111.32;
  const circle = L.ellipse
    ? L.ellipse([c.lat, c.lon], [c.major_km * 0.5, c.minor_km * 0.5], c.orientation, {
        color: c.color,
        weight: 2,
        fillColor: c.color,
        fillOpacity: 0.2,
      })
    : L.circle([c.lat, c.lon], {
        radius: c.radiusKm * 800,
        color: c.color,
        weight: 2,
        fillColor: c.color,
        fillOpacity: 0.2,
      });

  circle.bindPopup(popupContent(c), { maxWidth: 280 });
  circle.addTo(group);

  // Centroid marker (pulsing effect via custom icon)
  const centroidIcon = L.divIcon({
    className: '',
    html: `
      <div style="
        width:14px; height:14px; border-radius:50%;
        background:${c.color};
        border: 2px solid white;
        box-shadow: 0 0 0 4px ${c.color}40;
        animation: pulse 2s infinite;
      "></div>`,
    iconAnchor: [7, 7],
  });

  const marker = L.marker([c.lat, c.lon], { icon: centroidIcon });
  marker.bindPopup(popupContent(c), { maxWidth: 280 });
  marker.addTo(group);

  group.addTo(map);
  spillLayers[c.id] = group;
});

// ─── Layer switcher buttons ───────────────────────────────────────────────────
const mapBtns = {
  sentinel: document.getElementById('btnSentinel'),
  dark:     document.getElementById('btnDark'),
  street:   document.getElementById('btnStreet'),
};

function switchLayer(key) {
  map.removeLayer(activeLayer);
  activeLayer = TILE_LAYERS[key];
  map.addLayer(activeLayer);
  activeLayer.bringToBack();
  Object.entries(mapBtns).forEach(([k, btn]) => {
    btn.classList.toggle('active', k === key);
  });
}

mapBtns.sentinel.addEventListener('click', () => switchLayer('sentinel'));
mapBtns.dark.addEventListener('click',     () => switchLayer('dark'));
mapBtns.street.addEventListener('click',   () => switchLayer('street'));

// ─── Case filter pills ────────────────────────────────────────────────────────
let activeCaseFilter = 'all';

document.getElementById('casePills').addEventListener('click', e => {
  const pill = e.target.closest('.pill');
  if (!pill) return;

  document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
  pill.classList.add('active');
  activeCaseFilter = pill.dataset.case;

  Object.entries(spillLayers).forEach(([id, layer]) => {
    if (activeCaseFilter === 'all' || activeCaseFilter === id) {
      if (!map.hasLayer(layer)) layer.addTo(map);
    } else {
      if (map.hasLayer(layer)) map.removeLayer(layer);
    }
  });

  // Highlight corresponding card
  document.querySelectorAll('.case-card').forEach(card => card.classList.remove('active'));
  if (activeCaseFilter !== 'all') {
    const card = document.getElementById(`card-${activeCaseFilter}`);
    if (card) card.classList.add('active');

    const c = CASES[activeCaseFilter];
    if (c) map.flyTo([c.lat, c.lon], 7, { duration: 0.8 });
  } else {
    document.getElementById('card-case_01').classList.add('active');
    map.flyTo([18, 62], 5, { duration: 0.8 });
  }
});

// ─── Case card clicks ─────────────────────────────────────────────────────────
document.querySelectorAll('.case-card').forEach(card => {
  card.addEventListener('click', () => {
    const id = card.id.replace('card-', '');
    // Simulate clicking the corresponding pill
    const pill = document.querySelector(`.pill[data-case="${id}"]`);
    if (pill) pill.click();
  });
});

// ─── Navigation (sidebar) ─────────────────────────────────────────────────────
const monitoringMain    = document.querySelector('.main');
const spillView         = document.getElementById('spillView');
const spillSplitView    = document.getElementById('spillSplitView');
const maritimeView      = document.getElementById('maritimeView');

window.setView = function(view) {
  // Clear active state on all nav items
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  const navItem = document.querySelector(`.nav-item[data-view="${view}"]`);
  if (navItem) navItem.classList.add('active');

  // Hide all overlays first
  if (spillView) spillView.classList.add('hidden');
  if (spillSplitView) spillSplitView.classList.add('hidden');
  if (maritimeView) maritimeView.classList.add('hidden');

  if (view === 'spill') {
    monitoringMain.classList.add('hidden');
    if (spillView) spillView.classList.remove('hidden');
  } else if (view === 'spillsplit') {
    monitoringMain.classList.add('hidden');
    if (spillSplitView) {
      spillSplitView.classList.remove('hidden');
      renderSpillSplit();
    }
    const icon = document.getElementById('pageTitleIcon');
    const title = document.getElementById('pageTitle');
    const sub = document.getElementById('pageSubtitle');
    if (icon)  icon.textContent  = '✂️';
    if (title) title.textContent = 'SpillSplit — Source Hypothesis Testing';
    if (sub)   sub.textContent   = 'Arabian Sea · One vs Two Source BIC Comparison · Module 4';
  } else if (view === 'maritime') {
    monitoringMain.classList.add('hidden');
    if (maritimeView) {
      maritimeView.classList.remove('hidden');
      if (typeof initMaritimeModule === 'function') initMaritimeModule();
    }
  } else {
    monitoringMain.classList.remove('hidden');
    setTimeout(() => {
      if (typeof map !== 'undefined' && map) map.invalidateSize();
    }, 50);
    // Dispatch so module3 can react
    window.dispatchEvent(new CustomEvent('viewChanged', { detail: { view } }));
  }
};

document.querySelectorAll('.nav-item:not(.disabled)').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    window.setView(item.dataset.view);
  });
});

document.getElementById('backToMonitoring').addEventListener('click', () => {
  window.setView('monitoring');
});

// ─── Spill Investigation (M1-M2) case selector ───
const btnRunInvestigation = document.getElementById('runInvestigationBtn');
const selInvestigationCase = document.getElementById('investigationCaseSelect');
const emptyStateInvestigation = document.getElementById('investigationEmptyState');

if (btnRunInvestigation) {
  btnRunInvestigation.addEventListener('click', () => {
    const selectedCase = selInvestigationCase.value;
    
    // Hide empty state
    if (emptyStateInvestigation) emptyStateInvestigation.classList.add('hidden');
    
    // Hide all spill panels
    document.querySelectorAll('.spill-case-panel').forEach(p => p.classList.add('hidden'));
    
    // Show selected
    const targetPanel = document.getElementById('spillCase' + selectedCase.replace('case_', ''));
    if (targetPanel) {
      targetPanel.classList.remove('hidden');
    }
  });
}

document.getElementById('backToMonitoringFromSplit').addEventListener('click', () => {
  window.setView('monitoring');
});

// ─── SpillSplit Renderer (M4) ─────────────────────────────────────────────────
let spillSplitLoaded = false;

async function renderSpillSplit() {
  if (spillSplitLoaded) return;
  const grid = document.getElementById('spillSplitGrid');
  const cases = ['case_01', 'case_02', 'case_03'];
  const labels = ['Al-Mahra Corridor', 'Lakshadweep Passage', 'Oman Basin'];

  try {
    const results = await Promise.all(
      cases.map(c => fetch(`data/processed/${c}_spillsplit.json`).then(r => r.json()))
    );
    grid.innerHTML = '';

    results.forEach((d, i) => {
      const isOne   = d.result.toLowerCase().includes('one');
      const hypClass = isOne ? 'one' : 'multi';
      const hypLabel = isOne ? 'Single Source' : 'Multiple Sources';

      // BIC bar widths (normalize: lower BIC = better)
      const maxBIC = Math.max(d.one_source.bic, d.two_source.bic);
      const h1w = ((d.one_source.bic / maxBIC) * 100).toFixed(1);
      const h2w = ((d.two_source.bic / maxBIC) * 100).toFixed(1);

      // Source zone coords
      const sz = d.source_zones[0];
      const szLabel = sz
        ? `${sz.latitude.toFixed(4)}°N, ${sz.longitude.toFixed(4)}°E`
        : '--';

      grid.insertAdjacentHTML('beforeend', `
        <div class="spillsplit-panel ${hypClass}">
          <div class="spillsplit-header">
            <div class="spill-case-title">
              <span class="case-badge">CASE ${String(i+1).padStart(2,'0')}</span>
              ${labels[i]}
            </div>
            <span class="spillsplit-hypothesis ${isOne ? 'one' : 'multi'}">${hypLabel}</span>
          </div>

          <div class="spillsplit-stats">
            <div class="ss-stat">
              <div class="ss-stat-label">Stability Score</div>
              <div class="ss-stat-value ${isOne ? 'green' : 'orange'}">${d.stability.score.toFixed(3)}</div>
            </div>
            <div class="ss-stat">
              <div class="ss-stat-label">Separation</div>
              <div class="ss-stat-value yellow">${d.source_separation_km.toFixed(1)} <span style="font-size:11px;font-weight:400;color:var(--text-dim)">km</span></div>
            </div>
            <div class="ss-stat">
              <div class="ss-stat-label">Bootstrap Runs</div>
              <div class="ss-stat-value cyan">${d.stability.n_bootstrap_runs}</div>
            </div>
            <div class="ss-stat">
              <div class="ss-stat-label">Variation ±</div>
              <div class="ss-stat-value">${d.stability.variation_km.toFixed(2)} <span style="font-size:11px;font-weight:400;color:var(--text-dim)">km</span></div>
            </div>
          </div>

          <div class="bic-compare-label">BIC Model Comparison (lower = better fit)</div>
          <div class="bic-compare-row">
            <span class="bic-compare-name">H1</span>
            <div class="bic-bar-bg"><div class="bic-bar h1" style="width:${h1w}%"></div></div>
            <span class="bic-score">${d.one_source.bic.toFixed(1)}</span>
          </div>
          <div class="bic-compare-row">
            <span class="bic-compare-name">H2</span>
            <div class="bic-bar-bg"><div class="bic-bar h2" style="width:${h2w}%"></div></div>
            <span class="bic-score">${d.two_source.bic.toFixed(1)}</span>
          </div>

          <div class="source-zone-info">
            <div class="source-zone-row">
              <span>Primary Origin Zone</span>
              <span>${szLabel}</span>
            </div>
            <div class="source-zone-row">
              <span>H1 IoU</span>
              <span>${d.one_source.iou.toFixed(4)}</span>
            </div>
            <div class="source-zone-row">
              <span>BIC Δ (H1-H2)</span>
              <span style="color:${isOne ? 'var(--done)' : 'var(--orange)'}">
                ${(d.one_source.bic - d.two_source.bic).toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      `);
    });

    spillSplitLoaded = true;
  } catch(err) {
    console.error('SpillSplit load error:', err);
    grid.innerHTML = `<div class="pending-module-empty">
      <div class="pme-icon">⚠️</div>
      <div class="pme-title">Load Error</div>
      <div class="pme-sub">Could not fetch SpillSplit JSON. Run the HTTP server in the frontend/ directory.</div>
    </div>`;
  }
}

document.getElementById('backFromMaritime').addEventListener('click', () => {
  maritimeView.classList.add('hidden');
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelector('[data-view="monitoring"]').classList.add('active');
});

// ─── Start with dark marine layer ────────────────────────────────────────────
mapBtns.dark.click();

// ─── Inject pulse keyframe into document ─────────────────────────────────────
const style = document.createElement('style');
style.textContent = `
  @keyframes glow {
    0%,100% { box-shadow: 0 0 0 2px transparent; }
    50%      { box-shadow: 0 0 8px 2px rgba(0,200,255,0.3); }
  }
`;
document.head.appendChild(style);

/* ═══════════════════════════════════════════════════════════════════════════
   MODULE 5 — MARITIME MEMORY & VIRTUAL GATEWAYS CONTROLLER
   ═══════════════════════════════════════════════════════════════════════════ */

let maritimeMap = null;
let mmActiveLayer = null;
let mmInitialized = false;

// Color palette for vessels
const VESSEL_COLORS = {
  V001: '#00e5ff', // Cyan - Normal Trader
  V002: '#ff5252', // Red - Suspect Tanker (Dark Gap)
  V003: '#ffd740', // Amber - Anomalous Cargo
  V004: '#00e676', // Green - Coastal Feeder
  V005: '#b388ff', // Purple - Transit Bulker
};

// Maritime State
const mmState = {
  gateways: [],
  vessels: [],
  tracks: {},
  crossings: [],
  journeys: {},
  behaviour: {},
  traffic: null,
  sourceInfo: null,
  selectedVessel: 'all',
  
  // Replay State
  isPlaying: false,
  replaySpeed: 1, // 1x, 3x, 8x
  replayInterval: null,
  startTime: new Date('2024-03-15T00:00:00Z').getTime(),
  endTime: new Date('2024-03-15T12:00:00Z').getTime(),
  currentTime: new Date('2024-03-15T12:00:00Z').getTime(),
  
  // Layer groups
  layers: {
    gateways: null,
    tracks: null,
    vessels: null,
    crossings: null,
    gaps: null,
  },
};

function initMaritimeModule() {
  if (!mmInitialized) {
    initMaritimeMap();
    fetchMaritimeData();
    setupMaritimeControls();
    mmInitialized = true;
  } else {
    setTimeout(() => {
      if (maritimeMap) maritimeMap.invalidateSize();
    }, 150);
  }
}

function initMaritimeMap() {
  const mapEl = document.getElementById('maritimeMap');
  if (!mapEl) return;

  maritimeMap = L.map('maritimeMap', {
    center: [18.2, 65.5],
    zoom: 6,
    zoomControl: true,
  });

  const mmTileLayers = {
    dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© CartoDB', maxZoom: 19
    }),
    sentinel: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: '© Esri World Imagery', maxZoom: 18
    }),
    street: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap', maxZoom: 19
    }),
  };

  mmActiveLayer = mmTileLayers.dark;
  mmActiveLayer.addTo(maritimeMap);

  // Layer groups
  mmState.layers.gateways = L.layerGroup().addTo(maritimeMap);
  mmState.layers.tracks = L.layerGroup().addTo(maritimeMap);
  mmState.layers.gaps = L.layerGroup().addTo(maritimeMap);
  mmState.layers.crossings = L.layerGroup().addTo(maritimeMap);
  mmState.layers.vessels = L.layerGroup().addTo(maritimeMap);

  // Layer Switchers
  const mmBtns = {
    sentinel: document.getElementById('btnMmSentinel'),
    dark: document.getElementById('btnMmDark'),
    street: document.getElementById('btnMmStreet'),
  };

  function switchMmLayer(key) {
    maritimeMap.removeLayer(mmActiveLayer);
    mmActiveLayer = mmTileLayers[key];
    maritimeMap.addLayer(mmActiveLayer);
    mmActiveLayer.bringToBack();
    Object.entries(mmBtns).forEach(([k, btn]) => {
      if (btn) btn.classList.toggle('active', k === key);
    });
  }

  if (mmBtns.sentinel) mmBtns.sentinel.addEventListener('click', () => switchMmLayer('sentinel'));
  if (mmBtns.dark) mmBtns.dark.addEventListener('click', () => switchMmLayer('dark'));
  if (mmBtns.street) mmBtns.street.addEventListener('click', () => switchMmLayer('street'));

  const fitBtn = document.getElementById('btnFitCorridors');
  if (fitBtn) {
    fitBtn.addEventListener('click', () => {
      maritimeMap.flyTo([18.2, 65.5], 6, { duration: 0.8 });
    });
  }

  setTimeout(() => maritimeMap.invalidateSize(), 200);
}

// ─── API Data Fetching ───────────────────────────────────────────────────────
async function fetchMaritimeData() {
  try {
    const [gwRes, vRes, evRes, bRes, sRes] = await Promise.all([
      fetch('/api/gateways').catch(() => null),
      fetch('/api/maritime/vessels').catch(() => null),
      fetch('/api/maritime/gateway-events').catch(() => null),
      fetch('/api/maritime/behaviour').catch(() => null),
      fetch('/api/maritime/source-info').catch(() => null),
    ]);

    if (gwRes && gwRes.ok) {
      const gwData = await gwRes.json();
      mmState.gateways = gwData.features || [];
    }
    if (vRes && vRes.ok) {
      mmState.vessels = await vRes.json();
    }
    if (evRes && evRes.ok) {
      mmState.crossings = await evRes.json();
    }
    if (bRes && bRes.ok) {
      mmState.behaviour = await bRes.json();
    }
    if (sRes && sRes.ok) {
      mmState.sourceInfo = await sRes.json();
      updateSourceBadge(mmState.sourceInfo);
    }

    // Fetch individual vessel tracks
    await Promise.all(
      mmState.vessels.map(async (v) => {
        const tRes = await fetch(`/api/maritime/vessels/${v.vessel_id}/track`).catch(() => null);
        if (tRes && tRes.ok) {
          const trackData = await tRes.json();
          mmState.tracks[v.vessel_id] = trackData;
        }
        const jRes = await fetch(`/api/maritime/vessels/${v.vessel_id}/journey`).catch(() => null);
        if (jRes && jRes.ok) {
          const jData = await jRes.json();
          mmState.journeys[v.vessel_id] = jData;
        }
      })
    );

    renderAllMaritimeElements();
    // Select V001 by default
    selectVessel('V001');

  } catch (err) {
    console.warn('Backend API connection note:', err);
  }
}

function updateSourceBadge(info) {
  const badgeText = document.getElementById('sourceBadgeText');
  if (badgeText && info) {
    badgeText.textContent = `${info.mode.replace('_', ' ')} · ${info.label} (${info.record_count} pings)`;
  }
}

// ─── Rendering on Map ────────────────────────────────────────────────────────
function renderAllMaritimeElements() {
  renderGateways();
  renderTracksAndGaps();
  renderCrossings();
  renderReplayPings(mmState.currentTime);
  renderCrossingFeed();
  renderCorridorStatus();
}

function renderGateways() {
  if (!mmState.layers.gateways) return;
  mmState.layers.gateways.clearLayers();

  mmState.gateways.forEach(feat => {
    const coords = feat.geometry.coordinates; // [[lon, lat], ...]
    const latlngs = coords.map(c => [c[1], c[0]]);
    const props = feat.properties;

    // Outer glow line
    L.polyline(latlngs, {
      color: props.color || '#00f0ff',
      weight: 8,
      opacity: 0.25,
    }).addTo(mmState.layers.gateways);

    // Sharp core line
    const coreLine = L.polyline(latlngs, {
      color: props.color || '#00f0ff',
      weight: 3,
      opacity: 0.95,
      dashArray: '8 6',
    }).addTo(mmState.layers.gateways);

    // Corridor label
    coreLine.bindTooltip(
      `<strong>${props.gateway_id}</strong><br><span style="font-size:10px; opacity:0.8">${props.name}</span>`,
      { permanent: true, direction: 'top', className: 'leaflet-tooltip' }
    );
  });
}

function renderTracksAndGaps() {
  if (!mmState.layers.tracks) return;
  mmState.layers.tracks.clearLayers();
  mmState.layers.gaps.clearLayers();

  Object.entries(mmState.tracks).forEach(([vId, track]) => {
    if (mmState.selectedVessel !== 'all' && mmState.selectedVessel !== vId) return;

    const color = VESSEL_COLORS[vId] || '#00c8ff';
    const latlngs = track.pings.map(p => [p.lat, p.lon]);

    // Track polyline
    const poly = L.polyline(latlngs, {
      color: color,
      weight: mmState.selectedVessel === vId ? 3.5 : 2.0,
      opacity: mmState.selectedVessel === vId ? 0.9 : 0.45,
    }).addTo(mmState.layers.tracks);

    poly.on('click', () => selectVessel(vId));

    // Render AIS gaps as dashed warnings
    if (track.gaps && track.gaps.length > 0) {
      track.gaps.forEach(g => {
        const gapLine = L.polyline([[g.start_lat, g.start_lon], [g.end_lat, g.end_lon]], {
          color: '#ff5252',
          weight: 4,
          dashArray: '4 6',
          opacity: 0.95,
        }).addTo(mmState.layers.gaps);

        gapLine.bindPopup(`
          <div class="popup-title" style="color:#ff5252">⚠ AIS REPORTING BLACKOUT</div>
          <div class="popup-row"><span>Vessel</span><span>${vId} (${track.vessel_name})</span></div>
          <div class="popup-row"><span>Gap Duration</span><span>${g.duration_minutes} min</span></div>
          <div class="popup-row"><span>Threshold</span><span>30 min (Exceeded)</span></div>
          <div class="popup-pass" style="background:rgba(255,82,82,0.15); color:#ff5252">
            Classification: DARK VESSEL SUSPICION
          </div>
        `);
      });
    }
  });
}

function renderCrossings() {
  if (!mmState.layers.crossings) return;
  mmState.layers.crossings.clearLayers();

  mmState.crossings.forEach(ev => {
    if (mmState.selectedVessel !== 'all' && mmState.selectedVessel !== ev.vessel_id) return;

    const isEntry = ev.event_type === 'ENTRY';
    const iconColor = isEntry ? '#00e676' : '#ff6b35';

    const crossIcon = L.divIcon({
      className: '',
      html: `
        <div style="
          width: 12px; height: 12px; border-radius: 50%;
          background: ${iconColor};
          border: 2px solid white;
          box-shadow: 0 0 8px ${iconColor};
          cursor: pointer;
        "></div>
      `,
      iconAnchor: [6, 6],
    });

    const marker = L.marker([ev.lat, ev.lon], { icon: crossIcon }).addTo(mmState.layers.crossings);
    marker.bindPopup(`
      <div class="popup-title">GATEWAY ${ev.event_type} EVENT</div>
      <div class="popup-row"><span>Gateway</span><span>${ev.gateway_id}</span></div>
      <div class="popup-row"><span>Vessel</span><span>${ev.vessel_id} (${ev.vessel_name})</span></div>
      <div class="popup-row"><span>Time</span><span>${ev.timestamp.replace('T', ' ').slice(0, 19)} UTC</span></div>
      <div class="popup-row"><span>Speed</span><span>${ev.speed} kn</span></div>
      <div class="popup-row"><span>Course</span><span>${ev.course}°</span></div>
    `);
  });
}

function renderReplayPings(targetTimestamp) {
  if (!mmState.layers.vessels) return;
  mmState.layers.vessels.clearLayers();

  const targetDate = new Date(targetTimestamp);

  Object.entries(mmState.tracks).forEach(([vId, track]) => {
    if (mmState.selectedVessel !== 'all' && mmState.selectedVessel !== vId) return;

    const visiblePings = track.pings.filter(p => new Date(p.timestamp).getTime() <= targetDate.getTime());
    if (!visiblePings || visiblePings.length === 0) return;

    const currentPing = visiblePings[visiblePings.length - 1];
    const color = VESSEL_COLORS[vId] || '#00c8ff';
    const rot = currentPing.cog || 0;

    // SVG Ship icon with COG rotation
    const shipSvg = `
      <div class="ship-marker-wrap" style="transform: rotate(${rot}deg);" title="${vId} (${track.vessel_name})">
        <div class="ship-pulse" style="border-color:${color};"></div>
        <svg class="ship-marker-svg" viewBox="0 0 24 24" fill="${color}">
          <path d="M12 2L4 20L12 16L20 20L12 2Z" stroke="#ffffff" stroke-width="1.5" />
        </svg>
      </div>
    `;

    const icon = L.divIcon({
      className: '',
      html: shipSvg,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });

    const m = L.marker([currentPing.lat, currentPing.lon], { icon: icon }).addTo(mmState.layers.vessels);
    m.on('click', () => selectVessel(vId));
    m.bindTooltip(`<strong>${vId}</strong> · ${currentPing.sog} kn`, { direction: 'top', offset: [0, -10] });
  });
}

// ─── Vessel Selection & Inspector ────────────────────────────────────────────
function selectVessel(vesselId) {
  mmState.selectedVessel = vesselId;

  // Update pills
  document.querySelectorAll('.v-pill').forEach(p => {
    p.classList.toggle('active', p.dataset.vessel === vesselId);
  });

  // Re-render map layers with focus
  renderTracksAndGaps();
  renderCrossings();
  renderReplayPings(mmState.currentTime);

  // If a specific vessel is chosen, zoom to its track
  if (vesselId !== 'all' && mmState.tracks[vesselId]) {
    const pings = mmState.tracks[vesselId].pings;
    if (pings.length > 0) {
      const bounds = L.latLngBounds(pings.map(p => [p.lat, p.lon]));
      maritimeMap.flyToBounds(bounds, { padding: [40, 40], duration: 0.6 });
    }
  }

  // Populate Inspector Card
  const targetId = vesselId === 'all' ? 'V001' : vesselId;
  const v = mmState.vessels.find(item => item.vessel_id === targetId);
  const track = mmState.tracks[targetId];
  const jData = mmState.journeys[targetId];
  const bData = mmState.behaviour[targetId];

  if (!v || !track) return;

  document.getElementById('vesselBadge').textContent = targetId;
  document.getElementById('vesselName').textContent = v.vessel_name || track.vessel_name;
  document.getElementById('vesselMmsi').textContent = v.mmsi;
  document.getElementById('vesselSog').textContent = `${v.sog} kn`;
  document.getElementById('vesselCog').textContent = `${v.cog}°`;
  document.getElementById('vesselNav').textContent = v.nav_status_label;

  const statusBadge = document.getElementById('vesselStatusBadge');
  const bStatus = bData ? bData.status : v.status;

  if (statusBadge) {
    statusBadge.className = 'status-pill';
    if (bStatus === 'NORMAL_TRANSIT') {
      statusBadge.classList.add('status-normal');
      statusBadge.textContent = 'NORMAL TRANSIT';
    } else if (bStatus === 'POTENTIAL_UNEXPLAINED_DELAY') {
      statusBadge.classList.add('status-alert');
      statusBadge.textContent = 'POTENTIAL UNEXPLAINED DELAY';
    } else if (bStatus === 'EXPLAINED_DELAY') {
      statusBadge.classList.add('status-warning');
      statusBadge.textContent = 'EXPLAINED DELAY';
    } else {
      statusBadge.classList.add('status-normal');
      statusBadge.textContent = bStatus;
    }
  }

  if (jData && jData.journey) {
    const j = jData.journey;
    const t = jData.transit || {};
    document.getElementById('vesselDistance').textContent = `${j.distance_km} km`;
    document.getElementById('vesselDuration').textContent = `${j.actual_duration_h} h`;
    document.getElementById('vesselExpected').textContent = t.expected_duration_h ? `${t.expected_duration_h} h` : 'Baseline';
    
    const delayH = t.delay_h || 0;
    const delayStr = delayH > 0 ? `+${delayH} h (Delayed)` : `${delayH} h (On-time)`;
    document.getElementById('vesselDelay').textContent = delayStr;
  }

  // Populate Evidence Checklist
  const evidenceList = document.getElementById('evidenceList');
  if (evidenceList) {
    evidenceList.innerHTML = '';

    const hasGap = track.gaps && track.gaps.length > 0;
    const gapRow = document.createElement('div');
    gapRow.className = `evidence-row ${hasGap ? 'alert' : 'pass'}`;
    gapRow.innerHTML = `
      <span>${hasGap ? '⚠ AIS Blackout Detected' : '✓ AIS Continuity'}</span>
      <span class="tag">${hasGap ? `${track.gaps[0].duration_minutes} MIN GAP` : 'CONTINUOUS'}</span>
    `;
    evidenceList.appendChild(gapRow);

    const delayRow = document.createElement('div');
    const delayH = (jData && jData.transit && jData.transit.delay_h) || 0;
    const isDelayed = delayH > 1.0;
    delayRow.className = `evidence-row ${isDelayed ? 'alert' : 'pass'}`;
    delayRow.innerHTML = `
      <span>${isDelayed ? '▲ Passage Duration Delay' : '✓ Transit Duration'}</span>
      <span class="tag">${isDelayed ? `+${delayH}h DEV` : 'ON SCHEDULE'}</span>
    `;
    evidenceList.appendChild(delayRow);

    const trafficRow = document.createElement('div');
    trafficRow.className = 'evidence-row info';
    trafficRow.innerHTML = `
      <span>ℹ Regional Traffic Density</span>
      <span class="tag">NORMAL (2 SHIPS)</span>
    `;
    evidenceList.appendChild(trafficRow);

    const envRow = document.createElement('div');
    envRow.className = 'evidence-row info';
    envRow.innerHTML = `
      <span>ℹ Environmental Weather Grid</span>
      <span class="tag">DECOUPLED</span>
    `;
    evidenceList.appendChild(envRow);
  }
}

// ─── Feed & Corridors List ───────────────────────────────────────────────────
function renderCrossingFeed() {
  const feedEl = document.getElementById('crossingFeedList');
  if (!feedEl) return;
  feedEl.innerHTML = '';

  const countEl = document.getElementById('feedCount');
  if (countEl) countEl.textContent = `${mmState.crossings.length} Events`;

  mmState.crossings.forEach(ev => {
    const row = document.createElement('div');
    row.className = 'feed-row';
    const isEntry = ev.event_type === 'ENTRY';
    const tagClass = isEntry ? 'entry' : 'exit';

    row.innerHTML = `
      <div class="feed-left">
        <span class="feed-event-tag ${tagClass}">${ev.event_type}</span>
        <div>
          <strong style="color:#fff">${ev.vessel_id}</strong>
          <span style="color:var(--text-dim); font-size:10px;">· ${ev.gateway_id}</span>
        </div>
      </div>
      <div class="feed-right">
        <span class="feed-speed">${ev.speed} kn · ${ev.course}°</span>
        <span class="feed-time">${ev.timestamp.replace('T', ' ').slice(11, 16)} UTC</span>
      </div>
    `;
    row.addEventListener('click', () => selectVessel(ev.vessel_id));
    feedEl.appendChild(row);
  });
}

function renderCorridorStatus() {
  const listEl = document.getElementById('corridorStatusList');
  if (!listEl) return;
  listEl.innerHTML = '';

  mmState.gateways.forEach(gw => {
    const gwId = gw.properties.gateway_id;
    const name = gw.properties.name;
    const color = gw.properties.color || '#00f0ff';
    const crossings = mmState.crossings.filter(c => c.gateway_id === gwId);

    const row = document.createElement('div');
    row.className = 'corridor-row';
    row.style.borderLeftColor = color;
    row.innerHTML = `
      <span class="corridor-name">${gwId} — ${name}</span>
      <span class="corridor-count">${crossings.length} crossings</span>
    `;
    listEl.appendChild(row);
  });
}

// ─── Replay Controls ─────────────────────────────────────────────────────────
function setupMaritimeControls() {
  // Vessel pills
  document.getElementById('vesselPills').addEventListener('click', e => {
    const pill = e.target.closest('.v-pill');
    if (!pill) return;
    selectVessel(pill.dataset.vessel);
  });

  // Replay Slider
  const slider = document.getElementById('replaySlider');
  const timeDisplay = document.getElementById('replayTimeDisplay');

  function updateSliderTime(pct) {
    const totalMs = mmState.endTime - mmState.startTime;
    mmState.currentTime = mmState.startTime + (totalMs * pct / 100);
    const dt = new Date(mmState.currentTime);
    if (timeDisplay) {
      timeDisplay.textContent = dt.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    }
    renderReplayPings(mmState.currentTime);
  }

  if (slider) {
    slider.addEventListener('input', e => {
      updateSliderTime(Number(e.target.value));
    });
  }

  // Play / Pause
  const playBtn = document.getElementById('btnReplayPlay');
  const resetBtn = document.getElementById('btnReplayReset');

  function togglePlay() {
    mmState.isPlaying = !mmState.isPlaying;
    if (playBtn) playBtn.textContent = mmState.isPlaying ? '❚❚ Pause' : '▶ Play';

    if (mmState.isPlaying) {
      // If at end, loop to start
      if (Number(slider.value) >= 100) slider.value = 0;

      mmState.replayInterval = setInterval(() => {
        let val = Number(slider.value) + (0.5 * mmState.replaySpeed);
        if (val >= 100) {
          val = 100;
          togglePlay();
        }
        slider.value = val;
        updateSliderTime(val);
      }, 100);
    } else {
      clearInterval(mmState.replayInterval);
      mmState.replayInterval = null;
    }
  }

  if (playBtn) playBtn.addEventListener('click', togglePlay);

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (mmState.isPlaying) togglePlay();
      slider.value = 0;
      updateSliderTime(0);
    });
  }

  // Speed buttons
  document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      mmState.replaySpeed = Number(btn.dataset.speed || 1);
    });
  });
}

