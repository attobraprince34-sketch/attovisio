"""
attovisio.security_auditor
~~~~~~~~~~~~~~~~~~~~~~~~~~
Détection d'accès sensibles : fichiers de mots de passe, clés privées,
variables d'environnement critiques, exécution de commandes système, etc.
"""

import os
import re
import subprocess
import threading
from datetime import datetime
from typing import Callable, List, Optional

from .events import Event, EventBus

# ------------------------------------------------------------------
# Règles de détection des chemins sensibles
# ------------------------------------------------------------------

SENSITIVE_PATH_PATTERNS = [
    (r"/etc/passwd",           "Fichier de comptes Unix"),
    (r"/etc/shadow",           "Fichier de mots de passe chiffrés"),
    (r"/etc/sudoers",          "Configuration sudo"),
    (r"\.ssh/",                "Répertoire SSH (clés privées)"),
    (r"\.aws/credentials",     "Credentials AWS"),
    (r"\.env$",                "Fichier .env (variables d'environnement)"),
    (r"\.pem$",                "Certificat / clé privée PEM"),
    (r"\.key$",                "Fichier clé privée"),
    (r"\.p12$",                "Certificat PKCS12"),
    (r"id_rsa",                "Clé privée RSA"),
    (r"id_ed25519",            "Clé privée ED25519"),
    (r"secrets\.",             "Fichier de secrets"),
    (r"password",              "Fichier contenant 'password'"),
    (r"token",                 "Fichier contenant 'token'"),
    (r"/proc/self/mem",        "Mémoire du processus"),
    (r"\.htpasswd",            "Fichier de mots de passe HTTP"),
    (r"database\.yml",         "Configuration base de données"),
    (r"config\.json",          "Fichier de configuration"),
    (r"settings\.py",          "Paramètres Django / projet"),
]

SENSITIVE_ENV_VARS = {
    "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID",
    "DATABASE_URL", "DB_PASSWORD", "SECRET_KEY",
    "API_KEY", "GITHUB_TOKEN", "SLACK_TOKEN",
    "PRIVATE_KEY", "PASSWORD", "JWT_SECRET",
}

SENSITIVE_COMMANDS = [
    (r"\bsudo\b",              "Élévation de privilèges"),
    (r"\bchmod\b.*777",        "Permissions trop permissives"),
    (r"\brm\s+-rf\b",          "Suppression récursive forcée"),
    (r"\bcurl\b.*password",    "Transmission de mot de passe via curl"),
    (r"\bwget\b.*password",    "Transmission de mot de passe via wget"),
    (r"\bnc\b|\bnetcat\b",     "Netcat (shell inverse possible)"),
    (r"base64.*-d",            "Décodage base64 (obfuscation possible)"),
    (r"python.*-c",            "Exécution de code Python inline"),
    (r"\beval\b",              "Évaluation de code dynamique"),
]


