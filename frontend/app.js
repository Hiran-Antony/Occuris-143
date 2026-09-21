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
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    { attribution: '© CartoDB', maxZoom: 19 }
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
const monitoringMain = document.querySelector('.main');
const spillView      = document.getElementById('spillView');

document.querySelectorAll('.nav-item:not(.disabled)').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    const view = item.dataset.view;

    // Clear active state
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');

    if (view === 'spill') {
      spillView.classList.remove('hidden');
    } else {
      spillView.classList.add('hidden');
    }
  });
});

document.getElementById('backToMonitoring').addEventListener('click', () => {
  spillView.classList.add('hidden');
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelector('[data-view="monitoring"]').classList.add('active');
});

// ─── Start with dark marine layer ────────────────────────────────────────────
mapBtns.dark.click();

// ─── Inject pulse keyframe into document ─────────────────────────────────────
const style = document.createElement('style');
style.textContent = `
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 4px transparent; }
    50%      { box-shadow: 0 0 0 8px transparent; opacity: 0.7; }
  }
`;
document.head.appendChild(style);
