"""
attovisio.io_observer
~~~~~~~~~~~~~~~~~~~~~
Journalisation des accès fichiers (lecture, écriture, ouverture, fermeture).
Rend visible chaque interaction de votre programme avec le système de fichiers.
"""

import builtins
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from .events import Event, EventBus


# Référence à l'open() original avant tout monkey-patching
_original_open = builtins.open
_original_os_remove = os.remove
_original_os_rename = os.rename

_patch_lock = threading.Lock()
_is_patched = False


class IOObserver:
    """
    Observe les opérations de fichiers effectuées par votre programme.

    Deux modes de fonctionnement :

    1. **Passif** : s'abonne aux événements déjà émis par le bus.
    2. **Actif** (``intercept=True``) : remplace ``builtins.open`` pour
       capturer *toutes* les ouvertures de fichiers (y compris celles
       des bibliothèques tierces).

    .. warning::
        Le mode actif modifie ``builtins.open`` globalement.  Utilisez
        ``restore()`` ou le gestionnaire de contexte pour annuler.

    ::

        from attovisio import IOObserver

        observer = IOObserver(intercept=True, verbose=True)
        observer.start()

        with open("data.txt", "w") as f:
            f.write("bonjour")

        observer.stop()

    """

    def __init__(
        self,
        intercept: bool = False,
        verbose: bool = False,
        bus: Optional[EventBus] = None,
        ignore_prefixes: Optional[Set[str]] = None,
    ):
        """
        :param intercept: Active le mode actif (monkey-patch de ``open``).
        :param verbose: Affiche chaque événement fichier dans la console.
        :param bus: Bus d'événements partagé.
        :param ignore_prefixes: Chemins à ignorer (ex. ``{"/proc", "/sys"}``).
        """
        self.intercept = intercept
        self.verbose = verbose
        self.bus = bus or EventBus.get_global()
        self.ignore_prefixes: Set[str] = ignore_prefixes or {"/proc", "/sys", "/dev"}

    def start(self) -> "IOObserver":
        """Démarre l'observation."""
        if self.intercept:
            self._patch_open()
        return self

    def stop(self) -> "IOObserver":
        """Arrête l'observation et restaure ``open`` si patché."""
        if self.intercept:
            self._restore_open()
        return self

    def __enter__(self) -> "IOObserver":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # API publique pour émettre manuellement des événements
    # ------------------------------------------------------------------

    def log_open(self, path: str, mode: str = "r") -> None:
        """Journalise manuellement l'ouverture d'un fichier."""
        self._emit("file_open", path, {"mode": mode})

    def log_write(self, path: str, size_bytes: int = 0) -> None:
        """Journalise manuellement une écriture."""
        self._emit("file_write", path, {"size_bytes": size_bytes})

    def log_read(self, path: str, size_bytes: int = 0) -> None:
        """Journalise manuellement une lecture."""
        self._emit("file_read", path, {"size_bytes": size_bytes})

    def log_delete(self, path: str) -> None:
        """Journalise manuellement une suppression."""
        self._emit("file_delete", path, {})

    def log_rename(self, src: str, dst: str) -> None:
        """Journalise manuellement un renommage."""
        self._emit("file_rename", src, {"destination": dst})

    # ------------------------------------------------------------------
    # Monkey-patching
    # ------------------------------------------------------------------

    def _patch_open(self) -> None:
        """Remplace ``builtins.open`` par une version instrumentée."""
        global _is_patched
        observer = self

        with _patch_lock:
            if _is_patched:
                return

            def instrumented_open(file, mode="r", *args, **kwargs):
                path_str = str(file)
                if not observer._should_ignore(path_str):
                    observer._emit("file_open", path_str, {"mode": mode})
                fh = _original_open(file, mode, *args, **kwargs)
                return _wrap_file_handle(fh, path_str, observer)

            builtins.open = instrumented_open
            _is_patched = True

    def _restore_open(self) -> None:
        """Restaure ``builtins.open`` original."""
        global _is_patched
        with _patch_lock:
            builtins.open = _original_open
            _is_patched = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_ignore(self, path: str) -> bool:
        """Retourne True si ce chemin doit être ignoré."""
        return any(path.startswith(p) for p in self.ignore_prefixes)

    def _emit(self, kind: str, path: str, extra: dict) -> None:
        """Construit et émet un événement fichier."""
        abs_path = str(Path(path).resolve()) if path else path
        data = {
            "path": path,
            "absolute_path": abs_path,
            "filename": os.path.basename(path),
            "extension": os.path.splitext(path)[1],
            **extra,
        }
        event = Event(kind=kind, data=data)
        self.bus.emit(event)
        if self.verbose:
            icons = {
                "file_open": "📂", "file_write": "✍️",
                "file_read": "👁️", "file_delete": "🗑️", "file_rename": "✏️",
            }
            icon = icons.get(kind, "📄")
            ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            print(f"{icon} [{ts}] {kind.upper()} → {path}")


class _WrappedFile:
    """Enveloppe d'un objet fichier pour capturer les lectures/écritures."""

    def __init__(self, fh, path: str, observer: IOObserver):
        self._fh = fh
        self._path = path
        self._observer = observer

    def write(self, data) -> int:
        size = len(data) if isinstance(data, (bytes, str)) else 0
        result = self._fh.write(data)
        if not self._observer._should_ignore(self._path):
            self._observer._emit("file_write", self._path, {"size_bytes": size})
        return result

    def read(self, *args) -> bytes:
        result = self._fh.read(*args)
        size = len(result) if result else 0
        if not self._observer._should_ignore(self._path):
            self._observer._emit("file_read", self._path, {"size_bytes": size})
        return result

    def close(self) -> None:
        self._fh.close()
        if not self._observer._should_ignore(self._path):
            self._observer._emit("file_close", self._path, {})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __getattr__(self, name):
        return getattr(self._fh, name)

    def __iter__(self):
        return iter(self._fh)


def _wrap_file_handle(fh, path: str, observer: IOObserver):
    """Enveloppe un file handle si possible, sinon le retourne tel quel."""
    try:
        return _WrappedFile(fh, path, observer)
    except Exception:
        return fh
