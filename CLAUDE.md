# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Lancer l'application

```bash
# Activer le venv (obligatoire)
venv\Scripts\activate

# Démarrer l'appli
python -m time_tracker.main
```

L'appli démarre dans le system tray Windows. Clic gauche sur l'icône pour ouvrir la fenêtre.

## Installer les dépendances

```bash
venv\Scripts\pip install -r requirements.txt
```

Python 3.12 est installé dans `C:\Users\AdrienDubois\AppData\Local\Programs\Python\Python312\`. Si `python` n'est pas dans le PATH, utiliser le chemin complet.

## Architecture

Tous les fichiers sont dans `time_tracker/` :

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée. Classe `TimeTrackRApp` orchestre tous les composants, gère le tray pystray (thread séparé) et la boucle Tkinter (thread principal). |
| `app.py` | Fenêtre CustomTkinter. Se cache dans le tray (`withdraw`) au lieu de se fermer. Les mises à jour depuis d'autres threads passent obligatoirement par `after()`. |
| `timer_engine.py` | Thread daemon qui incrémente `_elapsed_seconds` toutes les secondes, appelle `tick_callback`, et sauvegarde en base toutes les 30 s (`AUTOSAVE_INTERVAL`). Toutes les mutations d'état passent par `self._lock`. |
| `task_manager.py` | Façade entre `Database`, `TimerEngine` et l'UI. Gère le démarrage/arrêt de tâches et la reprise de session au démarrage. |
| `database.py` | SQLite dans `%APPDATA%/TimeTracker/timetracker.db`. Tables : `tasks`, `sessions` (avec `is_active` pour détecter les sessions orphelines), `config`. |
| `idle_detector.py` | Thread daemon, vérifie `GetLastInputInfo` toutes les 30 s, déclenche `on_idle_callback` une seule fois par période d'inactivité. |
| `reminder.py` | Thread daemon, vérifie toutes les 10 s si `elapsed - last_reminder_at >= interval`. Réinitialisé via `reset()` à chaque nouvelle tâche. |
| `notifier.py` | `InteractableWindowsToaster` (obligatoire pour les boutons). `Toast(text_fields=[title, body], actions=[ToastButton(...)])`. |

## Règles importantes

- **Thread safety** : tout accès à l'UI Tkinter depuis un thread non-principal doit passer par `app.after(0, callable)`. Le `TimerEngine` appelle `tick_callback` depuis son thread — le callback doit utiliser `after()`.
- **Pas d'asyncio** : l'appli est entièrement synchrone avec des threads `daemon=True`.
- **Fermeture** : `WM_DELETE_WINDOW` → `withdraw()` (cache dans le tray). La vraie fermeture vient du menu tray "Quitter" → `timer.stop()` + `tray.stop()` + `app.destroy()`.
- **Langue** : commentaires en français.

## Git

Les commits suivent le format `préfixe: description` en français.
Préfixes : `feat`, `fix`, `refactor`, `docs`, `chore`.

Pousser sur `https://github.com/adubois-dev-booster/TimeTrackR` après chaque fichier terminé.
