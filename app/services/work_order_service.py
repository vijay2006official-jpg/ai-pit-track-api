from typing import Dict, Any
from app.models.pit import RoadPit, SeverityLevel

class WorkOrderService:
    @staticmethod
    def calculate_repair_material_estimate(severity: SeverityLevel, est_area_sq_px: float) -> Dict[str, Any]:
        """
        Estimates asphalt patch weight, crew hours, and recommended repair equipment.
        """
        # Baseline multipliers based on severity
        severity_multipliers = {
            SeverityLevel.LOW: {"depth_cm": 2.5, "labor_hours": 0.5, "priority": "Standard (Within 14 Days)"},
            SeverityLevel.MEDIUM: {"depth_cm": 5.0, "labor_hours": 1.0, "priority": "High (Within 5 Days)"},
            SeverityLevel.HIGH: {"depth_cm": 8.0, "labor_hours": 2.0, "priority": "Urgent (Within 48 Hours)"},
            SeverityLevel.CRITICAL: {"depth_cm": 12.0, "labor_hours": 3.5, "priority": "Emergency (Immediate Dispatch)"},
        }

        specs = severity_multipliers.get(severity, severity_multipliers[SeverityLevel.MEDIUM])
        
        # Approximate surface area in sq meters (scaled from pixel area)
        approx_area_sq_m = max(0.2, min(4.0, (est_area_sq_px or 5000.0) / 25000.0))
        depth_m = specs["depth_cm"] / 100.0
        volume_cu_m = round(approx_area_sq_m * depth_m, 3)

        # Asphalt density ~ 2.4 tonnes per m^3
        cold_mix_asphalt_kg = round(volume_cu_m * 2400.0, 1)
        tack_coat_liters = round(approx_area_sq_m * 0.7, 1)

        return {
            "estimated_area_sq_meters": round(approx_area_sq_m, 2),
            "estimated_depth_cm": specs["depth_cm"],
            "asphalt_volume_cu_m": volume_cu_m,
            "cold_mix_asphalt_kg": cold_mix_asphalt_kg,
            "tack_coat_primer_liters": tack_coat_liters,
            "estimated_labor_hours": specs["labor_hours"],
            "dispatch_priority": specs["priority"],
            "recommended_tools": [
                "Plate Compactor / Vibratory Roller",
                "Asphalt Rake & Shovel",
                "Tack Coat Spray Applicator",
                "Traffic Safety Cones & High-Vis Signage"
            ]
        }

    @staticmethod
    def generate_printable_html_work_order(pit: RoadPit, latest_image_url: str = None) -> str:
        """
        Generates a high-quality printable work order ticket styled with print-ready CSS.
        """
        estimates = WorkOrderService.calculate_repair_material_estimate(pit.severity, pit.estimated_area_sq_px)
        
        severity_badge_class = {
            SeverityLevel.CRITICAL: "bg-red-600 text-white",
            SeverityLevel.HIGH: "bg-orange-500 text-white",
            SeverityLevel.MEDIUM: "bg-amber-500 text-slate-950",
            SeverityLevel.LOW: "bg-emerald-600 text-white",
        }.get(pit.severity, "bg-gray-600 text-white")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Work Order #WO-{pit.id:05d} | Road Defect Repair</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @media print {{
      body {{ font-size: 12px; color: black; background: white; }}
      .no-print {{ display: none !important; }}
      .print-shadow {{ box-shadow: none !important; border: 1px solid #ccc !important; }}
    }}
  </style>
