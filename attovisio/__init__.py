"""
AttoVisio — Rend visibles les actions invisibles en informatique.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Une bibliothèque Python pour observer, tracer et narrer ce qui se passe
réellement dans votre programme : appels de fonctions, fichiers, réseau,
ressources système et sécurité.

Utilisation minimale::

    from attovisio import Tracer

    @Tracer.trace
    def demo(x):
        return x * 2

    demo(5)

Utilisation complète::

    from attovisio import Tracer, Monitor, Narrator, Visualizer, EventBus

    tracer = Tracer(verbose=True)

    @tracer.watch
    def calcul(a, b):
        return a + b

    with Monitor() as m:
        calcul(3, 4)

    Narrator().tell()                    # récit textuel
    Visualizer().dashboard("rapport.html")  # tableau de bord HTML

"""

from .events import Event, EventBus
from .tracer import Tracer
from .narration import Narrator
from .visualization import Visualizer
from .io_observer import IOObserver
from .security_auditor import SecurityAuditor

# Imports conditionnels (nécessitent psutil)
try:
    from .system_monitor import SystemMonitor, monitor_block
    from .network_watcher import NetworkWatcher
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

    class SystemMonitor:  # type: ignore
        def __init__(self, *a, **kw):
            raise ImportError("Installez psutil : pip install psutil")

    class NetworkWatcher:  # type: ignore
        def __init__(self, *a, **kw):
            raise ImportError("Installez psutil : pip install psutil")

    def monitor_block(*a, **kw):  # type: ignore
        raise ImportError("Installez psutil : pip install psutil")


# Alias pratiques
Monitor = SystemMonitor


def reset() -> None:
    """Réinitialise le bus global (utile entre deux sessions de tests)."""
    EventBus.reset_global()


def get_events(kind=None):
    """Raccourci pour récupérer les événements du bus global."""
    return EventBus.get_global().get_events(kind=kind)


def export_json(filepath: str) -> None:
    """Raccourci pour exporter tous les événements en JSON."""
    EventBus.get_global().export_json(filepath)


def tell() -> str:
    """Raccourci pour générer un récit texte de tous les événements."""
    return Narrator().tell()


__version__ = "0.1.0"
__author__ = "Attobra Prince"
__email__ = "attobraprince@example.com"
__license__ = "MIT"

__all__ = [
    # Noyau
    "Event",
    "EventBus",
    # Modules principaux
    "Tracer",
    "SystemMonitor",
    "Monitor",
    "IOObserver",
    "NetworkWatcher",
    "SecurityAuditor",
    "Visualizer",
    "Narrator",
    # Utilitaires
    "monitor_block",
    "reset",
    "get_events",
    "export_json",
    "tell",
    # Méta
    "__version__",
]
