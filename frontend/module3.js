/* ═══════════════════════════════════════════════════════════════════════════
   Module 3 Integration — module3.js
   Hooks up case_01_drift.json to the Leaflet map and UI panels.
   ═══════════════════════════════════════════════════════════════════════════ */

let driftData = null;
let playbackInterval = null;
let currentStepIdx = 0;
let playbackSpeed = 1; // 1x, 3x, 8x
let isPlaying = false;
let particleGroup = L.layerGroup();
let originPolygon = null;

// Initialize
async function loadModule3Data(caseId) {
  try {
    const res = await fetch(`data/processed/${caseId}_drift.json`);
    driftData = await res.json();
    console.log("Loaded Module 3 Data:", driftData);
    
    // Show UI panels
    document.getElementById('hydroCard').classList.remove('hidden');
    document.getElementById('timelineScrubber').classList.remove('hidden');
    document.getElementById('regimePanel').classList.remove('hidden');
    document.getElementById('weatheringPanel').classList.remove('hidden');
    document.querySelector('.module-progress').classList.add('hidden'); // Hide the old progress list

    // Add map layers
    particleGroup.addTo(map);

    // Draw origin zone ellipse
    const oz = driftData.origin_zone;
    originPolygon = L.ellipse([oz.center_lat, oz.center_lon], [(oz.semi_major_km)*500, (oz.semi_minor_km)*500], oz.angle_deg, {
      color: '#ff5252',
      weight: 1,
      dashArray: '4 4',
      fillColor: '#ff5252',
      fillOpacity: 0.1
    }).addTo(map);

    // Setup slider
    const slider = document.getElementById('timeSlider');
    slider.max = driftData.trajectory.length - 1;
    slider.value = 0;
    
    // Seek to S1 Scan (0h offset) initially
    const s1Index = driftData.trajectory.findIndex(s => s.time_offset_hours === 0);
    if(s1Index !== -1) {
      seekTo(s1Index);
    } else {
      seekTo(0);
    }
  } catch (err) {
    console.error("No drift data found for", caseId);
  }
}

function seekTo(index) {
  if (!driftData) return;
  currentStepIdx = parseInt(index);
  document.getElementById('timeSlider').value = currentStepIdx;
  renderStep(driftData.trajectory[currentStepIdx]);
}

