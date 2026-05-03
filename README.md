# 🔭 AttoVisio

> **Rend visibles les actions invisibles en informatique.**

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/attobraprince/attovisio/actions/workflows/ci.yml/badge.svg)](https://github.com/attobraprince/attovisio/actions)
[![PyPI](https://img.shields.io/pypi/v/attovisio.svg)](https://pypi.org/project/attovisio/)

AttoVisio est une bibliothèque Python qui vous permet d'**observer, tracer et comprendre** ce qui se passe réellement dans votre programme : appels de fonctions, accès fichiers, connexions réseau, consommation de ressources et risques de sécurité — le tout transformé en **langage naturel** et en **rapports HTML interactifs**.

---

## ✨ Fonctionnalités

| Module | Ce qu'il observe |
|--------|-----------------|
| `Tracer` | Appels de fonctions, valeurs de retour, exceptions, durées |
| `SystemMonitor` | CPU, mémoire RAM, threads, fichiers ouverts |
| `IOObserver` | Ouvertures, lectures, écritures, suppressions de fichiers |
| `NetworkWatcher` | Connexions TCP/UDP, hôtes distants |
| `SecurityAuditor` | Accès à fichiers sensibles, variables d'environnement critiques |
| `Narrator` | Traduction des événements en phrases lisibles en français |
| `Visualizer` | Timeline HTML, flamegraph, tableau de bord interactif |

---

## 📦 Installation

```bash
# Installation minimale (sans dépendances)
pip install attovisio

# Installation complète (avec surveillance CPU/réseau)
pip install attovisio[full]

# Pour les développeurs
pip install attovisio[dev]
```

**Aucune dépendance obligatoire !** AttoVisio fonctionne avec la bibliothèque standard Python.
`psutil` est optionnel (uniquement pour `SystemMonitor` et `NetworkWatcher`).

---

## 🚀 Quick Start — Démarrage rapide

### Exemple minimal (30 secondes)

```python
from attovisio import Tracer

@Tracer.trace
def demo(x):
    return x * 2

demo(5)
```

C'est tout ! AttoVisio capture silencieusement l'appel en arrière-plan.

### Voir ce qui s'est passé

```python
from attovisio import Tracer, Narrator, EventBus

@Tracer.trace
def addition(a, b):
    return a + b

@Tracer.trace
def division(a, b):
    return a / b

addition(10, 3)
division(8, 2)

# Raconter ce qui s'est passé
from attovisio import tell
print(tell())
```

**Sortie :**
```
📖 RÉCIT D'EXÉCUTION
==================================================
  4 événement(s) capturé(s)
==================================================

[14:32:01] La fonction « addition » a été appelée avec les arguments {'a': '10', 'b': '3'} [profondeur : 0].
[14:32:01] La fonction « addition » a terminé et a renvoyé 13 en 0.021 ms.
[14:32:01] La fonction « division » a été appelée avec les arguments {'a': '8', 'b': '2'} [profondeur : 0].
[14:32:01] La fonction « division » a terminé et a renvoyé 4.0 en 0.012 ms.
```

### Générer un rapport HTML

```python
from attovisio import Visualizer

viz = Visualizer()
viz.timeline("mon_rapport.html")        # Timeline filtrabl
viz.dashboard("tableau_bord.html")      # Tableau de bord complet
viz.flamegraph("performances.html")     # Graphe des durées
```

Ouvrez les fichiers HTML dans votre navigateur — aucune installation supplémentaire nécessaire !

---

## 📚 Tutoriel complet

### 1. Tracer des fonctions

```python
from attovisio import Tracer

# Méthode 1 : décorateur de classe (le plus simple)
@Tracer.trace
def ma_fonction(x):
    return x ** 2

# Méthode 2 : instance personnalisée
tracer = Tracer(verbose=True)  # affiche chaque événement en temps réel

@tracer.watch
def autre_fonction(a, b):
    return a + b

# Méthode 3 : surveiller les ressources pendant l'exécution
@tracer.watch          # combine traçage + profiling
def traitement_lourd():
    return sum(range(1_000_000))
```

### 2. Observer les fichiers

```python
from attovisio import IOObserver

# Mode manuel (journaliser explicitement)
observer = IOObserver(verbose=True)
observer.log_open("data.csv", mode="r")
observer.log_read("data.csv", size_bytes=2048)
observer.log_write("résultat.json", size_bytes=512)

# Mode automatique (intercepte tous les open())
with IOObserver(intercept=True, verbose=True):
    with open("mon_fichier.txt", "w") as f:
        f.write("bonjour")
    # → AttoVisio capture automatiquement l'ouverture et l'écriture
```

### 3. Surveiller les ressources système

```python
from attovisio import Monitor
import time

# Comme gestionnaire de contexte
with Monitor(interval=0.5) as m:
    # Votre code ici
    time.sleep(2)

print(m.summary())
# {'samples': 4, 'cpu_percent': {'min': 0.1, 'max': 12.3, 'avg': 2.1},
#  'memory_rss_mb': {'min': 45.2, 'max': 48.7, 'avg': 46.3}, ...}

# Ou comme décorateur
monitor = Monitor()

@monitor.profile
def calcul_intensif():
    return [i**2 for i in range(500_000)]
```

### 4. Audit de sécurité

```python
from attovisio import SecurityAuditor, IOObserver

# Démarrer l'audit
auditor = SecurityAuditor(verbose=True)
auditor.start()

# Scanner un répertoire
alertes = auditor.scan_directory("/home/user/projet")

# Vérifier les variables d'environnement
auditor.scan_environment()

# Lire le rapport
print(auditor.report())
# 🔐 RAPPORT DE SÉCURITÉ — 2 alerte(s)
# [HIGH] Accès fichier sensible : /home/user/.ssh/id_rsa
#   Catégorie : sensitive_file_access
#   Détail    : Répertoire SSH (clés privées)

auditor.stop()
```

### 5. Narration

```python
from attovisio import Narrator

narrator = Narrator()

# Récit complet
print(narrator.tell())

# Récit filtré (seulement les erreurs)
print(narrator.tell(kinds=["exception", "security_alert"]))

# Export texte
narrator.export_txt("rapport.txt")

# Export HTML coloré
html = narrator.tell_html()

# Personnaliser les messages
narrator.add_template(
    "mon_event",
    lambda d: f"Action personnalisée : {d.get('info', '?')}"
)
```

### 6. Export des données

```python
from attovisio import EventBus, export_json

# Export JSON de tous les événements
export_json("tous_les_événements.json")

# Accès direct au bus
bus = EventBus.get_global()
events = bus.get_events()                     # tous
calls  = bus.get_events(kind="function_call") # filtrés
bus.clear()                                   # réinitialiser
```

---

## 🔬 Utilisation avancée

### Plugins personnalisés

AttoVisio est conçu pour être extensible. Vous pouvez créer vos propres observateurs :

```python
from attovisio.events import Event, EventBus

class MonObservateur:
    """Observateur personnalisé pour les requêtes SQL."""

    def __init__(self, bus=None):
        self.bus = bus or EventBus.get_global()

    def log_requête(self, sql: str, durée_ms: float):
        event = Event(
            kind="sql_query",
            data={"sql": sql[:100], "duration_ms": durée_ms}
        )
        self.bus.emit(event)
```

### Hooks de narration

```python
narrator = Narrator()

# Ajouter un gabarit pour votre événement personnalisé
narrator.add_template(
    "sql_query",
    lambda d: f"Requête SQL exécutée en {d['duration_ms']} ms : {d['sql']}"
)
```

### Callbacks d'alertes sécurité

```python
import smtplib

def envoyer_alerte_email(alert: dict):
    """Envoie un email à chaque alerte de sécurité."""
    if alert["severity"] == "HIGH":
        print(f"🚨 Email envoyé pour : {alert['message']}")

auditor = SecurityAuditor(on_alert=envoyer_alerte_email)
```

### Intégration dans un projet Django

```python
# middleware.py
from attovisio import Tracer, SecurityAuditor, EventBus

tracer = Tracer()
auditor = SecurityAuditor().start()

class AttoVisioMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        view_func = tracer.watch(view_func)
        return None
```

---

## 🎓 Cas d'usage

### Pédagogie
AttoVisio est idéal pour **enseigner la programmation** :
- Montrer aux étudiants ce que fait vraiment leur code
- Rendre visible la récursivité, la complexité algorithmique
- Comprendre l'ordre d'exécution des fonctions

### Débogage
- Comprendre pourquoi une fonction est appelée avec de mauvais arguments
- Tracer l'origine d'une exception dans une chaîne d'appels
- Mesurer les durées pour identifier les goulots d'étranglement

### Sécurité
- Auditer un code tiers avant de l'exécuter en production
- Détecter les accès non autorisés à des fichiers sensibles
- Surveiller les connexions réseau inattendues

### Éco-conception
- Mesurer la consommation CPU/RAM de votre programme
- Identifier les parties du code les plus coûteuses en ressources
- Optimiser votre empreinte numérique

---

## 🗂️ Structure du projet

```
AttoVisio/
├── attovisio/
│   ├── __init__.py          # API publique
│   ├── events.py            # Event et EventBus (cœur du système)
│   ├── tracer.py            # Capture des appels de fonctions
│   ├── system_monitor.py    # Surveillance CPU / RAM / threads
│   ├── io_observer.py       # Journalisation des accès fichiers
│   ├── network_watcher.py   # Capture des connexions réseau
│   ├── security_auditor.py  # Détection d'accès sensibles
│   ├── visualization.py     # Rapports HTML (timeline, dashboard)
│   └── narration.py         # Traduction en langage naturel
├── tests/
│   └── test_attovisio.py    # 30+ tests unitaires
├── examples/
│   ├── demo_basic.py        # Démo minimale
│   ├── demo_advanced.py     # Démo complète
│   └── tutoriel_jupyter.ipynb
├── .github/
│   └── workflows/
│       └── ci.yml           # CI/CD GitHub Actions
├── setup.py
├── pyproject.toml
└── README.md
```

---

## 🧪 Lancer les tests

```bash
# Installer les dépendances de développement
pip install attovisio[dev]

# Lancer tous les tests
pytest tests/ -v

# Avec couverture de code
pytest tests/ -v --cov=attovisio --cov-report=html
```

---

## 🤝 Contribuer

Les contributions sont les bienvenues !

1. **Forkez** le dépôt
2. Créez une branche : `git checkout -b feature/mon-module`
3. Committez : `git commit -m "feat: ajouter MonModule"`
4. Poussez : `git push origin feature/mon-module`
5. Ouvrez une **Pull Request**

### Ajouter un nouveau module observateur

Un module AttoVisio suit ce patron minimal :

```python
from attovisio.events import Event, EventBus

class MonObservateur:
    def __init__(self, bus=None, verbose=False):
        self.bus = bus or EventBus.get_global()
        self.verbose = verbose

    def start(self):
        # Démarrer l'observation
        return self

    def stop(self):
        # Arrêter proprement
        return self

    def __enter__(self): return self.start()
    def __exit__(self, *_): self.stop()
```

---

## 📄 Licence

Distribué sous licence **MIT**. Voir [LICENSE](LICENSE) pour plus de détails.

```
MIT License

Copyright (c) 2024 Attobra Prince

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 👨‍💻 Auteur

**Attobra Prince** — Développeur Full Stack Python/Django & React, Abidjan, Côte d'Ivoire.

- GitHub : [@attobraprince](https://github.com/attobraprince)
- TikTok : [@prince__net](https://www.tiktok.com/@prince__net?is_from_webapp=1&sender_device=pc)

---

*"Rendre visible l'invisible, c'est le premier pas vers la maîtrise."*
