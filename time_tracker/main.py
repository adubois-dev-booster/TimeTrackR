"""
Point d'entrée de TimeTrackR.
Initialise tous les composants, gère la reprise de session au démarrage
et fait tourner l'icône tray en arrière-plan.
"""

import ctypes
import queue
import tkinter as tk

import pystray

from .core.database import Database
from .core.idle_detector import IdleDetector
from .core.reminder import Reminder
from .core.tag_utils import format_task_display
from .core.task_manager import TaskManager
from .core.timer_engine import TimerEngine
from .ui.app import App
from .ui.icon import create_icon
from .ui.notifier import Notifier
from .ui.overlay import Overlay


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

        # File thread-safe pour les appels UI depuis des threads non-principaux
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()

        # --- Couche persistance ---
        self._db = Database()

        # --- Moteur timer ---
        self._timer = TimerEngine(self._db, self._on_tick)

        # --- Gestionnaire de tâches ---
        self._task_manager = TaskManager(self._db, self._timer)

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
        # Note : App doit être créée avant Notifier (Notifier a besoin du parent Tk)
        self._app = App(
            task_manager=self._task_manager,
            timer_engine=self._timer,
            database=self._db,
            on_new_task_requested=self._show_window,
            on_quit_requested=self._quit,
        )
        self._app.bind("<<SettingsChanged>>", self._on_settings_changed)
        # Drain de la file UI déclenché par event_generate depuis n'importe quel thread
        self._app.bind("<<UITask>>", lambda e: self._drain_ui_queue())
        # Polling de secours : garantit le drain même si event_generate est manqué
        self._app.after(100, self._poll_ui_queue)

        # --- Notificateur (après App car nécessite une fenêtre Tk parente) ---
        self._notifier = Notifier(self._app)

        # --- Overlay (créé ici, affiché après mainloop) ---
        self._overlay = Overlay(
            parent=self._app,
            task_manager=self._task_manager,
            timer_engine=self._timer,
            database=self._db,
            on_open_main=self._show_window,
            on_stop_requested=self._handle_overlay_stop,
        )

        # --- Icône tray ---
        self._tray_icon = self._build_tray()

    # ------------------------------------------------------------------
    # Reprise de session au démarrage
    # ------------------------------------------------------------------

    def _check_resumable_session(self) -> None:
        """Vérifie s'il existe une session non terminée et propose la reprise."""
        from datetime import date as _date
        session = self._task_manager.get_resumable_session()
        if session is None:
            return

        new_day = session["started_at"][:10] != _date.today().isoformat()
        duree   = TimerEngine.format_elapsed(session["duration_seconds"])

        if new_day:
            msg = (
                f"Une session d'un jour précédent était en cours :\n\n"
                f"  Tâche  : {session['name']}\n"
                f"  Durée  : {duree}\n\n"
                f"Voulez-vous continuer cette tâche aujourd'hui ?"
            )
        else:
            msg = (
                f"Une session était en cours :\n\n"
                f"  Tâche  : {session['name']}\n"
                f"  Durée  : {duree}\n\n"
                f"Voulez-vous la reprendre ?"
            )

        reponse = tk.messagebox.askyesno("Reprendre la session ?", msg, parent=self._app)

        if reponse:
            self._task_manager.discard_last_session(session)
            if new_day:
                self._task_manager.start_task(session["name"], session["project"])
            else:
                self._task_manager.resume_last_session(session)
            self._app.restore_running_state()
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
    # File UI thread-safe (tray + timer → thread principal)
    # ------------------------------------------------------------------

    def _ui_call(self, fn) -> None:
        """
        Enfile fn pour exécution sur le thread principal.
        Thread-safe : event_generate() poste dans la queue Tk native.
        """
        self._ui_queue.put(fn)
        try:
            self._app.event_generate("<<UITask>>", when="tail")
        except Exception:
            pass  # Drainé par le polling de toute façon

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                self._ui_queue.get_nowait()()
            except queue.Empty:
                break

    def _poll_ui_queue(self) -> None:
        """Polling de secours toutes les 100 ms."""
        self._drain_ui_queue()
        try:
            self._app.after(100, self._poll_ui_queue)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Callbacks tray (thread pystray → thread principal via _ui_call)
    # ------------------------------------------------------------------

    def _show_window(self, icon=None, item=None) -> None:
        """Affiche la fenêtre principale."""
        self._ui_call(self._app.show)

    def _show_settings(self, icon=None, item=None) -> None:
        """Ouvre la fenêtre des paramètres depuis le tray."""
        self._ui_call(self._app.open_settings)

    def _tray_toggle_pause(self, icon=None, item=None) -> None:
        self._timer.toggle_pause()

    def _tray_stop(self, icon=None, item=None) -> None:
        self._task_manager.stop_task()
        self._ui_call(self._app._on_stop)
        self._ui_call(self._overlay.on_task_stopped)

    def _handle_overlay_stop(self) -> None:
        """Arrêt déclenché depuis le bouton ⏹ de l'overlay (thread principal)."""
        self._app.after(0, self._app._on_stop)

    def _quit(self, icon=None, item=None) -> None:
        """Fermeture propre : sauvegarde finale, arrêt du timer, destruction Tkinter."""
        if self._timer.is_running:
            self._timer.stop()
        self._ui_call(self._app.destroy)

    # ------------------------------------------------------------------
    # Callback tick timer (thread timer → thread principal via _ui_call)
    # ------------------------------------------------------------------

    def _on_tick(self, elapsed: int, task_name: str, project: str) -> None:
        """Redirige le tick vers le thread principal."""
        self._ui_call(lambda: self._on_tick_ui(elapsed, task_name, project))

    def _on_tick_ui(self, elapsed: int, task_name: str, project: str) -> None:
        """Exécuté sur le thread principal : propage le tick vers l'UI."""
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
        _orig_name, _    = self._timer.current_task
        original_task    = format_task_display(_orig_name, self._timer.current_tags)
        recent_tasks     = self._task_manager.get_recent_task_names()
        self._notifier.notify_idle(
            idle_seconds,
            on_resume=self._resume_from_idle,
            on_stop=self._stop_from_idle,
            original_task=original_task,
            recent_tasks=recent_tasks,
            on_other_continue=self._switch_to_other_task,
            on_other_resume_old=self._credit_and_resume,
        )

    def _resume_from_idle(self) -> None:
        """Même tâche → reprise simple."""
        self._task_manager.handle_idle_resume()
        self._idle_detector.reset()

    def _stop_from_idle(self) -> None:
        """Arrêt depuis la dialog d'inactivité."""
        self._task_manager.stop_task()
        self._idle_detector.reset()
        self._app.after(0, self._app._on_stop)
        self._app.after(0, self._overlay.on_task_stopped)

    def _switch_to_other_task(self, task_name: str, idle_seconds: int) -> None:
        """Continue sur une autre tâche : session A backdatée, session B depuis idle_start."""
        self._task_manager.handle_idle_switch_task(task_name, idle_seconds)
        self._idle_detector.reset()
        self._app.after(0, self._app._refresh_history)
        self._app.after(0, self._overlay.notify_task_list_changed)

    def _credit_and_resume(self, task_name: str, idle_seconds: int) -> None:
        """Crédite l'inactivité sur task_name, puis reprend la tâche d'origine."""
        self._task_manager.handle_idle_credit_and_resume(task_name, idle_seconds)
        self._idle_detector.reset()
        self._app.after(0, self._app._refresh_history)

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
