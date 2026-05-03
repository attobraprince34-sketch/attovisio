"""
AttoVisio — Démo Avancée
========================
Montre l'utilisation combinée de Tracer, IOObserver,
SecurityAuditor, Narrator et Visualizer.

Lancez-le avec : python examples/demo_advanced.py
"""

import sys
import os
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from attovisio import (
    Tracer, IOObserver, SecurityAuditor,
    Narrator, Visualizer, EventBus, reset
)

# Réinitialiser pour une démo propre
reset()
bus = EventBus.get_global()

print("=" * 60)
print("  🔭 AttoVisio — Démo Avancée")
print("=" * 60)

# ── 1. Tracer plusieurs fonctions ────────────────────────────
print("\n🔵 PARTIE 1 : Traçage de fonctions")

tracer = Tracer(verbose=False, bus=bus)

@tracer.watch
def charger_données(chemin: str) -> list:
    """Simule le chargement d'un fichier CSV."""
    time.sleep(0.02)
    return [{"id": i, "valeur": i * 10} for i in range(5)]

@tracer.watch
def filtrer(données: list, seuil: int) -> list:
    """Filtre les lignes dont la valeur dépasse le seuil."""
    return [d for d in données if d["valeur"] >= seuil]

@tracer.watch
def calculer_moyenne(données: list) -> float:
    """Calcule la moyenne des valeurs."""
    if not données:
        raise ValueError("Aucune donnée à analyser")
    return sum(d["valeur"] for d in données) / len(données)

# Exécution normale
données = charger_données("data/ventes.csv")
filtrées = filtrer(données, seuil=20)
moy = calculer_moyenne(filtrées)
print(f"  ✅ Moyenne calculée : {moy}")

# Simulation d'erreur
try:
    calculer_moyenne([])
except ValueError as e:
    print(f"  ⚠️  Erreur capturée : {e}")

# ── 2. Observation des fichiers ──────────────────────────────
print("\n🔵 PARTIE 2 : Observation des fichiers")

observer = IOObserver(bus=bus, verbose=False)

with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    tmp_path = f.name
    observer.log_open(tmp_path, mode="w")
    f.write("Données importantes\n")
    observer.log_write(tmp_path, size_bytes=20)

observer.log_read(tmp_path, size_bytes=20)
observer.log_delete(tmp_path)

file_events = bus.get_events()
file_event_kinds = [e.kind for e in file_events if "file" in e.kind]
print(f"  ✅ Événements fichiers : {file_event_kinds}")

# Nettoyage
try:
    os.unlink(tmp_path)
except FileNotFoundError:
    pass

# ── 3. Audit de sécurité ─────────────────────────────────────
print("\n🔵 PARTIE 3 : Audit de sécurité")

auditor = SecurityAuditor(bus=bus, verbose=False)
auditor.start()

# Simuler un accès à un fichier sensible
bus.emit_test = lambda: bus.emit(
    __import__("attovisio.events", fromlist=["Event"]).Event(
        kind="file_open",
        data={
            "path": "/home/user/.ssh/id_rsa",
            "absolute_path": "/home/user/.ssh/id_rsa",
            "filename": "id_rsa",
            "extension": "",
            "mode": "r",
        }
    )
)
bus.emit_test()

alerts = auditor.get_alerts()
print(f"  🚨 {len(alerts)} alerte(s) de sécurité détectée(s)")
for a in alerts:
    print(f"     [{a['severity']}] {a['message']}")

auditor.stop()

# ── 4. Narration ─────────────────────────────────────────────
print("\n🔵 PARTIE 4 : Narration en langage naturel")

narrator = Narrator(bus=bus)
events_for_story = bus.get_events(kind="function_call")[:3]
for e in events_for_story:
    print("  →", narrator.narrate(e))

# ── 5. Visualisation HTML ────────────────────────────────────
print("\n🔵 PARTIE 5 : Génération des rapports HTML")

viz = Visualizer(bus=bus)
output_dir = os.path.join(os.path.dirname(__file__), "..", "output_demo")
os.makedirs(output_dir, exist_ok=True)

timeline_path = viz.timeline(os.path.join(output_dir, "timeline.html"), title="Démo Avancée — Timeline")
dashboard_path = viz.dashboard(os.path.join(output_dir, "dashboard.html"), title="Démo Avancée — Dashboard")
flamegraph_path = viz.flamegraph(os.path.join(output_dir, "flamegraph.html"), title="Démo Avancée — Flamegraph")
json_path = viz.export_json(os.path.join(output_dir, "events.json"))

print(f"  ✅ Timeline     → {timeline_path}")
print(f"  ✅ Dashboard    → {dashboard_path}")
print(f"  ✅ Flamegraph   → {flamegraph_path}")
print(f"  ✅ JSON export  → {json_path}")

# ── 6. Résumé final ──────────────────────────────────────────
print("\n" + "=" * 60)
all_events = bus.get_events()
print(f"  📊 Total événements capturés : {len(all_events)}")
from collections import Counter
counts = Counter(e.kind for e in all_events)
for kind, count in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"     • {kind:<30} {count}")
print("=" * 60)
print("  🎉 Démo avancée terminée ! Ouvrez output_demo/*.html")
print("=" * 60)
