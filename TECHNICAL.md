# TimeTrackR — Documentation technique

## Lancer en développement

```bat
venv\Scripts\activate
python -m time_tracker.main
```

## Compiler l'exe

Double-cliquer sur **`build.bat`** (racine du projet), ou en ligne de commande :

```bat
venv\Scripts\activate
pyinstaller TimeTrackR.spec --clean
```

L'exe est produit dans `dist\TimeTrackR.exe`.  
La configuration PyInstaller est dans `TimeTrackR.spec` (one-file, no-console, UPX activé).

> **Base de données séparée** : l'exe utilise `%APPDATA%\TimeTracker_test\` au lieu de `TimeTracker\` pour ne pas mélanger données de prod et de test.

---

## Structure du projet

```
time_tracker/
├── main.py              # Point d'entrée — orchestre tous les composants
├── core/                # Logique métier (aucun import Tkinter)
│   ├── database.py      # Accès SQLite — toutes les requêtes passent ici
│   ├── timer_engine.py  # Thread daemon — tick 1 s, auto-save 30 s
│   ├── task_manager.py  # Façade entre database, timer et UI
│   ├── idle_detector.py # Thread daemon — détecte l'inactivité Windows
│   ├── reminder.py      # Thread daemon — rappel toutes les N minutes
│   └── tag_utils.py     # Parsing et formatage des #tags inline
└── ui/                  # Interface (Tkinter / CustomTkinter)
    ├── theme.py          # Source unique des couleurs, polices, dimensions
    ├── icon.py           # Icônes dessinées via PIL (chronomètre + contrôles)
    ├── app.py            # Fenêtre principale (historique 30 jours)
    ├── overlay.py        # Barre flottante toujours au premier plan
    ├── notifier.py       # Dialogs inactivité (_IdleDialog) et rappel (_ReminderDialog)
    ├── note_window.py    # Fenêtre de note de session
    └── settings_window.py# Paramètres (CTkToplevel modale)
```

---

## Base de données

**Chemin** : `%APPDATA%\TimeTracker\timetracker.db`  
(exe de test : `%APPDATA%\TimeTracker_test\timetracker.db`)

### Tables

#### `tasks`
| Colonne | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | inclut les #tags inline (ex: `"Dev #python"`) |
| project | TEXT | optionnel, défaut `''` |
| created_at | TEXT | ISO 8601 |
| hidden | INTEGER | `1` = masquée du dropdown (soft-delete) |
| tags | TEXT | colonne legacy v4, vidée en v5 — ne pas utiliser |

#### `sessions`
| Colonne | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| task_id | INTEGER FK | → tasks.id (foreign key activée) |
| started_at | TEXT | ISO 8601 |
| ended_at | TEXT | NULL si session en cours |
| duration_seconds | INTEGER | mis à jour toutes les 30 s par le timer |
| is_active | INTEGER | `1` = session non fermée (crash détection) |
| note | TEXT | note libre, sauvegardée depuis NoteWindow |

#### `config`
| Clé | Défaut | Description |
|---|---|---|
| `idle_enabled` | `"1"` | détection d'inactivité activée |
| `idle_minutes` | `"10"` | seuil d'inactivité en minutes |
| `reminder_enabled` | `"1"` | rappel de durée activé |
| `reminder_minutes` | `"60"` | intervalle de rappel en minutes |
| `close_to_tray` | `"1"` | fermer dans le tray au lieu de quitter |
| `overlay_x` | `"100"` | position X de l'overlay (persistée) |
| `overlay_y` | `"100"` | position Y de l'overlay (persistée) |
| `overlay_width` | `"340"` | largeur de l'overlay (persistée) |
| `theme` | `"dark"` | thème CustomTkinter (`"dark"` / `"light"`) |

### Migrations (incrémentales, idempotentes)

| Version | Changement |
|---|---|
| v1 | création initiale (tasks, sessions, config) |
| v2 | ajout `sessions.note` |
| v3 | ajout `tasks.hidden` |
| v4 | ajout `tasks.tags` (legacy, abandonné) |
| v5 | migration tags → inline dans `name`, vidage colonne `tags` |

---

## Modèle de threads

```
Thread principal (Tkinter mainloop)
  ├── App.mainloop()
  ├── consommateur de _ui_queue (event <<UITask>> + polling 100 ms)
  └── toutes les mises à jour UI passent ici

Thread TimerEngine (daemon)
  └── tick toutes les 1 s → _ui_call() → overlay.on_timer_tick()
      auto-save en base toutes les 30 s

Thread IdleDetector (daemon)
  └── sondage GetLastInputInfo toutes les 30 s
      déclenche _on_idle() une seule fois par période

Thread Reminder (daemon)
  └── vérifie toutes les 10 s si elapsed ≥ intervalle
      déclenche _on_reminder()

Thread pystray (daemon)
  └── menu tray → _ui_call() pour tout accès UI
```

**Règle absolue** : tout accès Tkinter depuis un thread non-principal passe par `app.after(0, fn)` ou `_ui_call(fn)`.

---

## Personnaliser l'apparence

Toutes les couleurs, polices et dimensions sont dans `time_tracker/ui/theme.py`.  
Constantes notables :
- `TAG_COLOR = "#f97316"` — couleur orange des badges #tag
- `FRAME_BG`, `DD_BG`, `ITEM_BG` — fonds des fenêtres flottantes
- `OVERLAY_H`, `OVERLAY_W_DEFAULT` — dimensions de la barre overlay

---

## Ajouter une dépendance

```bat
venv\Scripts\pip install <package>
venv\Scripts\pip freeze > requirements.txt
```

Puis vérifier si PyInstaller a besoin d'un hook supplémentaire dans `TimeTrackR.spec`.
