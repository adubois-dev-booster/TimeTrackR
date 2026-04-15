"""
Point d'entrée de TimeTrackR.
Initialise tous les composants, gère la reprise de session au démarrage
et fait tourner l'icône tray en arrière-plan.
"""

import tkinter as tk

import pystray
from PIL import Image, ImageDraw

from .app import App
from .database import Database
from .idle_detector import IdleDetector
from .notifier import Notifier
from .reminder import Reminder
from .task_manager import TaskManager
from .timer_engine import TimerEngine


# ------------------------------------------------------------------
# Icône tray générée dynamiquement (cercle coloré)
# ------------------------------------------------------------------

def _build_tray_icon() -> Image.Image:
    """Crée une icône 64×64 pour le system tray."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Fond circulaire bleu
    draw.ellipse([4, 4, size - 4, size - 4], fill="#2563eb")
    # Symbole ▶ centré
    draw.polygon([(24, 18), (24, 46), (48, 32)], fill="white")
    return img


# ------------------------------------------------------------------
# Classe principale
# ------------------------------------------------------------------

class TimeTrackRApp:
    """Orchestre tous les composants de l'application."""

    def __init__(self):
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

        # --- Fenêtre principale (créée mais non affichée) ---
        self._app = App(
            task_manager=self._task_manager,
            timer_engine=self._timer,
            database=self._db,
            on_new_task_requested=self._show_window,
            on_quit_requested=self._quit,
        )
        # Écoute les changements de paramètres (émis par SettingsWindow après sauvegarde)
        self._app.bind("<<SettingsChanged>>", self._on_settings_changed)

        # --- Icône tray (construite ici, démarrée dans run()) ---
        self._tray_icon = self._build_tray()

    # ------------------------------------------------------------------
    # Reprise de session au démarrage
    # ------------------------------------------------------------------

    def _check_resumable_session(self) -> None:
        """
        Vérifie s'il existe une session non terminée.
        Affiche un dialog de reprise si c'est le cas.
        """
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
        else:
            self._task_manager.discard_last_session(session)

    # ------------------------------------------------------------------
    # Icône tray (pystray)
    # ------------------------------------------------------------------

    def _build_tray(self) -> pystray.Icon:
        """Construit et retourne l'icône tray avec son menu contextuel."""
        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir TimeTrackR", self._show_window, default=True),
            pystray.MenuItem("Paramètres", self._show_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause / Reprendre", self._tray_toggle_pause),
            pystray.MenuItem("Arrêter la tâche", self._tray_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", self._quit),
        )
        icon = pystray.Icon(
            "TimeTrackR",
            _build_tray_icon(),
            "TimeTrackR — En attente",
            menu,
        )
        return icon

    def _update_tray_tooltip(self) -> None:
        """Met à jour le tooltip de l'icône avec la tâche et le temps écoulé."""
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
        """Affiche la fenêtre principale (depuis n'importe quel thread)."""
        self._app.after(0, self._app.show)

    def _show_settings(self, icon=None, item=None) -> None:
        """Ouvre la fenêtre des paramètres depuis le tray."""
        self._app.after(0, self._app.open_settings)

    def _tray_toggle_pause(self, icon=None, item=None) -> None:
        """Bascule pause/reprise depuis le menu tray."""
        self._timer.toggle_pause()

    def _tray_stop(self, icon=None, item=None) -> None:
        """Arrête la tâche courante depuis le menu tray."""
        self._task_manager.stop_task()
        self._app.after(0, self._app._on_stop)

    def _quit(self, icon=None, item=None) -> None:
        """Fermeture propre : sauvegarde finale, arrêt du timer, fin de Tkinter."""
        if self._timer.is_running:
            self._timer.stop()
        # Détruire la fenêtre Tkinter depuis son thread (via after) pour
        # que mainloop() se termine proprement, puis pystray est stoppé dans run()
        self._app.after(0, self._app.destroy)

    # ------------------------------------------------------------------
    # Callback tick timer (thread timer → UI)
    # ------------------------------------------------------------------

    def _on_tick(self, elapsed: int, task_name: str, project: str) -> None:
        """Reçoit chaque tick et propage vers l'UI et le tooltip tray."""
        # Mise à jour de la fenêtre
        try:
            self._app.on_timer_tick(elapsed, task_name, project)
        except Exception:
            pass
        # Mise à jour du tooltip toutes les 5 secondes pour éviter la surcharge
        if elapsed % 5 == 0:
            self._update_tray_tooltip()

    # ------------------------------------------------------------------
    # Callbacks inactivité et rappel
    # ------------------------------------------------------------------

    def _on_idle(self, idle_seconds: float) -> None:
        """Déclenché quand l'inactivité dépasse le seuil."""
        if not self._timer.is_running or self._timer.is_paused:
            return
        self._timer.pause()
        self._notifier.notify_idle(
            idle_seconds,
            on_resume=self._resume_from_idle,
            on_stop=self._stop_from_idle,
        )

    def _resume_from_idle(self) -> None:
        """L'utilisateur a cliqué 'Reprendre' dans la notification d'inactivité."""
        self._timer.resume()
        self._idle_detector.reset()
        self._app.after(0, lambda: self._app._update_button_states(running=True, paused=False))

    def _stop_from_idle(self) -> None:
        """L'utilisateur a cliqué 'Arrêter' dans la notification d'inactivité."""
        self._task_manager.stop_task()
        self._idle_detector.reset()
        self._app.after(0, self._app._on_stop)

    def _on_reminder(self, elapsed: int, task_name: str) -> None:
        """Déclenché par le rappel de durée de tâche."""
        self._notifier.notify_reminder(
            task_name,
            elapsed,
            on_continue=lambda: None,  # L'utilisateur continue : ne rien faire
            on_new_task=lambda: self._app.after(0, self._app._on_new_task),
        )

    # ------------------------------------------------------------------
    # Mise à jour des paramètres à la volée
    # ------------------------------------------------------------------

    def _on_settings_changed(self, event=None) -> None:
        """
        Synchronise les modules périphériques avec les nouveaux paramètres.
        SettingsWindow a déjà sauvegardé en base avant d'émettre cet événement,
        donc on lit directement depuis la DB.
        """
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
        Lance l'icône tray via run_detached() (thread interne géré par pystray)
        puis démarre la boucle Tkinter dans le thread principal.
        La vérification de session reprend se fait via after() une fois
        que la boucle est active, pour éviter d'appeler des dialogs avant mainloop.
        """
        # run_detached() démarre pystray dans son propre thread et rend l'icône
        # visible via la fonction setup par défaut (visible = True)
        self._tray_icon.run_detached()

        # Vérification de la session orpheline après que mainloop est démarrée
        self._app.after(200, self._check_resumable_session)

        # Boucle Tkinter dans le thread principal (obligatoire sous Windows)
        self._app.mainloop()

        # Nettoyage quand mainloop() se termine (suite à app.destroy())
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