class SecurityAuditor:
    """
    Analyse les événements du bus et lève des alertes de sécurité.

    L'auditeur s'abonne automatiquement aux événements ``file_open``,
    ``network_connect`` et ``subprocess_exec`` pour détecter les accès
    suspects.

    ::

        from attovisio import SecurityAuditor, IOObserver

        auditor = SecurityAuditor(verbose=True)
        auditor.start()

        observer = IOObserver(intercept=True).start()
        with open("/etc/passwd") as f:   # → alerte levée !
            pass

        auditor.stop()
        print(auditor.get_alerts())

    """

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        verbose: bool = False,
        on_alert: Optional[Callable[[dict], None]] = None,
    ):
        """
        :param bus: Bus d'événements partagé.
        :param verbose: Affiche les alertes dans la console.
        :param on_alert: Callback appelé à chaque alerte (ex. envoi email).
        """
        self.bus = bus or EventBus.get_global()
        self.verbose = verbose
        self.on_alert = on_alert
        self._alerts: List[dict] = []
        self._lock = threading.Lock()

    def start(self) -> "SecurityAuditor":
        """S'abonne aux événements du bus."""
        self.bus.subscribe("file_open", self._check_file)
        self.bus.subscribe("file_write", self._check_file)
        self.bus.subscribe("network_connect", self._check_network)
        self.bus.subscribe("subprocess_exec", self._check_subprocess)
        self.bus.subscribe("env_access", self._check_env)
        return self

    def stop(self) -> "SecurityAuditor":
        """Se désabonne des événements."""
        self.bus.unsubscribe("file_open", self._check_file)
        self.bus.unsubscribe("file_write", self._check_file)
        self.bus.unsubscribe("network_connect", self._check_network)
        self.bus.unsubscribe("subprocess_exec", self._check_subprocess)
        self.bus.unsubscribe("env_access", self._check_env)
        return self

    def __enter__(self) -> "SecurityAuditor":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Analyseurs par type d'événement
    # ------------------------------------------------------------------

    def _check_file(self, event: Event) -> None:
        """Vérifie si un accès fichier touche un chemin sensible."""
        path = event.data.get("path", "") or event.data.get("absolute_path", "")
        for pattern, description in SENSITIVE_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                self._raise_alert(
                    severity="HIGH",
                    category="sensitive_file_access",
                    message=f"Accès fichier sensible : {path}",
                    detail=description,
                    related_event=event,
                )
                break

    def _check_network(self, event: Event) -> None:
        """Vérifie les connexions réseau suspectes."""
        remote = event.data.get("remote_address", "")
        host = event.data.get("remote_host", "")

        # Connexions sortantes vers ports suspects
        suspicious_ports = {22: "SSH", 23: "Telnet", 3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis"}
        for port, name in suspicious_ports.items():
            if f":{port}" in str(remote):
                self._raise_alert(
                    severity="MEDIUM",
                    category="suspicious_network",
                    message=f"Connexion vers port {name} ({port}) : {remote}",
                    detail=f"Service exposé : {name}",
                    related_event=event,
                )

    def _check_subprocess(self, event: Event) -> None:
        """Vérifie les commandes système exécutées."""
        cmd = event.data.get("command", "")
        for pattern, description in SENSITIVE_COMMANDS:
            if re.search(pattern, str(cmd), re.IGNORECASE):
                self._raise_alert(
                    severity="HIGH",
                    category="dangerous_command",
                    message=f"Commande suspecte : {cmd}",
                    detail=description,
                    related_event=event,
                )

    def _check_env(self, event: Event) -> None:
        """Vérifie l'accès aux variables d'environnement sensibles."""
        var_name = event.data.get("variable", "").upper()
        for sensitive in SENSITIVE_ENV_VARS:
            if sensitive in var_name or var_name in sensitive:
                self._raise_alert(
                    severity="MEDIUM",
                    category="sensitive_env_access",
                    message=f"Accès variable d'environnement sensible : {var_name}",
                    detail="Variable pouvant contenir des secrets",
                    related_event=event,
                )
                break

    # ------------------------------------------------------------------
    # Scanneurs manuels
    # ------------------------------------------------------------------

    def scan_environment(self) -> List[dict]:
        """
        Scanne les variables d'environnement actuelles à la recherche de secrets.

        :returns: Liste d'alertes pour les variables suspectes.
        """
        alerts = []
        for var, value in os.environ.items():
            if any(s in var.upper() for s in SENSITIVE_ENV_VARS):
                alert = self._raise_alert(
                    severity="INFO",
                    category="env_secret_detected",
                    message=f"Variable d'environnement sensible présente : {var}",
                    detail="La valeur est masquée pour la sécurité",
                    related_event=None,
                )
                alerts.append(alert)
        return alerts

    def scan_directory(self, path: str) -> List[dict]:
        """
        Scanne un répertoire à la recherche de fichiers sensibles.

        :param path: Chemin du répertoire à analyser.
        :returns: Liste d'alertes pour les fichiers suspects trouvés.
        """
        alerts = []
        for root, dirs, files in os.walk(path):
            # Ignorer les dossiers cachés et node_modules
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
            for fname in files:
                filepath = os.path.join(root, fname)
                for pattern, description in SENSITIVE_PATH_PATTERNS:
                    if re.search(pattern, filepath, re.IGNORECASE):
                        alert = self._raise_alert(
                            severity="HIGH",
                            category="sensitive_file_found",
                            message=f"Fichier sensible trouvé : {filepath}",
                            detail=description,
                            related_event=None,
                        )
                        alerts.append(alert)
                        break
        return alerts

    # ------------------------------------------------------------------
    # Gestion des alertes
    # ------------------------------------------------------------------

    def _raise_alert(
        self,
        severity: str,
        category: str,
        message: str,
        detail: str,
        related_event: Optional[Event],
    ) -> dict:
        """Crée et enregistre une alerte de sécurité."""
        alert = {
            "severity": severity,
            "category": category,
            "message": message,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
            "related_event_kind": related_event.kind if related_event else None,
        }
        with self._lock:
            self._alerts.append(alert)

        alert_event = Event(kind="security_alert", data=alert)
        self.bus.emit(alert_event)

        if self.verbose:
            icons = {"HIGH": "🚨", "MEDIUM": "⚠️", "INFO": "ℹ️", "LOW": "💡"}
            icon = icons.get(severity, "⚠️")
            print(f"{icon} [SÉCURITÉ/{severity}] {message}")
            print(f"   → {detail}")

        if self.on_alert:
            try:
                self.on_alert(alert)
            except Exception:
                pass

        return alert

    def get_alerts(self, severity: Optional[str] = None) -> List[dict]:
        """
        Retourne les alertes collectées.

        :param severity: Filtre par sévérité (``"HIGH"``, ``"MEDIUM"``, ``"INFO"``).
        :returns: Liste d'alertes.
        """
        with self._lock:
            alerts = list(self._alerts)
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        return alerts

    def report(self) -> str:
        """Génère un rapport textuel des alertes."""
        alerts = self.get_alerts()
        if not alerts:
            return "✅ Aucune alerte de sécurité détectée."

        lines = [f"🔐 RAPPORT DE SÉCURITÉ — {len(alerts)} alerte(s)", "=" * 50]
        for a in alerts:
            lines.append(f"\n[{a['severity']}] {a['message']}")
            lines.append(f"  Catégorie : {a['category']}")
            lines.append(f"  Détail    : {a['detail']}")
            lines.append(f"  Date      : {a['timestamp']}")
        return "\n".join(lines)
