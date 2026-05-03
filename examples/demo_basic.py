"""
AttoVisio — Démo basique
========================
Ce fichier montre l'utilisation minimale d'AttoVisio.
Lancez-le avec : python examples/demo_basic.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from attovisio import Tracer, EventBus

print("=" * 55)
print("  🔭 AttoVisio — Démo Basique")
print("=" * 55)

# ── 1. Décorateur de classe ──────────────────────────────────
print("\n📌 Exemple 1 : Décorateur @Tracer.trace")

@Tracer.trace
def demo(x):
    """Fonction de démonstration."""
    return x * 2

result = demo(5)
print(f"  demo(5) → {result}")

# ── 2. Instance avec verbose ─────────────────────────────────
print("\n📌 Exemple 2 : Tracer avec verbose=True")

tracer = Tracer(verbose=True)

@tracer.watch
def addition(a, b):
    return a + b

@tracer.watch
def soustraction(a, b):
    return a - b

addition(10, 3)
soustraction(10, 3)

# ── 3. Capture d'exceptions ──────────────────────────────────
print("\n📌 Exemple 3 : Capture d'exception")

@tracer.watch
def division(a, b):
    return a / b

try:
    division(10, 0)
except ZeroDivisionError:
    pass

# ── 4. Résumé des événements ─────────────────────────────────
print("\n📌 Exemple 4 : Résumé du bus global")
bus = EventBus.get_global()
events = bus.get_events()

print(f"  Total événements : {len(events)}")
for kind in sorted(set(e.kind for e in events)):
    count = sum(1 for e in events if e.kind == kind)
    print(f"    • {kind} : {count}")

print("\n✅ Démo basique terminée !")
