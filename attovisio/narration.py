"""
attovisio.narration
~~~~~~~~~~~~~~~~~~~
Transforme les événements techniques en phrases lisibles par un humain.
Rend la compréhension accessible même aux débutants.
"""

import json
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .events import Event, EventBus


# ------------------------------------------------------------------
# Gabarits de narration par type d'événement
# ------------------------------------------------------------------

DEFAULT_TEMPLATES: Dict[str, Callable[[dict], str]] = {

    "function_call": lambda d: (
        f"La fonction « {d.get('function', '?')} » a été appelée"
        + (f" avec les arguments {_fmt_args(d.get('arguments', {}))}" if d.get("arguments") else "")
        + f" [profondeur : {d.get('depth', 0)}]."
    ),

    "function_return": lambda d: (
        f"La fonction « {d.get('function', '?')} » a terminé"
        + (f" et a renvoyé {d.get('return_value', 'rien')}" if d.get("return_value") else "")
        + f" en {d.get('duration_ms', 0)} ms."
    ),

    "exception": lambda d: (
        f"⚠️  Une erreur de type « {d.get('exception_type', '?')} » est survenue"
        f" dans « {d.get('function', '?')} » : {d.get('exception_message', '')}."
    ),

    "file_open": lambda d: (
        f"Le fichier « {d.get('filename', d.get('path', '?'))} » a été ouvert"
        + (f" en mode {d.get('mode', 'lecture')}" if d.get("mode") else "")
        + "."
    ),

    "file_write": lambda d: (
        f"Des données ont été écrites dans « {d.get('filename', d.get('path', '?'))} »"
        + (f" ({d.get('size_bytes', 0)} octets)" if d.get("size_bytes") else "")
        + "."
    ),

    "file_read": lambda d: (
        f"Des données ont été lues depuis « {d.get('filename', d.get('path', '?'))} »"
        + (f" ({d.get('size_bytes', 0)} octets)" if d.get("size_bytes") else "")
        + "."
    ),

    "file_delete": lambda d: (
        f"Le fichier « {d.get('filename', d.get('path', '?'))} » a été supprimé."
    ),

    "file_rename": lambda d: (
        f"Le fichier « {d.get('path', '?')} » a été renommé"
        f" en « {d.get('destination', '?')} »."
    ),

    "file_close": lambda d: (
        f"Le fichier « {d.get('filename', d.get('path', '?'))} » a été fermé."
    ),

    "network_connect": lambda d: (
        f"Une connexion réseau a été établie"
        + (f" vers {d.get('remote_host') or d.get('remote_address', '?')}" if d.get("remote_address") else "")
        + (f" via {d.get('protocol', 'TCP')}" if d.get("protocol") else "")
        + "."
    ),

    "network_disconnect": lambda d: (
        f"Une connexion réseau a été fermée."
    ),

    "system_metrics": lambda d: (
        f"Ressources système : CPU processus {d.get('process_cpu_percent', 0)}%, "
        f"RAM {d.get('process_memory_rss_mb', 0)} MB, "
        f"{d.get('process_threads', 0)} thread(s) actif(s)."
    ),

    "function_profile": lambda d: (
        f"Profil de « {d.get('function', '?')} » : "
        + _fmt_summary(d.get("resources", {}))
    ),

    "security_alert": lambda d: (
        f"🚨 ALERTE SÉCURITÉ [{d.get('severity', '?')}] : {d.get('message', '')}. "
        f"Détail : {d.get('detail', '')}."
    ),

    "block_profile": lambda d: (
        f"Bloc « {d.get('label', '?')} » terminé. "
        + _fmt_summary(d.get("resources", {}))
    ),

    "subprocess_exec": lambda d: (
        f"Une commande système a été exécutée : « {d.get('command', '?')} »."
    ),
}


def _fmt_args(args: dict) -> str:
    """Formate les arguments de façon lisible."""
    if not args:
        return ""
    parts = [f"{k}={v}" for k, v in list(args.items())[:4]]
    return "{" + ", ".join(parts) + ("…" if len(args) > 4 else "") + "}"


def _fmt_summary(summary: dict) -> str:
    """Formate un résumé de ressources."""
    if not summary:
        return ""
    parts = []
    if "cpu_percent" in summary:
        parts.append(f"CPU moy. {summary['cpu_percent'].get('avg', 0)}%")
    if "memory_rss_mb" in summary:
        parts.append(f"RAM max {summary['memory_rss_mb'].get('max', 0)} MB")
    if "duration_s" in summary:
        parts.append(f"durée {summary['duration_s']} s")
    return ", ".join(parts) + "." if parts else ""


# ------------------------------------------------------------------
# Classe Narrator
# ------------------------------------------------------------------

