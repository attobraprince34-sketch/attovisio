"""
attovisio.visualization
~~~~~~~~~~~~~~~~~~~~~~~
Génération de graphes, timelines et rapports HTML interactifs à partir
des événements collectés. Pas besoin de matplotlib ni de dépendances lourdes :
la sortie principale est du HTML/SVG autonome.
"""

import json
import os
from collections import Counter
from datetime import datetime
from typing import List, Optional

from .events import Event, EventBus


# ------------------------------------------------------------------
# Couleurs par type d'événement
# ------------------------------------------------------------------

EVENT_COLORS = {
    "function_call":    "#2196F3",
    "function_return":  "#4CAF50",
    "exception":        "#F44336",
    "file_open":        "#FF9800",
    "file_write":       "#FF5722",
    "file_read":        "#FFC107",
    "file_close":       "#9E9E9E",
    "file_delete":      "#E91E63",
    "network_connect":  "#9C27B0",
    "network_disconnect": "#673AB7",
    "system_metrics":   "#607D8B",
    "security_alert":   "#F44336",
    "function_profile": "#00BCD4",
    "block_profile":    "#009688",
    "subprocess_exec":  "#795548",
}

EVENT_ICONS = {
    "function_call":    "⚡",
    "function_return":  "✅",
    "exception":        "❌",
    "file_open":        "📂",
    "file_write":       "✍️",
    "file_read":        "👁️",
    "file_close":       "📁",
    "file_delete":      "🗑️",
    "network_connect":  "🌐",
    "security_alert":   "🚨",
    "system_metrics":   "📊",
}


