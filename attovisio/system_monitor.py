"""
attovisio.system_monitor
~~~~~~~~~~~~~~~~~~~~~~~~
Surveillance en temps réel du CPU, de la mémoire, des threads et des processus.
Rend visible la consommation de ressources de votre programme.
"""

import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from .events import Event, EventBus


class SystemMonitor:
    """
    Surveille les ressources système (CPU, RAM, threads, processus).

    ::

        from attovisio import Monitor

        monitor = Monitor()
        monitor.start(interval=1.0)   # échantillonnage toutes les secondes
        # ... votre code ...
        monitor.stop()
        rapport = monitor.summary()

    Utilisation comme gestionnaire de contexte::

        with Monitor() as m:
            calcul_intensif()
        print(m.summary())

    """

    def __init__(
        self,
        interval: float = 1.0,
        bus: Optional[EventBus] = None,
        verbose: bool = False,
    ):
        """
        :param interval: Intervalle d'échantillonnage en secondes.
        :param bus: Bus d'événements partagé.
        :param verbose: Affiche les métriques dans la console.
        """
        if not _HAS_PSUTIL:
            raise ImportError(
                "psutil est requis pour SystemMonitor.\n"
                "Installez-le avec : pip install psutil"
            )
        self.interval = interval
        self.bus = bus or EventBus.get_global()
        self.verbose = verbose

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._samples: List[dict] = []
        self._process = psutil.Process()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def start(self, interval: Optional[float] = None) -> "SystemMonitor":
        """
        Démarre la surveillance en arrière-plan.

        :param interval: Surcharge l'intervalle défini à la construction.
        :returns: L'instance (chaînage possible).
        """
        if interval is not None:
            self.interval = interval
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="attovisio-monitor")
        self._thread.start()
        return self

    def stop(self) -> "SystemMonitor":
        """Arrête la surveillance."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval * 2)
        return self

    def __enter__(self) -> "SystemMonitor":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Surveillance ponctuelle
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """
        Effectue une capture instantanée des métriques système.

        :returns: Dictionnaire avec cpu, memory, threads, open_files.
        """
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        proc_cpu = self._process.cpu_percent(interval=None)
        proc_mem = self._process.memory_info()
        n_threads = self._process.num_threads()

        try:
            open_files = len(self._process.open_files())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            open_files = -1

        try:
            connections = len(self._process.net_connections())
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            connections = -1

        sample = {
            "timestamp": datetime.now().isoformat(),
            "system_cpu_percent": cpu,
            "system_memory_total_mb": round(mem.total / 1_048_576, 1),
            "system_memory_used_mb": round(mem.used / 1_048_576, 1),
            "system_memory_percent": mem.percent,
            "process_cpu_percent": proc_cpu,
            "process_memory_rss_mb": round(proc_mem.rss / 1_048_576, 2),
            "process_threads": n_threads,
            "process_open_files": open_files,
            "process_connections": connections,
        }
        return sample

    # ------------------------------------------------------------------
    # Boucle d'arrière-plan
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        """Boucle principale de surveillance."""
        while self._running:
            sample = self.snapshot()
            self._samples.append(sample)

            event = Event(
                kind="system_metrics",
                data=sample,
                timestamp=datetime.fromisoformat(sample["timestamp"]),
            )
            self.bus.emit(event)

            if self.verbose:
                cpu = sample["process_cpu_percent"]
                mem = sample["process_memory_rss_mb"]
                thr = sample["process_threads"]
                ts = sample["timestamp"][11:19]
                print(f"📊 [{ts}] CPU:{cpu}%  RAM:{mem}MB  Threads:{thr}")

            time.sleep(self.interval)

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """
        Retourne un résumé statistique des métriques collectées.

        :returns: Dictionnaire avec min/max/avg pour CPU et mémoire.
        """
        if not self._samples:
            return {"error": "Aucune donnée collectée."}

        cpus = [s["process_cpu_percent"] for s in self._samples]
        mems = [s["process_memory_rss_mb"] for s in self._samples]
        thrs = [s["process_threads"] for s in self._samples]

        def _stats(values: list) -> dict:
            return {
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "avg": round(sum(values) / len(values), 2),
            }

        return {
            "samples": len(self._samples),
            "duration_s": round(len(self._samples) * self.interval, 1),
            "cpu_percent": _stats(cpus),
            "memory_rss_mb": _stats(mems),
            "threads": _stats(thrs),
        }

    def get_samples(self) -> List[dict]:
        """Retourne la liste brute de tous les échantillons."""
        return list(self._samples)

    # ------------------------------------------------------------------
    # Décorateur
    # ------------------------------------------------------------------

    def profile(self, func):
        """
        Décorateur : surveille les ressources pendant l'exécution de la fonction.

        ::

            @monitor.profile
            def traitement_lourd():
                ...

        """
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with SystemMonitor(interval=0.1, bus=self.bus) as local_mon:
                result = func(*args, **kwargs)
            summary = local_mon.summary()
            event = Event(
                kind="function_profile",
                data={
                    "function": func.__qualname__,
                    "resources": summary,
                },
            )
            self.bus.emit(event)
            return result

        return wrapper


# ------------------------------------------------------------------
# Décorateur rapide (sans instancier Monitor)
# ------------------------------------------------------------------

@contextmanager
def monitor_block(label: str = "bloc", bus: Optional[EventBus] = None):
    """
    Gestionnaire de contexte léger pour surveiller un bloc de code.

    ::

        with monitor_block("chargement données"):
            données = charger_gros_fichier()

    """
    bus = bus or EventBus.get_global()
    mon = SystemMonitor(interval=0.1, bus=bus)
    mon.start()
    try:
        yield mon
    finally:
        mon.stop()
        summary = mon.summary()
        event = Event(kind="block_profile", data={"label": label, "resources": summary})
        bus.emit(event)
