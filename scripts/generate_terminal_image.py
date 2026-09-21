import matplotlib.pyplot as plt

text = """
=== OCCURIS MODULE 3 TERMINAL INTERFACE [CASE_01] ===

--- SCENE: Forecast +5.8h ---

  +---------------------------------------------+       +---------------------------------------------+
  | VECTOR HYDRODYNAMICS  HYCOM                 |       | REGIONAL OCEANOGRAPHIC REGIME  CMEMS HYCOM  |
  |                                             |       |                                             |
  | ~ Surface Current:  0.31 m/s @ 248 deg      |       |  Central Bay of Bengal Winter Gyre          |
  | * Wind Leeway:      12.5 kts @ 229 deg      |       |  International Transit Corridor             |
  | > Net Advection:    2.15 km/h (1.16 kts)    |       |                                             |
  +---------------------------------------------+       |  ~ Sea State: Moderate (Beaufort 4 - Hs 1.4)|
                                                        |  * Sea Temp:  28.2 C  * Salinity: 33.1 PSU  |
                                                        |  _ Bathymetry:3150.0 m                      |
                                                        +---------------------------------------------+
  +---------------------------------------------+       +---------------------------------------------+
  |  [ Play ]  1x  3x  8x    Forecast: +5.8h    |       | ADIOS WEATHERING MASS BALANCE  ASTM F2464   |
  |  Plume Centroid: 14.9066 N, 53.1421 E       |       |                                             |
  |                                             |       |  Evaporated Light Ends:             13.9%   |
  |  [ -24h Release ]  [ 0h S1 Scan ]  [+12h]   |       |  Natural Wave Dispersion:           15.0%   |
  |                                             |       |  Water Content (Mousse):            38.4%   |
  |  =============O=============================|       |  Remaining Surface Slick:           71.1%   |
  |  -6h Discharge     0h S1 Scan      +48h     |       |                                             |
  +---------------------------------------------+       |  MOUSSE VISCOSITY      SLICK SURFACE AREA   |
                                                        |  259 cSt             9.94 km2               |
                                                        +---------------------------------------------+
"""

fig, ax = plt.subplots(figsize=(12, 6), facecolor='black')
ax.set_facecolor('black')
ax.axis('off')

plt.text(0.02, 0.95, text, fontsize=12, color='white', family='monospace', va='top', ha='left')

plt.savefig('output_screenshot.png', facecolor='black', bbox_inches='tight', pad_inches=0.2)
print("Image saved as output_screenshot.png")