class Narrator:
    """
    Transforme les événements AttoVisio en texte narratif humain.

    Vous pouvez personnaliser les gabarits ou en ajouter de nouveaux
    pour des types d'événements personnalisés.

    ::

        from attovisio import Narrator, EventBus

        bus = EventBus.get_global()
        narrator = Narrator(bus=bus)

        # Après avoir collecté des événements...
        story = narrator.tell()
        print(story)

    Personnalisation ::

        narrator.add_template(
            "my_event",
            lambda d: f"Mon événement personnalisé : {d.get('info')}"
        )

    """

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        language: str = "fr",
        verbose: bool = False,
    ):
        """
        :param bus: Bus d'événements partagé.
        :param language: Langue de narration (actuellement ``"fr"`` uniquement).
        :param verbose: Affiche chaque narration en temps réel.
        """
        self.bus = bus or EventBus.get_global()
        self.language = language
        self.verbose = verbose
        self._templates: Dict[str, Callable[[dict], str]] = dict(DEFAULT_TEMPLATES)

        if verbose:
            self.bus.subscribe("*", self._live_narrate)

    # ------------------------------------------------------------------
    # Personnalisation des gabarits
    # ------------------------------------------------------------------

    def add_template(self, event_kind: str, template: Callable[[dict], str]) -> None:
        """
        Ajoute ou remplace un gabarit de narration.

        :param event_kind: Type d'événement (ex. ``"my_event"``).
        :param template: Fonction ``(data_dict) -> str``.
        """
        self._templates[event_kind] = template

    def remove_template(self, event_kind: str) -> None:
        """Supprime un gabarit de narration."""
        self._templates.pop(event_kind, None)

    # ------------------------------------------------------------------
    # Narration
    # ------------------------------------------------------------------

    def narrate(self, event: Event) -> str:
        """
        Traduit un événement en phrase lisible.

        :param event: L'événement à narrer.
        :returns: Phrase descriptive.
        """
        template = self._templates.get(event.kind)
        if template:
            try:
                sentence = template(event.data)
            except Exception as exc:
                sentence = f"[Erreur de narration pour '{event.kind}': {exc}]"
        else:
            sentence = f"Événement « {event.kind} » : {json.dumps(event.data, ensure_ascii=False)[:100]}."

        ts = event.timestamp.strftime("%H:%M:%S")
        return f"[{ts}] {sentence}"

    def tell(
        self,
        events: Optional[List[Event]] = None,
        kinds: Optional[List[str]] = None,
    ) -> str:
        """
        Génère un récit complet de tous les événements collectés.

        :param events: Liste d'événements (utilise le bus si None).
        :param kinds: Filtre par types d'événements.
        :returns: Texte narratif multi-lignes.
        """
        if events is None:
            events = self.bus.get_events()
        if kinds:
            events = [e for e in events if e.kind in kinds]

        if not events:
            return "Aucun événement à narrer pour le moment."

        lines = [
            "📖 RÉCIT D'EXÉCUTION",
            "=" * 50,
            f"  {len(events)} événement(s) capturé(s)",
            "=" * 50,
            "",
        ]
        for event in events:
            lines.append(self.narrate(event))

        lines.append("")
        lines.append("=" * 50)
        lines.append("Fin du récit.")
        return "\n".join(lines)

    def tell_html(self, events: Optional[List[Event]] = None) -> str:
        """
        Génère un récit au format HTML avec coloration par type d'événement.

        :param events: Liste d'événements (utilise le bus si None).
        :returns: Fragment HTML.
        """
        if events is None:
            events = self.bus.get_events()

        color_map = {
            "function_call": "#2196F3",
            "function_return": "#4CAF50",
            "exception": "#F44336",
            "file_open": "#FF9800",
            "file_write": "#FF5722",
            "network_connect": "#9C27B0",
            "security_alert": "#F44336",
            "system_metrics": "#607D8B",
        }

        rows = []
        for event in events:
            color = color_map.get(event.kind, "#333333")
            sentence = self.narrate(event)
            rows.append(
                f'<tr><td style="color:{color};padding:4px 8px;">{sentence}</td></tr>'
            )

        return (
            "<table style='font-family:monospace;font-size:13px;border-collapse:collapse;width:100%'>"
            + "\n".join(rows)
            + "</table>"
        )

    def export_txt(self, filepath: str, **kwargs) -> None:
        """
        Exporte le récit dans un fichier texte.

        :param filepath: Chemin du fichier de sortie.
        """
        story = self.tell(**kwargs)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(story)

    # ------------------------------------------------------------------
    # Mode temps réel
    # ------------------------------------------------------------------

    def _live_narrate(self, event: Event) -> None:
        """Callback pour la narration en temps réel."""
        print(self.narrate(event))