function renderStep(step) {
  // 1. Update Map Particles
  particleGroup.clearLayers();
  
  // Draw particles
  step.particles.forEach(p => {
    L.circleMarker([p[0], p[1]], {
      radius: 2,
      color: '#00e5ff',
      fillColor: '#00e5ff',
      fillOpacity: 0.8,
      weight: 0
    }).addTo(particleGroup);
  });
  
  // Draw centroid
  L.circleMarker([step.plume_centroid.latitude, step.plume_centroid.longitude], {
    radius: 6,
    color: '#ffd740',
    weight: 2,
    fillColor: '#ff5252',
    fillOpacity: 1
  }).addTo(particleGroup);

  // 2. Update Timeline UI
  const offset = step.time_offset_hours;
  const phaseEl = document.getElementById('scrubberPhase');
  if(offset < 0) { phaseEl.textContent = `Hindcast: ${offset.toFixed(1)}h`; phaseEl.style.color = '#ff5252'; }
  else if(offset === 0) { phaseEl.textContent = `S1 Scan: 0.0h`; phaseEl.style.color = '#00e5ff'; }
  else { phaseEl.textContent = `Forecast: +${offset.toFixed(1)}h`; phaseEl.style.color = '#ffd740'; }
  
  document.getElementById('scrubberTime').textContent = step.formatted_time;
  document.getElementById('scrubberMeta').textContent = `Plume Centroid: ${step.plume_centroid.latitude.toFixed(4)}°N, ${step.plume_centroid.longitude.toFixed(4)}°E · Area: ${step.plume_area_km2.toFixed(2)} km²`;

  // 3. Update Vector Hydrodynamics
  const vh = step.vector_hydrodynamics || driftData.vector_hydrodynamics;
  document.getElementById('hydroCurrent').textContent = `${vh.surface_current.speed_mps.toFixed(2)} m/s @ ${vh.surface_current.direction_deg.toFixed(0)}°`;
  document.getElementById('hydroWind').textContent = `${vh.wind_leeway.speed_knots.toFixed(1)} kts @ ${vh.wind_leeway.direction_deg.toFixed(0)}°`;
  document.getElementById('hydroNet').textContent = `${vh.net_advection.speed_kmh.toFixed(2)} km/h (${vh.net_advection.speed_knots.toFixed(2)} kts)`;

  // 4. Update Oceanographic Regime
  const reg = driftData.oceanographic_regime;
  document.getElementById('regimeName').textContent = reg.regime_name;
  document.getElementById('regimeSub').innerHTML = `📍 ${reg.sub_region}`;
  document.getElementById('regimeSeaState').textContent = reg.sea_state;
  document.getElementById('regimeTemp').textContent = `${reg.sea_temp_c} °C`;
  document.getElementById('regimeSalinity').textContent = `${reg.salinity_psu} PSU`;
  document.getElementById('regimeBathymetry').textContent = `${reg.bathymetry_m} m`;

  // 5. Update ADIOS Weathering
  const w = step.weathering || driftData.trajectory[driftData.trajectory.length-1].weathering;
  document.getElementById('wEvapPercent').textContent = `${w.evaporated_percent.toFixed(1)}%`;
  document.getElementById('wEvapBar').style.width = `${w.evaporated_percent}%`;
  
  document.getElementById('wDispPercent').textContent = `${w.dispersion_percent.toFixed(1)}%`;
  document.getElementById('wDispBar').style.width = `${w.dispersion_percent}%`;
  
  document.getElementById('wWaterPercent').textContent = `${w.water_content_percent.toFixed(1)}%`;
  document.getElementById('wWaterBar').style.width = `${w.water_content_percent}%`;
  
  document.getElementById('wRemainPercent').textContent = `${w.remaining_slick_percent.toFixed(1)}%`;
  document.getElementById('wRemainBar').style.width = `${w.remaining_slick_percent}%`;
  
  document.getElementById('wViscosity').textContent = Math.round(w.viscosity_cst);
  document.getElementById('wArea').textContent = w.slick_area_km2.toFixed(2);
  
  // Highlight active milestone button
  document.querySelectorAll('.m-btn').forEach(btn => {
    btn.classList.toggle('active', Math.abs(parseFloat(btn.dataset.target) - offset) < 0.1);
  });
}

function togglePlayback() {
  const btn = document.getElementById('btnPlayPause');
  if (isPlaying) {
    clearInterval(playbackInterval);
    isPlaying = false;
    btn.innerHTML = '▶';
  } else {
    isPlaying = true;
    btn.innerHTML = '⏸';
    if(currentStepIdx >= driftData.trajectory.length - 1) seekTo(0);
    playbackInterval = setInterval(() => {
      let nextIdx = currentStepIdx + playbackSpeed;
      if (nextIdx >= driftData.trajectory.length) {
        nextIdx = driftData.trajectory.length - 1;
        togglePlayback(); // Stop at end
      }
      seekTo(nextIdx);
    }, 100);
  }
}

// Event Listeners
document.getElementById('timeSlider').addEventListener('input', (e) => {
  if (isPlaying) togglePlayback();
  seekTo(e.target.value);
});

document.getElementById('btnPlayPause').addEventListener('click', togglePlayback);

document.querySelectorAll('.speed-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    playbackSpeed = parseInt(e.target.dataset.speed);
    document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
  });
});

