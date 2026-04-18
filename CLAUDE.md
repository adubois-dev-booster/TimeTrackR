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

`time_tracker/main.py` : point d'entrée. `TimeTrackRApp` orchestre tous les composants, gère le tray pystray (thread séparé) et la boucle Tkinter (thread principal).

### `time_tracker/core/` — logique métier (pas de Tkinter)

| Fichier | Rôle |
|---|---|
| `database.py` | SQLite dans `%APPDATA%/TimeTracker/timetracker.db`. Tables : `tasks`, `sessions` (avec `is_active` pour détecter les sessions orphelines), `config`. |
| `timer_engine.py` | Thread daemon qui incrémente `_elapsed_seconds` toutes les secondes, appelle `tick_callback`, et sauvegarde en base toutes les 30 s (`AUTOSAVE_INTERVAL`). Toutes les mutations d'état passent par `self._lock`. |
| `task_manager.py` | Façade entre `Database`, `TimerEngine` et l'UI. Gère démarrage/arrêt, reprise au démarrage, et les trois cas d'inactivité (`handle_idle_resume`, `handle_idle_credit_and_resume`, `handle_idle_switch_task`). |
| `idle_detector.py` | Thread daemon, vérifie `GetLastInputInfo` toutes les 30 s, déclenche `on_idle_callback` une seule fois par période d'inactivité. |
| `reminder.py` | Thread daemon, vérifie toutes les 10 s si `elapsed - last_reminder_at >= interval`. Réinitialisé via `reset()` à chaque nouvelle tâche. |

### `time_tracker/ui/` — interface (Tkinter / CustomTkinter)

| Fichier | Rôle |
|---|---|
| `theme.py` | **Source unique** pour toutes les couleurs, tailles de police et dimensions de fenêtre. Modifier ici pour changer l'apparence. |
| `icon.py` | Icône chronomètre dessinée programmatiquement via `create_icon(size)`. |
| `app.py` | Fenêtre CustomTkinter principale. Se cache dans le tray ou quitte selon `close_to_tray` (config DB). Mises à jour depuis d'autres threads via `after()`. |
| `overlay.py` | Fenêtre flottante borderless (toujours au premier plan). Dropdown de tâches avec `_TaskDropdown(tk.Toplevel)`. |
| `notifier.py` | Dialog d'inactivité (`_IdleDialog`) et rappel de durée (`_ReminderPopup`). Le dropdown de la dialog d'inactivité utilise `_SimpleDropdown` (même pattern que l'overlay). |
| `note_window.py` | Fenêtre de note flottante, redimensionnable. |
| `settings_window.py` | `CTkToplevel` modale, singleton. Sauvegarde en base puis émet `<<SettingsChanged>>` sur la fenêtre parente. |

## Règles importantes

- **Thread safety** : tout accès à l'UI Tkinter depuis un thread non-principal doit passer par `app.after(0, callable)`. Le `TimerEngine` appelle `tick_callback` depuis son thread — le callback doit utiliser `after()`.
- **Pas d'asyncio** : l'appli est entièrement synchrone avec des threads `daemon=True`.
- **Fermeture** : `WM_DELETE_WINDOW` → `withdraw()` (cache dans le tray). La vraie fermeture vient du menu tray "Quitter" → `timer.stop()` + `tray.stop()` + `app.destroy()`.
- **Langue** : commentaires en français.

## Git

Les commits suivent le format `préfixe: description` en français.
Préfixes : `feat`, `fix`, `refactor`, `docs`, `chore`.

Pousser sur `https://github.com/adubois-dev-booster/TimeTrackR` après chaque fichier terminé.
