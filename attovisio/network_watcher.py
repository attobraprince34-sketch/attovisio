"""
attovisio.network_watcher
~~~~~~~~~~~~~~~~~~~~~~~~~
Capture des connexions réseau ouvertes par le processus courant.
Rend visible toute communication réseau de votre programme.
"""

import socket
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from contextlib import contextmanager

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from .events import Event, EventBus


class NetworkWatcher:
    """
    Surveille les connexions réseau du processus Python courant.

    Utilise ``psutil`` pour scanner périodiquement les sockets ouverts
    et émet des événements à chaque nouvelle connexion ou déconnexion.

    ::

        from attovisio import NetworkWatcher

        watcher = NetworkWatcher(verbose=True)
        watcher.start()

        import requests
        requests.get("https://example.com")

        watcher.stop()
        print(watcher.get_connections())

    """

    def __init__(
        self,
        interval: float = 0.5,
        bus: Optional[EventBus] = None,
        verbose: bool = False,
    ):
        """
        :param interval: Intervalle de scan en secondes.
        :param bus: Bus d'événements partagé.
        :param verbose: Affiche chaque connexion dans la console.
        """
        if not _HAS_PSUTIL:
            raise ImportError(
                "psutil est requis pour NetworkWatcher.\n"
                "Installez-le avec : pip install psutil"
            )
        self.interval = interval
        self.bus = bus or EventBus.get_global()
        self.verbose = verbose

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._known_conns: Set[str] = set()
        self._all_connections: List[dict] = []
        self._process = psutil.Process()

    def start(self) -> "NetworkWatcher":
        """Démarre la surveillance réseau."""
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="attovisio-network"
        )
        self._thread.start()
        return self

    def stop(self) -> "NetworkWatcher":
        """Arrête la surveillance réseau."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval * 2)
        return self

    def __enter__(self) -> "NetworkWatcher":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Boucle de surveillance
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            try:
                self._scan()
            except Exception:
                pass
            time.sleep(self.interval)

    def _scan(self) -> None:
        """Scanne les connexions actives et émet des événements pour les nouvelles."""
        try:
            connections = self._process.net_connections(kind="all")
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            return

        current_keys: Set[str] = set()

        for conn in connections:
            key = self._conn_key(conn)
            current_keys.add(key)

            if key not in self._known_conns:
                # Nouvelle connexion détectée
                info = self._conn_to_dict(conn)
                self._all_connections.append(info)
                self._known_conns.add(key)

                event = Event(kind="network_connect", data=info)
                self.bus.emit(event)

                if self.verbose:
                    ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
                    laddr = info.get("local_address", "?")
                    raddr = info.get("remote_address", "?")
                    proto = info.get("protocol", "?")
                    status = info.get("status", "?")
                    print(f"🌐 [{ts}] CONNEXION {proto} {laddr} → {raddr}  [{status}]")

        # Connexions fermées
        closed = self._known_conns - current_keys
        for key in closed:
            self._known_conns.discard(key)
            event = Event(kind="network_disconnect", data={"connection_key": key})
            self.bus.emit(event)
            if self.verbose:
                ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
                print(f"🔌 [{ts}] DÉCONNEXION {key}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _conn_key(conn) -> str:
        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "-"
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
        return f"{conn.type}:{laddr}↔{raddr}"

    @staticmethod
    def _conn_to_dict(conn) -> dict:
        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None

        # Résolution DNS optionnelle (non bloquante)
        remote_host = None
        if conn.raddr:
            try:
                remote_host = socket.gethostbyaddr(conn.raddr.ip)[0]
            except Exception:
                remote_host = conn.raddr.ip

        proto_map = {
            1: "TCP", 2: "UDP", 3: "RAW",
            socket.SOCK_STREAM: "TCP",
            socket.SOCK_DGRAM: "UDP",
        }
        proto = proto_map.get(conn.type, str(conn.type))

        return {
            "local_address": laddr,
            "remote_address": raddr,
            "remote_host": remote_host,
            "protocol": proto,
            "status": conn.status,
            "family": str(conn.family),
            "timestamp": datetime.now().isoformat(),
        }

    def get_connections(self) -> List[dict]:
        """Retourne toutes les connexions détectées depuis le démarrage."""
        return list(self._all_connections)

    def summary(self) -> dict:
        """Retourne un résumé des connexions observées."""
        conns = self._all_connections
        if not conns:
            return {"total": 0}

        hosts = list({c.get("remote_host") or c.get("remote_address") for c in conns if c.get("remote_address")})
        protos = {}
        for c in conns:
            p = c.get("protocol", "?")
            protos[p] = protos.get(p, 0) + 1

        return {
            "total": len(conns),
            "unique_remote_hosts": hosts,
            "protocols": protos,
        }


# ------------------------------------------------------------------
# Patch socket (mode avancé)
# ------------------------------------------------------------------

def patch_socket(bus: Optional[EventBus] = None, verbose: bool = False) -> None:
    """
    Patche ``socket.socket.connect`` pour capturer *toutes* les connexions,
    y compris celles initiées avant le démarrage du ``NetworkWatcher``.

    .. warning::
        Modifie ``socket.socket.connect`` globalement.  Utilisez
        ``unpatch_socket()`` pour annuler.

    :param bus: Bus d'événements partagé.
    :param verbose: Affiche les connexions dans la console.
    """
    bus = bus or EventBus.get_global()
    _orig_connect = socket.socket.connect

    def _instrumented_connect(self_sock, address):
        result = _orig_connect(self_sock, address)
        host = address[0] if isinstance(address, tuple) else str(address)
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        event = Event(
            kind="network_connect",
            data={
                "remote_address": f"{host}:{port}" if port else host,
                "remote_host": host,
                "protocol": "TCP",
                "status": "ESTABLISHED",
                "source": "socket_patch",
            },
        )
        bus.emit(event)
        if verbose:
            ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            print(f"🌐 [{ts}] CONNECT → {host}:{port}")
        return result

    socket.socket.connect = _instrumented_connect


def unpatch_socket() -> None:
    """Restaure ``socket.socket.connect`` original."""
    if hasattr(socket.socket, "_orig_connect"):
        socket.socket.connect = socket.socket._orig_connect
