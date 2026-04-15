"""
Point d'entrée de TimeTrackR.
Initialise tous les composants, gère la reprise de session au démarrage
et fait tourner l'icône tray en arrière-plan.
"""

import ctypes
import tkinter as tk

import pystray

from .app import App
from .database import Database
from .icon import create_icon
from .idle_detector import IdleDetector
from .notifier import Notifier
from .overlay import Overlay
from .reminder import Reminder
from .task_manager import TaskManager
from .timer_engine import TimerEngine


# ------------------------------------------------------------------
# Identification de l'application pour la barre des tâches Windows
# ------------------------------------------------------------------

def _set_app_id() -> None:
    """
    Déclare un AppUserModelID unique pour que Windows regroupe toutes les fenêtres
    de TimeTrackR sous la même icône dans la barre des tâches.
    """
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "DevBooster.TimeTrackR.1.0"
        )
    except Exception:
        pass


# ------------------------------------------------------------------
# Classe principale
# ------------------------------------------------------------------

class TimeTrackRApp:
    """Orchestre tous les composants de l'application."""

    def __init__(self):
        _set_app_id()

        # --- Couche persistance ---
        self._db = Database()

        # --- Moteur timer ---
        self._timer = TimerEngine(self._db, self._on_tick)

        # --- Gestionnaire de tâches ---
        self._task_manager = TaskManager(self._db, self._timer)

        # --- Notificateur ---
        self._notifier = Notifier()

        # --- Détecteur d'inactivité ---
        idle_minutes = int(self._db.get_config("idle_minutes", "10"))
        self._idle_detector = IdleDetector(self._on_idle, idle_minutes)
        if self._db.get_config("idle_enabled", "1") != "1":
            self._idle_detector.disable()

        # --- Rappel de durée ---
        reminder_minutes = int(self._db.get_config("reminder_minutes", "60"))
        self._reminder = Reminder(self._on_reminder, reminder_minutes)
        self._reminder.set_timer_engine(self._timer)
        if self._db.get_config("reminder_enabled", "1") != "1":
            self._reminder.disable()

        # --- Fenêtre principale (cachée au démarrage) ---
        self._app = App(
            task_manager=self._task_manager,
            timer_engine=self._timer,
            database=self._db,
            on_new_task_requested=self._show_window,
            on_quit_requested=self._quit,
        )
        self._app.bind("<<SettingsChanged>>", self._on_settings_changed)

        # --- Overlay (créé ici, affiché après mainloop) ---
        self._overlay = Overlay(
            parent=self._app,
            task_manager=self._task_manager,
            timer_engine=self._timer,
            database=self._db,
            on_open_main=self._show_window,
        )

        # --- Icône tray ---
        self._tray_icon = self._build_tray()

    # ------------------------------------------------------------------
    # Reprise de session au démarrage
    # ------------------------------------------------------------------

    def _check_resumable_session(self) -> None:
        """Vérifie s'il existe une session non terminée et propose la reprise."""
        session = self._task_manager.get_resumable_session()
        if session is None:
            return

        duree = TimerEngine.format_elapsed(session["duration_seconds"])
        reponse = tk.messagebox.askyesno(
            "Reprendre la session ?",
            f"Une session était en cours :\n\n"
            f"  Tâche  : {session['name']}\n"
            f"  Durée  : {duree}\n\n"
            f"Voulez-vous la reprendre ?",
            parent=self._app,
        )
        if reponse:
            self._task_manager.resume_last_session(session)
            self._app.restore_running_state(session["name"], session["project"])
            self._overlay.notify_task_list_changed()
        else:
            self._task_manager.discard_last_session(session)

    # ------------------------------------------------------------------
    # Icône tray (pystray)
    # ------------------------------------------------------------------

    def _build_tray(self) -> pystray.Icon:
        """Construit l'icône tray avec l'icône chronomètre partagée."""
        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir TimeTrackR", self._show_window, default=True),
            pystray.MenuItem("Paramètres", self._show_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause / Reprendre", self._tray_toggle_pause),
            pystray.MenuItem("Arrêter la tâche", self._tray_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", self._quit),
        )
        # Utilisation de la même icône chronomètre que les fenêtres
        icon = pystray.Icon(
            "TimeTrackR",
            create_icon(64),
            "TimeTrackR — En attente",
            menu,
        )
        return icon

    def _update_tray_tooltip(self) -> None:
        """Met à jour le tooltip de l'icône tray."""
        if self._timer.is_running:
            task, _ = self._timer.current_task
            elapsed = TimerEngine.format_elapsed(self._timer.elapsed_seconds)
            status = "⏸" if self._timer.is_paused else "▶"
            self._tray_icon.title = f"TimeTrackR — {status} {task} [{elapsed}]"
        else:
            self._tray_icon.title = "TimeTrackR — En attente"

    # ------------------------------------------------------------------
    # Callbacks tray
    # ------------------------------------------------------------------

    def _show_window(self, icon=None, item=None) -> None:
        """Affiche la fenêtre principale."""
        self._app.after(0, self._app.show)

    def _show_settings(self, icon=None, item=None) -> None:
        """Ouvre la fenêtre des paramètres depuis le tray."""
        self._app.after(0, self._app.open_settings)

    def _tray_toggle_pause(self, icon=None, item=None) -> None:
        self._timer.toggle_pause()

    def _tray_stop(self, icon=None, item=None) -> None:
        self._task_manager.stop_task()
        self._app.after(0, self._app._on_stop)
        self._app.after(0, self._overlay.on_task_stopped)

    def _quit(self, icon=None, item=None) -> None:
        """Fermeture propre : sauvegarde finale, arrêt du timer, destruction Tkinter."""
        if self._timer.is_running:
            self._timer.stop()
        self._app.after(0, self._app.destroy)

    # ------------------------------------------------------------------
    # Callback tick timer (thread timer → UI)
    # ------------------------------------------------------------------

    def _on_tick(self, elapsed: int, task_name: str, project: str) -> None:
        """Propage le tick vers la fenêtre principale et l'overlay."""
        try:
            self._app.on_timer_tick(elapsed, task_name, project)
        except Exception:
            pass
        try:
            self._overlay.on_timer_tick(elapsed, task_name, project)
        except Exception:
            pass
        # Tooltip tray mis à jour toutes les 5 secondes
        if elapsed % 5 == 0:
            self._update_tray_tooltip()

    # ------------------------------------------------------------------
    # Callbacks inactivité et rappel
    # ------------------------------------------------------------------

    def _on_idle(self, idle_seconds: float) -> None:
        if not self._timer.is_running or self._timer.is_paused:
            return
        self._timer.pause()
        self._notifier.notify_idle(
            idle_seconds,
            on_resume=self._resume_from_idle,
            on_stop=self._stop_from_idle,
        )

    def _resume_from_idle(self) -> None:
        self._timer.resume()
        self._idle_detector.reset()
        self._app.after(0, lambda: self._app._update_button_states(running=True, paused=False))

    def _stop_from_idle(self) -> None:
        self._task_manager.stop_task()
        self._idle_detector.reset()
        self._app.after(0, self._app._on_stop)
        self._app.after(0, self._overlay.on_task_stopped)

    def _on_reminder(self, elapsed: int, task_name: str) -> None:
        self._notifier.notify_reminder(
            task_name,
            elapsed,
            on_continue=lambda: None,
            on_new_task=lambda: self._app.after(0, self._app._on_new_task),
        )

    # ------------------------------------------------------------------
    # Mise à jour des paramètres à la volée
    # ------------------------------------------------------------------

    def _on_settings_changed(self, event=None) -> None:
        """Lit les nouveaux paramètres en base et les applique aux modules."""
        idle_enabled = self._db.get_config("idle_enabled", "1") == "1"
        idle_minutes = int(self._db.get_config("idle_minutes", "10"))
        reminder_enabled = self._db.get_config("reminder_enabled", "1") == "1"
        reminder_minutes = int(self._db.get_config("reminder_minutes", "60"))

        self._idle_detector.set_threshold(idle_minutes)
        if idle_enabled:
            self._idle_detector.enable()
        else:
            self._idle_detector.disable()

        self._reminder.set_interval(reminder_minutes)
        if reminder_enabled:
            self._reminder.enable()
        else:
            self._reminder.disable()

    # ------------------------------------------------------------------
    # Démarrage
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Lance le tray via run_detached() puis la boucle Tkinter dans le thread principal.
        La session orpheline est vérifiée via after() une fois la boucle démarrée.
        """
        self._tray_icon.run_detached()
        self._app.after(200, self._check_resumable_session)
        self._app.mainloop()
        try:
            self._tray_icon.stop()
        except Exception:
            pass


# ------------------------------------------------------------------
# Point d'entrée
# ------------------------------------------------------------------

def main() -> None:
    """Lance TimeTrackR."""
    app = TimeTrackRApp()
    app.run()


if __name__ == "__main__":
    main()
