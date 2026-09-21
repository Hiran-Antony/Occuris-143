"""
Module 3 Demo — Terminal Playback Console
Simulates the operational surveillance interface data panels (Vector Hydrodynamics, Timeline, & Weathering).
Uses ANSI color codes to match the exact aesthetic of the frontend mockup.
"""
import sys, json, argparse, os
from pathlib import Path

os.system('') # Enable ANSI colors on Windows

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import CASES

class C:
    CYAN = '\033[38;2;0;255;255m'
    GREEN = '\033[38;2;0;255;100m'
    YELLOW = '\033[38;2;255;200;0m'
    RED = '\033[38;2;255;50;80m'
    BLUE_BG = '\033[48;2;0;50;100m'
    GRAY = '\033[90m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def load_drift(case_id: str) -> dict:
    p = ROOT / "data" / "processed" / f"{case_id}_drift.json"
    if not p.exists():
        print(f"Run python src/drift/backward_drift.py --case {case_id} first.")
        sys.exit(1)
    return json.loads(p.read_text())

def get_step_at_offset(trajectory: list, target_offset: float) -> dict:
    return min(trajectory, key=lambda s: abs(s["time_offset_hours"] - target_offset))

def format_left_panel(step: dict, data: dict, milestones: list, active_id: str) -> list:
    lines = []
    
    # 1. Hydro Card
    vh = step.get("vector_hydrodynamics", data["vector_hydrodynamics"])
    sc = vh["surface_current"]
    wl = vh["wind_leeway"]
    na = vh["net_advection"]
    
    lines.append(f"  +{'-'*45}+")
    lines.append(f"  | {C.CYAN}{C.BOLD}VECTOR HYDRODYNAMICS{C.RESET} {C.BLUE_BG} HYCOM {C.RESET}" + " "*13 + "|")
    lines.append(f"  |                                             |")
    lines.append(f"  | ~ Surface Current:  {C.CYAN}{sc['speed_mps']:.2f} m/s @ {sc['direction_deg']:.0f} deg{C.RESET}" + " "*7 + "|")
    lines.append(f"  | * Wind Leeway:      {C.GREEN}{wl['speed_knots']:.1f} kts @ {wl['direction_deg']:.0f} deg{C.RESET}" + " "*8 + "|")
    lines.append(f"  | > Net Advection:    {C.YELLOW}{na['speed_kmh']:.2f} km/h ({na['speed_knots']:.2f} kts){C.RESET} |")
    lines.append(f"  +{'-'*45}+")
    lines.append("")
    lines.append("")
    lines.append("")
    
    # 2. Timeline
    offset = step["time_offset_hours"]
    if offset < 0: label = f"{C.RED}Hindcast: {offset:.1f}h{C.RESET}"
    elif offset == 0: label = f"{C.CYAN}S1 Scan:   0h{C.RESET}"
    else: label = f"{C.YELLOW}Forecast: +{offset:.1f}h{C.RESET}"

    btns = []
    for m in milestones:
        m_id = m["id"]
        txt = m["label"]
        if m_id == active_id: btns.append(f"[{C.CYAN}{C.BOLD}{txt}{C.RESET}]")
        else: btns.append(f"[ {C.GRAY}{txt}{C.RESET} ]")
    btn_str = "  ".join(btns)
    
    c = step["plume_centroid"]
    area = step["plume_area_km2"]
    
    bar_len = 70
    pos = int((offset - (-24)) / (48 - (-24)) * bar_len)
    pos = max(0, min(bar_len-1, pos))
    bar = f"{C.CYAN}{'=' * pos}O{C.GRAY}{'=' * (bar_len - pos - 1)}{C.RESET}"
    
    lines.append(f"  +{'-'*85}+")
    lines.append(f"  |  [ Play ]  1x  3x  8x    {label}      ( {step['formatted_time']} )")
    lines.append(f"  |                          Plume Centroid: {c['latitude']:.4f} N, {c['longitude']:.4f} E * Area: {area:.2f} km2")
    lines.append(f"  |")
    lines.append(f"  |  {btn_str}")
    lines.append(f"  |")
    lines.append(f"  |  {bar}")
    lines.append(f"  |  {C.RED}-6h Reconstructed Discharge{C.RESET}   {C.GRAY}-3h{C.RESET}   {C.CYAN}0h Satellite Detection{C.RESET}   {C.GRAY}+12h   +24h   +36h{C.RESET}   {C.YELLOW}+48h Dispersion Horizon{C.RESET}")
    lines.append(f"  +{'-'*85}+")
    
    return lines

