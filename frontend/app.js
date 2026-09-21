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

window.setView = function(view) {
  // Clear active state on all nav items
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  const navItem = document.querySelector(`.nav-item[data-view="${view}"]`);
  if (navItem) navItem.classList.add('active');

  // Hide all overlays first
  spillView.classList.add('hidden');
  spillSplitView.classList.add('hidden');

  if (view === 'spill') {
    monitoringMain.classList.add('hidden');
    spillView.classList.remove('hidden');
  } else if (view === 'spillsplit') {
    monitoringMain.classList.add('hidden');
    spillSplitView.classList.remove('hidden');
    // Load SpillSplit data for all cases
    renderSpillSplit();
    // Update page header
    const icon = document.getElementById('pageTitleIcon');
    const title = document.getElementById('pageTitle');
    const sub = document.getElementById('pageSubtitle');
    if (icon)  icon.textContent  = '✂️';
    if (title) title.textContent = 'SpillSplit — Source Hypothesis Testing';
    if (sub)   sub.textContent   = 'Arabian Sea · One vs Two Source BIC Comparison · Module 4';
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