document.querySelectorAll('.m-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    if (isPlaying) togglePlayback();
    const targetOffset = parseFloat(e.currentTarget.dataset.target);
    const closestIdx = driftData.trajectory.findIndex(s => Math.abs(s.time_offset_hours - targetOffset) < 0.2);
    if(closestIdx !== -1) seekTo(closestIdx);
  });
});

// Hook into view changes triggered from app.js
window.addEventListener('viewChanged', (e) => {
  const view = e.detail.view;
  
  if (view === 'drift') {
    // Show Module 3 UI
    document.getElementById('hydroCard').classList.remove('hidden');
    document.getElementById('timelineScrubber').classList.remove('hidden');
    document.getElementById('regimePanel').classList.remove('hidden');
    document.getElementById('weatheringPanel').classList.remove('hidden');
    document.getElementById('culpritPanel').classList.remove('hidden');
    document.querySelector('.module-progress').classList.add('hidden');
    
    // Auto load Case 01 if no data is loaded yet
    if (!driftData) {
      if(typeof L.ellipse === 'undefined') {
         const script = document.createElement('script');
         script.src = 'https://cdn.jsdelivr.net/npm/leaflet-ellipse@1.2.3/l.ellipse.min.js';
         script.onload = () => loadModule3Data(activeCaseFilter === 'all' ? 'case_01' : activeCaseFilter);
         document.head.appendChild(script);
      } else {
         loadModule3Data(activeCaseFilter === 'all' ? 'case_01' : activeCaseFilter);
      }
    } else {
      particleGroup.addTo(map);
      if(originPolygon) map.addLayer(originPolygon);
    }

    // Change title and subtitle
    const titleIcon = document.getElementById('pageTitleIcon');
    const title = document.getElementById('pageTitle');
    const subtitle = document.getElementById('pageSubtitle');
    if (titleIcon) titleIcon.textContent = '🌊';
    if (title) title.textContent = 'Drift Forecast & Trajectory Modeling';
    if (subtitle) subtitle.textContent = 'Arabian Sea · 48h Forecast & -24h Hindcast · Vector Hydrodynamics & ADIOS Weathering';

  } else if (view === 'monitoring') {
    // Hide Module 3 UI
    document.getElementById('hydroCard').classList.add('hidden');
    document.getElementById('timelineScrubber').classList.add('hidden');
    document.getElementById('regimePanel').classList.add('hidden');
    document.getElementById('weatheringPanel').classList.add('hidden');
    document.getElementById('culpritPanel').classList.add('hidden');
    
    // Ensure module progress shows in monitoring
    const moduleProgress = document.querySelector('.module-progress');
    if (moduleProgress) moduleProgress.classList.remove('hidden');
    
    if (map.hasLayer(particleGroup)) map.removeLayer(particleGroup);
    if (originPolygon && map.hasLayer(originPolygon)) map.removeLayer(originPolygon);

    if (isPlaying) togglePlayback();

    // Restore title and subtitle
    const titleIcon = document.getElementById('pageTitleIcon');
    const title = document.getElementById('pageTitle');
    const subtitle = document.getElementById('pageSubtitle');
    if (titleIcon) titleIcon.textContent = '📡';
    if (title) title.textContent = 'Regional Monitoring';
    if (subtitle) subtitle.textContent = 'Arabian Sea · 3 Investigation Cases · Modules 1–2 Active';
  }
});

// Hijack the case pill click to load module 3 data IF we are in drift mode
document.getElementById('casePills').addEventListener('click', e => {
  const pill = e.target.closest('.pill');
  if (!pill) return;
  const caseId = pill.dataset.case;
  
  // Only load new JSON if Drift Forecast is the active view
  const isDriftActive = document.querySelector('.nav-item[data-view="drift"]').classList.contains('active');
  if (isDriftActive && caseId !== 'all') {
    loadModule3Data(caseId);
  } else if (isDriftActive && caseId === 'all') {
    particleGroup.clearLayers();
    if(originPolygon) map.removeLayer(originPolygon);
  }
});