</head>
<body class="bg-slate-100 text-slate-900 p-8 min-h-screen">
  <div class="max-w-4xl mx-auto bg-white p-8 rounded-2xl shadow-lg border border-slate-200 print-shadow space-y-6">
    
    <!-- Action Bar -->
    <div class="flex items-center justify-between no-print border-b pb-4">
      <a href="/dashboard" class="text-sm font-semibold text-slate-600 hover:text-black">← Back to Dashboard</a>
      <button onclick="window.print()" class="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded-lg shadow transition-all">
        🖨️ Print Work Order (PDF)
      </button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between border-b border-slate-200 pb-5">
      <div>
        <h1 class="text-2xl font-black tracking-tight text-slate-900">DEPARTMENT OF PUBLIC WORKS</h1>
        <p class="text-xs uppercase tracking-wider text-slate-500 font-semibold mt-0.5">Municipal Highway & Road Maintenance Dispatch</p>
      </div>
      <div class="text-right">
        <div class="text-sm font-bold text-slate-800">TICKET #WO-{pit.id:05d}</div>
        <div class="text-xs text-slate-500">Issued: {pit.first_detected_at.strftime('%Y-%m-%d %H:%M UTC')}</div>
      </div>
    </div>

    <!-- Defect Summary Banner -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
      <div>
        <span class="block text-xs font-semibold text-slate-500">Hazard Severity</span>
        <span class="inline-block mt-1 px-2.5 py-0.5 rounded text-xs font-bold {severity_badge_class}">{pit.severity.value}</span>
      </div>
      <div>
        <span class="block text-xs font-semibold text-slate-500">Dispatch Priority</span>
        <span class="block text-xs font-bold text-slate-800 mt-1">{estimates['dispatch_priority']}</span>
      </div>
      <div>
        <span class="block text-xs font-semibold text-slate-500">Current Status</span>
        <span class="block text-xs font-bold text-slate-800 mt-1">{pit.status.value}</span>
      </div>
      <div>
        <span class="block text-xs font-semibold text-slate-500">Inspection Count</span>
        <span class="block text-xs font-bold text-slate-800 mt-1">{pit.detection_count} Automated Scans</span>
      </div>
    </div>

    <!-- Location & Telemetry -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
      <div class="space-y-3">
        <h3 class="text-sm font-bold border-b pb-1 text-slate-800">📍 Geo Location & Routing</h3>
        <p class="text-xs text-slate-700"><b>Road / Segment:</b> {pit.road_name or 'Main Route'}</p>
        <p class="text-xs text-slate-700"><b>Address / Marker:</b> {pit.address or 'N/A'}</p>
        <p class="text-xs text-slate-700 font-mono"><b>GPS Coordinates:</b> {pit.latitude:.5f}, {pit.longitude:.5f}</p>
        <p class="text-xs text-blue-600 underline">
          <a href="https://www.google.com/maps?q={pit.latitude},{pit.longitude}" target="_blank">Open Navigation Map (Google Maps)</a>
        </p>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-bold border-b pb-1 text-slate-800">🏗️ Material & Equipment Estimations</h3>
        <p class="text-xs text-slate-700"><b>Estimated Defect Area:</b> ~{estimates['estimated_area_sq_meters']} m² (Depth: {estimates['estimated_depth_cm']} cm)</p>
        <p class="text-xs text-slate-700"><b>Cold/Hot Asphalt Mix Required:</b> ~{estimates['cold_mix_asphalt_kg']} kg ({estimates['asphalt_volume_cu_m']} m³)</p>
        <p class="text-xs text-slate-700"><b>Tack Coat Primer:</b> ~{estimates['tack_coat_primer_liters']} Liters</p>
        <p class="text-xs text-slate-700"><b>Estimated Repair Duration:</b> ~{estimates['estimated_labor_hours']} Crew Hours</p>
      </div>
    </div>

    <!-- Visual Evidence Snapshot -->
    <div class="space-y-2">
      <h3 class="text-sm font-bold border-b pb-1 text-slate-800">📸 AI Vision Defect Evidence</h3>
      <div class="rounded-xl overflow-hidden border border-slate-300 max-h-64 bg-slate-900 flex items-center justify-center">
        {f'<img src="{latest_image_url}" class="w-full h-full object-contain max-h-64" />' if latest_image_url else '<div class="p-8 text-xs text-slate-400">Image recorded on field inspection vehicle</div>'}
      </div>
    </div>

    <!-- Crew Sign-Off Section -->
    <div class="border-t border-slate-200 pt-5 grid grid-cols-2 gap-6">
      <div class="space-y-6">
        <div>
          <span class="block text-xs font-semibold text-slate-500 mb-6">Assigned Crew Lead Signature:</span>
          <div class="border-b border-slate-400 w-4/5"></div>
        </div>
        <div>
          <span class="block text-xs font-semibold text-slate-500 mb-6">Repair Completion Date:</span>
          <div class="border-b border-slate-400 w-4/5"></div>
        </div>
      </div>

      <div class="space-y-2 bg-slate-50 p-3 rounded-lg border border-slate-200 text-[11px] text-slate-600">
        <span class="font-bold block text-slate-800">Safety & Standard Protocol Checklist:</span>
        <p>☐ Set up safety cones 15m prior to repair zone</p>
        <p>☐ Clean loose gravel and moisture from cavity</p>
        <p>☐ Apply tack coat spray to edges & base</p>
        <p>☐ Compact asphalt in layers not exceeding 5cm</p>
      </div>
    </div>

  </div>
</body>
</html>
"""
        return html
