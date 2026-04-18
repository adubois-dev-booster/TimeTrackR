"""
Moteur de timer : thread daemon qui gère le chronomètre en arrière-plan.
Émet un tick toutes les secondes via un callback vers l'UI.
Sauvegarde automatiquement la session en base toutes les 30 secondes.
"""

import threading
import time
from datetime import datetime
from typing import Callable

from .database import Database


# Intervalle de sauvegarde automatique en secondes
AUTOSAVE_INTERVAL = 30


class TimerEngine:
    """
    Gère le cycle de vie du timer (démarrer, pauser, reprendre, arrêter).
    Thread-safe : toutes les modifications d'état passent par un verrou.
    """

    def __init__(self, database: Database, tick_callback: Callable[[int, str, str], None]):
        """
        :param database:      Instance Database pour la persistance.
        :param tick_callback: Appelé toutes les secondes avec (secondes_écoulées, nom_tâche, projet).
        """
        self._db = database
        self._tick_callback = tick_callback
        self._lock = threading.Lock()

        # État courant du timer
        self._running = False
        self._paused = False
        self._task_name = ""
        self._project = ""
        self._session_id: int | None = None
        self._elapsed_seconds = 0
        self._started_at: datetime | None = None
        self._last_autosave = 0

        # Thread daemon : s'arrête automatiquement si le processus principal quitte
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Contrôles publics (thread-safe)
    # ------------------------------------------------------------------

    def start(self, task_name: str, project: str, resume_session_id: int | None = None, resume_elapsed: int = 0) -> None:
        """
        Démarre (ou reprend) le timer pour une tâche.
        Si resume_session_id est fourni, on reprend une session existante
        au lieu d'en créer une nouvelle.
        """
        with self._lock:
            # Arrêter proprement une session précédente si elle existe
            if self._running and self._session_id:
                self._save_session(is_active=False)

            self._task_name = task_name
            self._project = project
            self._elapsed_seconds = resume_elapsed
            self._started_at = datetime.now()
            self._paused = False
            self._running = True
            self._last_autosave = 0

            if resume_session_id is not None:
                # Reprise d'une session existante
                self._session_id = resume_session_id
            else:
                # Nouvelle session en base
                task_id = self._db.get_or_create_task(task_name, project)
                self._session_id = self._db.save_session(task_id, self._started_at)

    def pause(self) -> None:
        """Met le timer en pause (la session reste active en base)."""
        with self._lock:
            if self._running and not self._paused:
                self._paused = True
                if self._session_id:
                    self._save_session(is_active=True)

    def resume(self) -> None:
        """Reprend le timer après une pause."""
        with self._lock:
            if self._running and self._paused:
                self._paused = False

    def stop(self) -> None:
        """Arrête le timer et ferme la session en base."""
        with self._lock:
            if self._running:
                if self._session_id:
                    self._save_session(is_active=False)
                self._running = False
                self._paused = False
                self._session_id = None
                self._elapsed_seconds = 0
                self._task_name = ""
                self._project = ""

    def add_elapsed(self, extra_seconds: int) -> None:
        """Ajoute du temps à l'elapsed sans relancer le timer (thread-safe)."""
        with self._lock:
            if self._running:
                self._elapsed_seconds += extra_seconds

    def toggle_pause(self) -> bool:
        """Bascule pause/reprise. Retourne True si le timer est maintenant en pause."""
        with self._lock:
            if not self._running:
                return False
            self._paused = not self._paused
            if self._paused and self._session_id:
                self._save_session(is_active=True)
            return self._paused

    # ------------------------------------------------------------------
    # Lecture d'état (thread-safe)
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def elapsed_seconds(self) -> int:
        with self._lock:
            return self._elapsed_seconds

    @property
    def current_task(self) -> tuple[str, str]:
        """Retourne (nom_tâche, projet)."""
        with self._lock:
            return self._task_name, self._project

    @property
    def session_id(self) -> int | None:
        with self._lock:
            return self._session_id

    # ------------------------------------------------------------------
    # Boucle interne (thread daemon)
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Boucle principale : tick toutes les secondes."""
        while True:
            time.sleep(1)

            with self._lock:
                if not self._running or self._paused:
                    continue

                self._elapsed_seconds += 1
                self._last_autosave += 1
                task_name = self._task_name
                project = self._project
                elapsed = self._elapsed_seconds

                # Sauvegarde automatique toutes les AUTOSAVE_INTERVAL secondes
                if self._last_autosave >= AUTOSAVE_INTERVAL and self._session_id:
                    self._save_session(is_active=True)
                    self._last_autosave = 0

            # Appel du callback hors du verrou pour éviter un deadlock avec l'UI
            try:
                self._tick_callback(elapsed, task_name, project)
            except Exception:
                pass  # L'UI peut avoir été détruite ; on continue silencieusement

    def _save_session(self, is_active: bool) -> None:
        """
        Enregistre l'état courant en base.
        Doit être appelé avec self._lock déjà acquis.
        """
        ended_at = None if is_active else datetime.now()
        self._db.update_session(
            session_id=self._session_id,
            duration_seconds=self._elapsed_seconds,
            ended_at=ended_at,
            is_active=is_active,
        )

    # ------------------------------------------------------------------
    # Utilitaire
    # ------------------------------------------------------------------

    @staticmethod
    def format_elapsed(seconds: int) -> str:
        """
        Durée compacte : omet les heures si nulles, les minutes si nulles.
        Exemples : 12s · 23m12s · 1h05m30s
        """
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}h{m:02d}m{s:02d}s"
        if m > 0:
            return f"{m}m{s:02d}s"
        return f"{s}s"
