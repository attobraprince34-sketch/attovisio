"""
attovisio.events
~~~~~~~~~~~~~~~~
Système d'événements central d'AttoVisio.
Tous les modules émettent des ``Event`` sur le ``EventBus`` global.
"""

import json
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Event:
    """
    Représente un événement observable capturé par AttoVisio.

    :param kind: Type d'événement (``"function_call"``, ``"cpu_spike"``, etc.).
    :param data: Dictionnaire de données associées à l'événement.
    :param timestamp: Horodatage de l'événement.
    """
    kind: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Sérialise l'événement en dictionnaire."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    def to_json(self) -> str:
        """Sérialise l'événement en JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __str__(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        return f"[{ts}] {self.kind.upper()} — {self.data}"


class EventBus:
    """
    Bus central qui collecte tous les événements émis par les modules AttoVisio.

    Les listeners (fonctions de rappel) peuvent s'abonner à des types d'événements
    spécifiques ou à tous les événements.

    ::

        bus = EventBus.get_global()
        bus.subscribe("exception", lambda e: print("ERREUR :", e))

    """

    _global: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._events: List[Event] = []
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_global(cls) -> "EventBus":
        """Retourne le bus global partagé (singleton thread-safe)."""
        if cls._global is None:
            with cls._lock:
                if cls._global is None:
                    cls._global = cls()
        return cls._global

    @classmethod
    def reset_global(cls) -> None:
        """Réinitialise le bus global (utile pour les tests)."""
        with cls._lock:
            cls._global = None

    def emit(self, event: Event) -> None:
        """
        Émet un événement sur le bus.

        :param event: L'événement à émettre.
        """
        with self._lock:
            self._events.append(event)
            listeners = list(self._listeners.get(event.kind, []))
            listeners += list(self._listeners.get("*", []))

        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass  # ne jamais laisser un listener planter le programme

    def subscribe(self, kind: str, callback: Callable[[Event], None]) -> None:
        """
        S'abonne à un type d'événement.

        :param kind: Type d'événement, ou ``"*"`` pour tous.
        :param callback: Fonction appelée à chaque événement correspondant.
        """
        with self._lock:
            self._listeners.setdefault(kind, []).append(callback)

    def unsubscribe(self, kind: str, callback: Callable[[Event], None]) -> None:
        """Désabonne un listener."""
        with self._lock:
            if kind in self._listeners:
                self._listeners[kind] = [
                    cb for cb in self._listeners[kind] if cb is not callback
                ]

    def get_events(
        self,
        kind: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Event]:
        """
        Retourne les événements collectés.

        :param kind: Filtre par type (optionnel).
        :param since: Ne retourner que les événements après cette date.
        :returns: Liste d'événements.
        """
        with self._lock:
            events = list(self._events)

        if kind:
            events = [e for e in events if e.kind == kind]
        if since:
            events = [e for e in events if e.timestamp >= since]
        return events

    def clear(self) -> None:
        """Efface tous les événements collectés."""
        with self._lock:
            self._events.clear()

    def export_json(self, filepath: str) -> None:
        """
        Exporte tous les événements dans un fichier JSON.

        :param filepath: Chemin du fichier de sortie.
        """
        events = self.get_events()
        data = [e.to_dict() for e in events]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def __len__(self) -> int:
        return len(self._events)

    def __repr__(self) -> str:
        return f"EventBus({len(self._events)} events)"
