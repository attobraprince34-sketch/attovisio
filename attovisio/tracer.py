"""
attovisio.tracer
~~~~~~~~~~~~~~~~
Capture des appels de fonctions, des exceptions et de la pile d'exécution.
Rend visible ce qui se passe "sous le capot" de votre code Python.
"""

import functools
import traceback
import time
import threading
import inspect
from datetime import datetime
from typing import Any, Callable, List, Optional

from .events import Event, EventBus


class Tracer:
    """
    Capture et journalise les appels de fonctions, les valeurs de retour
    et les exceptions levées.

    Utilisation simple::

        from attovisio import Tracer

        @Tracer.trace
        def ma_fonction(x):
            return x * 2

        ma_fonction(5)

    Utilisation avancée::

        tracer = Tracer(verbose=True)

        @tracer.watch
        def calcul(a, b):
            return a + b

    """

    # Instance partagée (singleton léger) pour l'API de classe
    _default: Optional["Tracer"] = None

    def __init__(self, verbose: bool = False, bus: Optional[EventBus] = None):
        """
        Initialise le Tracer.

        :param verbose: Si True, affiche les événements dans la console.
        :param bus: Bus d'événements partagé pour la collecte centralisée.
        """
        self.verbose = verbose
        self.bus = bus or EventBus.get_global()
        self._call_depth: dict = {}  # profondeur d'imbrication par thread

    # ------------------------------------------------------------------
    # API de classe (raccourcis statiques)
    # ------------------------------------------------------------------

    @classmethod
    def _get_default(cls) -> "Tracer":
        if cls._default is None:
            cls._default = cls()
        return cls._default

    @classmethod
    def trace(cls, func: Callable) -> Callable:
        """
        Décorateur de classe pour tracer une fonction sans instancier le Tracer.

        ::

            @Tracer.trace
            def demo(x):
                return x * 2

        """
        return cls._get_default().watch(func)

    # ------------------------------------------------------------------
    # Décorateur d'instance
    # ------------------------------------------------------------------

    def watch(self, func: Callable) -> Callable:
        """
        Décorateur qui enveloppe une fonction pour capturer ses appels.

        :param func: La fonction à surveiller.
        :returns: La fonction enveloppée.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self._execute(func, args, kwargs)
        wrapper._attovisio_traced = True
        return wrapper

    # ------------------------------------------------------------------
    # Logique interne
    # ------------------------------------------------------------------

    def _execute(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Exécute la fonction en capturant l'appel et le résultat."""
        tid = threading.get_ident()
        depth = self._call_depth.get(tid, 0)
        self._call_depth[tid] = depth + 1

        module = inspect.getmodule(func)
        module_name = module.__name__ if module else "?"
        source_file = inspect.getfile(func) if inspect.isfunction(func) else "?"
        try:
            source_line = inspect.getsourcelines(func)[1]
        except (OSError, TypeError):
            source_line = 0

        # Représentation lisible des arguments
        sig = inspect.signature(func)
        try:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            args_repr = {k: _safe_repr(v) for k, v in bound.arguments.items()}
        except TypeError:
            args_repr = {"args": [_safe_repr(a) for a in args], "kwargs": {k: _safe_repr(v) for k, v in kwargs.items()}}

        start = time.perf_counter()
        start_time = datetime.now()

        call_event = Event(
            kind="function_call",
            data={
                "function": func.__qualname__,
                "module": module_name,
                "file": source_file,
                "line": source_line,
                "arguments": args_repr,
                "depth": depth,
                "thread_id": tid,
            },
            timestamp=start_time,
        )
        self.bus.emit(call_event)
        if self.verbose:
            _print_event(call_event)

        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start

            return_event = Event(
                kind="function_return",
                data={
                    "function": func.__qualname__,
                    "module": module_name,
                    "return_value": _safe_repr(result),
                    "duration_ms": round(duration * 1000, 3),
                    "depth": depth,
                    "thread_id": tid,
                },
                timestamp=datetime.now(),
            )
            self.bus.emit(return_event)
            if self.verbose:
                _print_event(return_event)

            return result

        except Exception as exc:
            duration = time.perf_counter() - start
            tb = traceback.format_exc()

            error_event = Event(
                kind="exception",
                data={
                    "function": func.__qualname__,
                    "module": module_name,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "traceback": tb,
                    "duration_ms": round(duration * 1000, 3),
                    "depth": depth,
                    "thread_id": tid,
                },
                timestamp=datetime.now(),
            )
            self.bus.emit(error_event)
            if self.verbose:
                _print_event(error_event, error=True)
            raise

        finally:
            self._call_depth[tid] = max(0, self._call_depth.get(tid, 1) - 1)

    def get_events(self, kind: Optional[str] = None) -> List[Event]:
        """
        Retourne les événements capturés, filtrés par type si précisé.

        :param kind: Filtre optionnel (``"function_call"``, ``"exception"``, etc.).
        :returns: Liste d'événements.
        """
        return self.bus.get_events(kind=kind)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_repr(obj: Any, max_len: int = 120) -> str:
    """Représentation courte et sûre d'un objet."""
    try:
        r = repr(obj)
        return r if len(r) <= max_len else r[:max_len] + "…"
    except Exception:
        return "<non-représentable>"


def _print_event(event: Event, error: bool = False) -> None:
    """Affiche un événement dans la console (mode verbose)."""
    prefix = "❌" if error else ("📥" if event.kind == "function_call" else "📤")
    ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
    fn = event.data.get("function", "?")
    if event.kind == "function_call":
        args = event.data.get("arguments", {})
        print(f"{prefix} [{ts}] APPEL   {fn}({args})")
    elif event.kind == "function_return":
        dur = event.data.get("duration_ms", 0)
        ret = event.data.get("return_value", "")
        print(f"{prefix} [{ts}] RETOUR  {fn} → {ret}  ({dur} ms)")
    elif event.kind == "exception":
        exc = event.data.get("exception_type", "?")
        msg = event.data.get("exception_message", "")
        print(f"{prefix} [{ts}] ERREUR  {fn} → {exc}: {msg}")