def format_right_panel(step: dict, data: dict) -> list:
    lines = []
    w = step["weathering"]
    r = data["oceanographic_regime"]
    
    lines.append(f"  +{'-'*45}+")
    lines.append(f"  | {C.WHITE}{C.BOLD}REGIONAL OCEANOGRAPHIC REGIME{C.RESET} {C.BLUE_BG} CMEMS HYCOM {C.RESET}|")
    lines.append(f"  |                                             |")
    lines.append(f"  |  {C.CYAN}{C.BOLD}{r['regime_name']}{C.RESET}" + " "*12 + "|")
    lines.append(f"  |  {C.GRAY}{r['sub_region']}{C.RESET}" + " "*4 + "|")
    lines.append(f"  |                                             |")
    lines.append(f"  |  ~ Sea State: {r['sea_state']}" + " "*3 + "|")
    lines.append(f"  |  * Sea Temp:  {r['sea_temp_c']} C  * Salinity: {r['salinity_psu']} PSU      |")
    lines.append(f"  |  _ Bathymetry:{r['bathymetry_m']} m" + " "*22 + "|")
    lines.append(f"  +{'-'*45}+")
    lines.append(f"  +{'-'*45}+")
    lines.append(f"  | {C.WHITE}{C.BOLD}ADIOS WEATHERING MASS BALANCE{C.RESET} {C.YELLOW} ASTM F2464 {C.RESET}|")
    lines.append(f"  |                                             |")
    lines.append(f"  |  {C.CYAN}Evaporated Light Ends:{C.RESET}" + f"{w['evaporated_percent']:>17.1f}% |")
    lines.append(f"  |  {C.GREEN}Natural Wave Dispersion:{C.RESET}" + f"{w['dispersion_percent']:>15.1f}% |")
    lines.append(f"  |  {C.YELLOW}Water Content (Mousse):{C.RESET}" + f"{w['water_content_percent']:>16.1f}% |")
    lines.append(f"  |  {C.RED}Remaining Surface Slick:{C.RESET}" + f"{w['remaining_slick_percent']:>15.1f}% |")
    lines.append(f"  |                                             |")
    lines.append(f"  |  {C.WHITE}MOUSSE VISCOSITY{C.RESET}      {C.WHITE}SLICK SURFACE AREA{C.RESET}   |")
    lines.append(f"  |  {C.YELLOW}{w['viscosity_cst']:.0f} cSt{C.RESET}             {C.CYAN}{w['slick_area_km2']:.2f} km2{C.RESET}          |")
    lines.append(f"  +{'-'*45}+")
    
    return lines

def run_demo(case_id: str, highlight_step: float = 5.8):
    data = load_drift(case_id)
    traj = data["trajectory"]
    milestones = data["milestones"]
    
    print(f"\n{C.BOLD}=== OCCURIS MODULE 3 TERMINAL INTERFACE [{case_id.upper()}] ==={C.RESET}")
    
    # Grab the closest step to +5.8h (to mimic the screenshot exactly)
    step = get_step_at_offset(traj, highlight_step)
    
    print(f"\n{C.BOLD}--- SCENE: Forecast +{highlight_step}h ---{C.RESET}\n")
    
    left_lines = format_left_panel(step, data, milestones, active_id="forecast_12h")
    right_lines = format_right_panel(step, data)
    
    # Pad left lines so they can be zipped
    max_len = max(len(left_lines), len(right_lines))
    left_lines.extend(["" * 90] * (max_len - len(left_lines)))
    right_lines.extend(["" * 50] * (max_len - len(right_lines)))
    
    for l, r in zip(left_lines, right_lines):
        # We assume Left panel is 90 chars wide visually (ANSI makes length hard to calculate)
        # So we just print them with a fixed separator if left is not empty
        print(f"{l}\t\t{r}")
        
    print("\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="case_01", help="Case ID")
    args = parser.parse_args()
    run_demo(args.case)