class Visualizer:
    """
    Génère des visualisations HTML interactives des événements AttoVisio.

    ::

        from attovisio import Visualizer

        viz = Visualizer()
        viz.timeline("rapport.html")         # Timeline interactive
        viz.flamegraph("flamme.html")         # Graphe d'appels
        viz.dashboard("tableau_bord.html")    # Tableau de bord complet

    """

    def __init__(self, bus: Optional[EventBus] = None):
        """
        :param bus: Bus d'événements partagé.
        """
        self.bus = bus or EventBus.get_global()

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def timeline(
        self,
        filepath: str,
        events: Optional[List[Event]] = None,
        title: str = "AttoVisio — Timeline",
    ) -> str:
        """
        Génère une timeline HTML interactive des événements.

        :param filepath: Chemin du fichier HTML de sortie.
        :param events: Liste d'événements (utilise le bus si None).
        :param title: Titre du rapport.
        :returns: Chemin absolu du fichier créé.
        """
        if events is None:
            events = self.bus.get_events()

        rows_html = ""
        for event in events:
            color = EVENT_COLORS.get(event.kind, "#607D8B")
            icon = EVENT_ICONS.get(event.kind, "•")
            ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            fn = event.data.get("function", event.data.get("path", event.data.get("remote_address", "")))
            detail = fn[:60] + "…" if fn and len(fn) > 60 else (fn or "")
            duration = event.data.get("duration_ms", "")
            dur_badge = f'<span style="background:#e0e0e0;border-radius:4px;padding:1px 6px;font-size:11px;">{duration} ms</span>' if duration else ""

            rows_html += f"""
            <tr class="event-row" data-kind="{event.kind}">
                <td style="padding:6px 10px;white-space:nowrap;color:#666;font-size:12px;">{ts}</td>
                <td style="padding:6px 10px;">
                    <span style="background:{color};color:#fff;border-radius:4px;padding:2px 8px;font-size:12px;font-family:monospace;">
                        {icon} {event.kind}
                    </span>
                </td>
                <td style="padding:6px 10px;font-family:monospace;font-size:13px;">{detail}</td>
                <td style="padding:6px 10px;">{dur_badge}</td>
            </tr>
            """

        # Filtres
        kinds = sorted(set(e.kind for e in events))
        filter_buttons = "".join(
            f'<button onclick="filterEvents(\'{k}\')" style="margin:3px;padding:4px 10px;border-radius:4px;border:none;cursor:pointer;background:{EVENT_COLORS.get(k,"#607D8B")};color:#fff;font-size:12px;">{k}</button>'
            for k in kinds
        )

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f5f5f5; }}
    .header {{ background: linear-gradient(135deg, #1a237e, #283593); color: #fff; padding: 24px 32px; }}
    .header h1 {{ margin: 0; font-size: 24px; }}
    .header p {{ margin: 6px 0 0; opacity: .7; font-size: 14px; }}
    .stats {{ display: flex; gap: 16px; padding: 16px 32px; flex-wrap: wrap; }}
    .stat-card {{ background: #fff; border-radius: 8px; padding: 12px 20px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
    .stat-card .num {{ font-size: 28px; font-weight: bold; color: #1a237e; }}
    .stat-card .label {{ font-size: 12px; color: #888; }}
    .filters {{ padding: 8px 32px; }}
    .table-wrap {{ padding: 0 32px 32px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
    thead {{ background: #1a237e; color: #fff; }}
    th {{ padding: 10px 12px; text-align: left; font-size: 13px; }}
    tr.event-row:hover {{ background: #f3f4ff; }}
    tr.event-row.hidden {{ display: none; }}
    .reset-btn {{ margin: 3px; padding: 4px 10px; border-radius: 4px; border: 1px solid #ccc; cursor: pointer; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>🔭 {title}</h1>
    <p>Généré par AttoVisio le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')} — {len(events)} événements</p>
  </div>

  <div class="stats">
    <div class="stat-card"><div class="num">{len(events)}</div><div class="label">Événements totaux</div></div>
    <div class="stat-card"><div class="num">{len(kinds)}</div><div class="label">Types distincts</div></div>
    <div class="stat-card"><div class="num">{sum(1 for e in events if e.kind == 'exception')}</div><div class="label">Exceptions</div></div>
    <div class="stat-card"><div class="num">{sum(1 for e in events if e.kind == 'security_alert')}</div><div class="label">Alertes sécurité</div></div>
  </div>

  <div class="filters">
    <strong style="font-size:13px;">Filtrer : </strong>
    {filter_buttons}
    <button class="reset-btn" onclick="showAll()">Tout afficher</button>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Horodatage</th>
          <th>Type</th>
          <th>Détail</th>
          <th>Durée</th>
        </tr>
      </thead>
      <tbody id="events-body">
        {rows_html}
      </tbody>
    </table>
  </div>

  <script>
    function filterEvents(kind) {{
      document.querySelectorAll('.event-row').forEach(function(row) {{
        row.classList.toggle('hidden', row.dataset.kind !== kind);
      }});
    }}
    function showAll() {{
      document.querySelectorAll('.event-row').forEach(function(row) {{
        row.classList.remove('hidden');
      }});
    }}
  </script>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return os.path.abspath(filepath)

    # ------------------------------------------------------------------
    # Flamegraph des appels
    # ------------------------------------------------------------------

    def flamegraph(
        self,
        filepath: str,
        events: Optional[List[Event]] = None,
        title: str = "AttoVisio — Flamegraph",
    ) -> str:
        """
        Génère un graphe en flammes des fonctions tracées.

        :param filepath: Chemin du fichier HTML de sortie.
        :param events: Liste d'événements (utilise le bus si None).
        :returns: Chemin absolu du fichier créé.
        """
        if events is None:
            events = self.bus.get_events()

        returns = [e for e in events if e.kind == "function_return"]
        if not returns:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("<p>Pas de données de fonction disponibles.</p>")
            return os.path.abspath(filepath)

        # Durées par fonction
        fn_durations: dict = {}
        for e in returns:
            fn = e.data.get("function", "?")
            dur = float(e.data.get("duration_ms", 0))
            fn_durations.setdefault(fn, []).append(dur)

        fn_avg = {fn: sum(d)/len(d) for fn, d in fn_durations.items()}
        max_dur = max(fn_avg.values()) if fn_avg else 1

        # Barres SVG
        bars = ""
        y = 20
        w_total = 700
        for fn, avg in sorted(fn_avg.items(), key=lambda x: -x[1]):
            pct = avg / max_dur
            bw = max(int(pct * (w_total - 160)), 4)
            color = f"hsl({int(120 * (1 - pct))},70%,55%)"
            fn_short = fn[:35] + "…" if len(fn) > 35 else fn
            bars += (
                f'<rect x="160" y="{y}" width="{bw}" height="22" fill="{color}" rx="3"/>'
                f'<text x="155" y="{y+16}" text-anchor="end" font-size="12" fill="#333">{fn_short}</text>'
                f'<text x="{160+bw+6}" y="{y+16}" font-size="11" fill="#555">{avg:.1f} ms</text>'
            )
            y += 30

        svg_h = y + 20
        content = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>{title}</title>
<style>body{{font-family:Arial;margin:24px;background:#fafafa;}}h2{{color:#1a237e;}}</style>
</head><body>
<h2>🔥 {title}</h2>
<p style="color:#666;font-size:13px;">Durée moyenne par fonction (ms) — {len(returns)} retours capturés</p>
<svg viewBox="0 0 900 {svg_h}" xmlns="http://www.w3.org/2000/svg" style="max-width:900px;">
{bars}
</svg>
</body></html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return os.path.abspath(filepath)

    # ------------------------------------------------------------------
    # Tableau de bord complet
    # ------------------------------------------------------------------

    def dashboard(
        self,
        filepath: str,
        events: Optional[List[Event]] = None,
        title: str = "AttoVisio — Tableau de bord",
    ) -> str:
        """
        Génère un tableau de bord HTML complet combinant timeline,
        statistiques et alertes de sécurité.

        :param filepath: Chemin du fichier HTML de sortie.
        :param events: Liste d'événements (utilise le bus si None).
        :returns: Chemin absolu du fichier créé.
        """
        if events is None:
            events = self.bus.get_events()

        # Compte par type
        counts = Counter(e.kind for e in events)
        bars_html = ""
        max_count = max(counts.values()) if counts else 1
        for kind, count in sorted(counts.items(), key=lambda x: -x[1]):
            pct = int(count / max_count * 200)
            color = EVENT_COLORS.get(kind, "#607D8B")
            icon = EVENT_ICONS.get(kind, "•")
            bars_html += f"""
            <div style="display:flex;align-items:center;margin:6px 0;">
                <span style="width:200px;font-size:13px;color:#333;">{icon} {kind}</span>
                <div style="background:{color};height:18px;width:{pct}px;border-radius:4px;"></div>
                <span style="margin-left:8px;font-size:13px;color:#555;">{count}</span>
            </div>"""

        # Alertes sécurité
        alerts = [e for e in events if e.kind == "security_alert"]
        alerts_html = ""
        for a in alerts[:10]:
            sev = a.data.get("severity", "INFO")
            msg = a.data.get("message", "")
            sev_color = {"HIGH": "#F44336", "MEDIUM": "#FF9800", "INFO": "#2196F3"}.get(sev, "#607D8B")
            alerts_html += f'<div style="padding:8px;margin:4px 0;border-left:4px solid {sev_color};background:#fff;border-radius:0 4px 4px 0;font-size:13px;"><strong style="color:{sev_color};">[{sev}]</strong> {msg}</div>'

        if not alerts_html:
            alerts_html = '<p style="color:green;">✅ Aucune alerte de sécurité.</p>'

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f0f2f5; }}
    .header {{ background: linear-gradient(135deg, #0d47a1, #1565c0); color: #fff; padding: 28px 40px; }}
    .header h1 {{ margin: 0; font-size: 26px; }}
    .header p {{ margin: 8px 0 0; opacity: .75; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 24px 40px; }}
    .card {{ background: #fff; border-radius: 10px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
    .card h3 {{ margin: 0 0 16px; font-size: 15px; color: #1a237e; border-bottom: 2px solid #e8eaf6; padding-bottom: 8px; }}
    .full-width {{ grid-column: 1 / -1; }}
    @media (max-width: 700px) {{ .grid {{ grid-template-columns: 1fr; padding: 12px; }} }}
  </style>
</head>
<body>
  <div class="header">
    <h1>🔭 {title}</h1>
    <p>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')} — {len(events)} événements capturés</p>
  </div>

  <div class="grid">
    <div class="card">
      <h3>📊 Distribution des événements</h3>
      {bars_html}
    </div>
    <div class="card">
      <h3>🚨 Alertes de sécurité ({len(alerts)})</h3>
      {alerts_html}
    </div>
    <div class="card full-width">
      <h3>⏱️ Résumé</h3>
      <table style="width:100%;font-size:13px;border-collapse:collapse;">
        <tr style="background:#e8eaf6;"><th style="padding:8px;text-align:left;">Type</th><th style="padding:8px;text-align:right;">Nombre</th></tr>
        {"".join(f'<tr><td style="padding:6px 8px;">{k}</td><td style="padding:6px 8px;text-align:right;">{v}</td></tr>' for k, v in sorted(counts.items(), key=lambda x: -x[1]))}
      </table>
    </div>
  </div>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return os.path.abspath(filepath)

    def export_json(self, filepath: str, events: Optional[List[Event]] = None) -> str:
        """
        Exporte tous les événements en JSON.

        :param filepath: Chemin du fichier de sortie.
        :returns: Chemin absolu du fichier créé.
        """
        if events is None:
            events = self.bus.get_events()
        data = [e.to_dict() for e in events]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return os.path.abspath(filepath)


    def charts(
        self,
        filepath: str,
        events: Optional[List[Event]] = None,
        title: str = "AttoVisio — Dashboard Graphiques",
    ) -> str:
        """
        Génère un dashboard HTML avec de vrais graphiques interactifs
        (courbes CPU/RAM, camembert, barres de durées) via Chart.js.

        Aucune dépendance Python supplémentaire — Chart.js est chargé via CDN.

        :param filepath: Chemin du fichier HTML de sortie.
        :param events: Liste d'événements (utilise le bus si None).
        :returns: Chemin absolu du fichier créé.
        """
        import json as _json
        from collections import Counter

        if events is None:
            events = self.bus.get_events()

        metrics    = [e for e in events if e.kind == "system_metrics"]
        returns    = [e for e in events if e.kind == "function_return"]
        exceptions = [e for e in events if e.kind == "exception"]
        alerts     = [e for e in events if e.kind == "security_alert"]
        net        = [e for e in events if "network" in e.kind]
        files      = [e for e in events if "file" in e.kind]

        cpu = [round(e.data.get("process_cpu_percent", 0), 1) for e in metrics]
        ram = [round(e.data.get("process_memory_rss_mb", 0), 1) for e in metrics]
        ts  = [e.timestamp.strftime("%H:%M:%S") for e in metrics]

        fn_durs: dict = {}
        for e in returns:
            fn = e.data.get("function", "?").split(".")[-1]
            fn_durs.setdefault(fn, []).append(float(e.data.get("duration_ms", 0)))

        fn_labels = list(fn_durs.keys())
        fn_avgs   = [round(sum(v) / len(v), 2) for v in fn_durs.values()]
        fn_max    = [round(max(v), 2) for v in fn_durs.values()]
        fn_counts = [len(v) for v in fn_durs.values()]

        kind_counts = Counter(e.kind for e in events)
        donut_colors = [EVENT_COLORS.get(k, "#94A3B8") for k in kind_counts.keys()]

        alert_rows = ""
        for a in alerts:
            sev = a.data.get("severity", "INFO")
            msg = a.data.get("message", "")
            det = a.data.get("detail", "")
            sc  = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "INFO": "#3B82F6"}.get(sev, "#64748B")
            alert_rows += f'<div class="alert-item"><span class="alert-badge" style="background:{sc}">{sev}</span><div class="alert-text"><div class="alert-msg">{msg}</div><div class="alert-det">{det}</div></div></div>'

        net_rows  = "".join(f'<div class="net-item">🌐 <strong>{n.data.get("protocol","TCP")}</strong> → {n.data.get("remote_host") or n.data.get("remote_address","?")}</div>' for n in net)
        file_rows = "".join(f'<div class="file-item">📄 {f.data.get("filename", f.data.get("path","?"))} <span class="mode-badge">mode:{f.data.get("mode","r")}</span></div>' for f in files)

        tl_rows = ""
        for e in events[-20:]:
            color = EVENT_COLORS.get(e.kind, "#64748B")
            icon  = EVENT_ICONS.get(e.kind, "•")
            fn    = (e.data.get("function") or e.data.get("filename") or e.data.get("remote_host") or "")[:40]
            dur   = e.data.get("duration_ms", "")
            dur_s = f'<span class="dur-badge">{dur}ms</span>' if dur else ""
            tl_rows += f'<tr><td class="td-ts">{e.timestamp.strftime("%H:%M:%S")}</td><td><span class="kind-pill" style="background:{color}">{icon} {e.kind}</span></td><td class="td-fn">{fn}</td><td>{dur_s}</td></tr>'

        avg_cpu = round(sum(cpu) / len(cpu), 1) if cpu else 0
        html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#0B0F1A;--surface:#131929;--surface2:#1C2438;--border:#252E45;--accent:#6EE7B7;--accent2:#818CF8;--text:#E2E8F0;--muted:#64748B;--font-head:'Syne',sans-serif;--font-mono:'JetBrains Mono',monospace;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-mono);}}
.header{{display:flex;align-items:center;justify-content:space-between;padding:18px 32px;border-bottom:1px solid var(--border);}}
.logo-text{{font-family:var(--font-head);font-size:22px;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
.logo-sub{{font-size:11px;color:var(--muted);letter-spacing:.08em;}}
.header-meta{{font-size:11px;color:var(--muted);text-align:right;}}
.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:20px 32px 0;}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 20px;position:relative;overflow:hidden;}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;}}
.kpi.blue::before{{background:linear-gradient(90deg,#3B82F6,#818CF8);}}
.kpi.green::before{{background:linear-gradient(90deg,#10B981,#6EE7B7);}}
.kpi.red::before{{background:linear-gradient(90deg,#EF4444,#F87171);}}
.kpi.yellow::before{{background:linear-gradient(90deg,#F59E0B,#FBBF24);}}
.kpi-num{{font-family:var(--font-head);font-size:34px;font-weight:800;line-height:1;}}
.kpi-label{{font-size:10px;color:var(--muted);margin-top:5px;letter-spacing:.06em;text-transform:uppercase;}}
.kpi-icon{{position:absolute;top:14px;right:16px;font-size:20px;opacity:.2;}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:14px;padding:18px 32px;}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px 22px;}}
.card-title{{font-family:var(--font-head);font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:14px;display:flex;align-items:center;gap:8px;}}
.dot{{width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0;}}
.full-width{{grid-column:1/-1;}}
canvas{{max-height:200px;}}
.alert-item{{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);}}
.alert-item:last-child{{border-bottom:none;}}
.alert-badge{{font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;color:#fff;white-space:nowrap;flex-shrink:0;}}
.alert-msg{{font-size:12px;color:var(--text);}}
.alert-det{{font-size:11px;color:var(--muted);margin-top:2px;}}
.net-item,.file-item{{font-size:12px;padding:6px 0;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;}}
.net-item:last-child,.file-item:last-child{{border-bottom:none;}}
.mode-badge{{font-size:10px;background:var(--surface2);padding:1px 6px;border-radius:4px;color:var(--muted);margin-left:auto;}}
table{{width:100%;border-collapse:collapse;font-size:11px;}}
th{{text-align:left;padding:7px 8px;color:var(--muted);border-bottom:1px solid var(--border);font-size:10px;text-transform:uppercase;letter-spacing:.08em;}}
td{{padding:6px 8px;border-bottom:1px solid rgba(255,255,255,.04);}}
.td-ts{{color:var(--muted);white-space:nowrap;}}
.kind-pill{{font-size:10px;padding:2px 7px;border-radius:4px;color:#fff;white-space:nowrap;}}
.dur-badge{{font-size:10px;background:var(--surface2);padding:2px 6px;border-radius:4px;color:var(--accent);}}
tr:hover td{{background:var(--surface2);}}
</style></head><body>
<div class="header">
  <div class="logo">🔭 <span class="logo-text">AttoVisio</span> <span class="logo-sub" style="margin-left:8px">Dashboard</span></div>
  <div class="header-meta"><div>{len(events)} événements</div><div style="color:var(--accent);margin-top:2px">● Rapport généré</div></div>
</div>
<div class="kpi-grid">
  <div class="kpi blue"><span class="kpi-icon">⚡</span><div class="kpi-num" style="color:#818CF8">{sum(fn_counts)}</div><div class="kpi-label">Appels de fonctions</div></div>
  <div class="kpi green"><span class="kpi-icon">📊</span><div class="kpi-num" style="color:#6EE7B7">{avg_cpu}%</div><div class="kpi-label">CPU moyen</div></div>
  <div class="kpi red"><span class="kpi-icon">❌</span><div class="kpi-num" style="color:#F87171">{len(exceptions)}</div><div class="kpi-label">Exceptions</div></div>
  <div class="kpi yellow"><span class="kpi-icon">🚨</span><div class="kpi-num" style="color:#FBBF24">{len(alerts)}</div><div class="kpi-label">Alertes sécurité</div></div>
</div>
<div class="grid">
  <div class="card"><div class="card-title"><span class="dot" style="background:#6EE7B7"></span>CPU &amp; RAM dans le temps</div><canvas id="cpuRam"></canvas></div>
  <div class="card"><div class="card-title"><span class="dot" style="background:#818CF8"></span>Répartition événements</div><canvas id="donut"></canvas></div>
  <div class="card"><div class="card-title"><span class="dot" style="background:#F59E0B"></span>Durée moy / max par fonction (ms)</div><canvas id="duration"></canvas></div>
  <div class="card">
    <div class="card-title"><span class="dot" style="background:#EF4444"></span>Alertes sécurité</div>
    {alert_rows or '<div style="color:var(--accent);font-size:13px;">✅ Aucune alerte</div>'}
    <div style="margin-top:14px;" class="card-title"><span class="dot" style="background:#8B5CF6"></span>Réseau</div>{net_rows or '<div style="color:var(--muted);font-size:12px;">Aucune connexion</div>'}
  </div>
  <div class="card"><div class="card-title"><span class="dot" style="background:#3B82F6"></span>Appels &amp; Durée max</div><canvas id="grouped"></canvas></div>
  <div class="card"><div class="card-title"><span class="dot" style="background:#F97316"></span>Fichiers accédés</div>{file_rows or '<div style="color:var(--muted);font-size:12px;">Aucun fichier</div>'}</div>
  <div class="card full-width"><div class="card-title"><span class="dot"></span>Timeline — 20 derniers événements</div>
    <table><thead><tr><th>Heure</th><th>Type</th><th>Détail</th><th>Durée</th></tr></thead><tbody>{tl_rows}</tbody></table>
  </div>
</div>
<script>
Chart.defaults.color='#64748B';Chart.defaults.borderColor='#252E45';
Chart.defaults.font.family="'JetBrains Mono',monospace";Chart.defaults.font.size=11;
new Chart(document.getElementById('cpuRam'),{{type:'line',data:{{labels:{_json.dumps(ts)},datasets:[{{label:'CPU %',data:{_json.dumps(cpu)},borderColor:'#6EE7B7',backgroundColor:'rgba(110,231,183,.08)',borderWidth:2,pointRadius:3,tension:0.4,fill:true,yAxisID:'y'}},{{label:'RAM MB',data:{_json.dumps(ram)},borderColor:'#818CF8',backgroundColor:'rgba(129,140,248,.08)',borderWidth:2,pointRadius:3,tension:0.4,fill:true,yAxisID:'y1'}}]}},options:{{responsive:true,interaction:{{mode:'index',intersect:false}},scales:{{y:{{position:'left',grid:{{color:'#1C2438'}},ticks:{{color:'#6EE7B7'}}}},y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{color:'#818CF8'}}}},x:{{grid:{{color:'#1C2438'}}}}}},plugins:{{legend:{{labels:{{color:'#94A3B8',boxWidth:12}}}}}}}}}});
new Chart(document.getElementById('donut'),{{type:'doughnut',data:{{labels:{_json.dumps(list(kind_counts.keys()))},datasets:[{{data:{_json.dumps(list(kind_counts.values()))},backgroundColor:{_json.dumps(donut_colors)},borderColor:'#0B0F1A',borderWidth:3,hoverOffset:8}}]}},options:{{responsive:true,cutout:'62%',plugins:{{legend:{{position:'right',labels:{{color:'#94A3B8',boxWidth:10,font:{{size:10}},padding:6}}}}}}}}}});
new Chart(document.getElementById('duration'),{{type:'bar',data:{{labels:{_json.dumps(fn_labels)},datasets:[{{label:'Moy',data:{_json.dumps(fn_avgs)},backgroundColor:['rgba(110,231,183,.7)','rgba(129,140,248,.7)','rgba(251,191,36,.7)'],borderColor:['#6EE7B7','#818CF8','#FBBF24'],borderWidth:1,borderRadius:5}},{{label:'Max',data:{_json.dumps(fn_max)},backgroundColor:['rgba(110,231,183,.25)','rgba(129,140,248,.25)','rgba(251,191,36,.25)'],borderColor:['#6EE7B7','#818CF8','#FBBF24'],borderWidth:1,borderRadius:5}}]}},options:{{responsive:true,scales:{{y:{{grid:{{color:'#1C2438'}},beginAtZero:true}},x:{{grid:{{color:'#1C2438'}}}}}},plugins:{{legend:{{labels:{{color:'#94A3B8',boxWidth:12}}}}}}}}}});
new Chart(document.getElementById('grouped'),{{type:'bar',data:{{labels:{_json.dumps(fn_labels)},datasets:[{{label:'Nb appels',data:{_json.dumps(fn_counts)},backgroundColor:'rgba(59,130,246,.7)',borderColor:'#3B82F6',borderWidth:1,borderRadius:5,yAxisID:'y'}},{{label:'Durée max (ms)',data:{_json.dumps(fn_max)},backgroundColor:'rgba(239,68,68,.5)',borderColor:'#EF4444',borderWidth:1,borderRadius:5,yAxisID:'y1',type:'line',tension:0.3,pointRadius:5,pointBackgroundColor:'#EF4444'}}]}},options:{{responsive:true,interaction:{{mode:'index',intersect:false}},scales:{{y:{{position:'left',beginAtZero:true,grid:{{color:'#1C2438'}},ticks:{{color:'#3B82F6'}}}},y1:{{position:'right',beginAtZero:true,grid:{{drawOnChartArea:false}},ticks:{{color:'#EF4444'}}}},x:{{grid:{{color:'#1C2438'}}}}}},plugins:{{legend:{{labels:{{color:'#94A3B8',boxWidth:12}}}}}}}}}});
</script></body></html>"""

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(html)
        return os.path.abspath(filepath)
