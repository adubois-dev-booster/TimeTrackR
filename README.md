# TimeTrackR

Application de suivi de temps pour Windows, avec icône dans la barre des tâches, détection d'inactivité et rappels paramétrables.

## Fonctionnalités

- Icône système (tray) avec menu contextuel
- Fenêtre principale avec timer HH:MM:SS
- Gestion de tâches et projets
- Reprise automatique de la dernière session au démarrage
- Détection d'inactivité clavier/souris (via `GetLastInputInfo`)
- Rappels paramétrables (inactivité et durée de tâche)
- Notifications Windows natives
- Persistance SQLite dans `%APPDATA%/TimeTracker/`

## Prérequis

- Windows 10 ou Windows 11
- Python 3.11+

## Installation

```bash
# Cloner le dépôt
git clone https://github.com/adubois-dev-booster/TimeTrackR.git
cd TimeTrackR

# Créer et activer l'environnement virtuel
python -m venv venv
venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

## Lancement

```bash
python time_tracker/main.py
```

L'application démarre dans la barre des tâches (system tray). Clic gauche sur l'icône pour ouvrir la fenêtre principale, clic droit pour le menu.
