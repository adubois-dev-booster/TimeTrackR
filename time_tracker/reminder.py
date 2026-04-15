"""
Gestion des rappels de durée de tâche.
Si le timer tourne depuis Y minutes sans interruption, un callback est déclenché.
Le rappel se répète tous les Y minutes tant que la tâche continue.
"""

import threading
import time


class Reminder:
    """
    Surveille la durée d'une tâche et déclenche un rappel périodique.
    S'appuie sur le timer_engine pour connaître le temps écoulé.
    """

    def __init__(self, on_reminder_callback, interval_minutes: int = 60):
        """
        :param on_reminder_callback: Appelé quand l'intervalle est atteint.
                                     Signature : callback(elapsed_seconds: int, task_name: str)
        :param interval_minutes:     Intervalle en minutes entre deux rappels.
        """
        self._callback = on_reminder_callback
        self._interval_seconds = interval_minutes * 60
        self._enabled = True

        # Référence vers le timer engine, injectée via set_timer_engine()
        self._timer_engine = None
        self._last_reminder_at = 0  # secondes écoulées au dernier rappel

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Contrôles publics
    # ------------------------------------------------------------------

    def set_timer_engine(self, engine) -> None:
        """Injecte la référence vers le TimerEngine après création."""
        self._timer_engine = engine

    def set_interval(self, minutes: int) -> None:
        """Met à jour l'intervalle à la volée (prend effet au prochain cycle)."""
        self._interval_seconds = minutes * 60

    def enable(self) -> None:
        """Active les rappels."""
        self._enabled = True

    def disable(self) -> None:
        """Désactive les rappels."""
        self._enabled = False

    def reset(self) -> None:
        """Réinitialise le compteur (appelé à chaque démarrage/reprise de tâche)."""
        self._last_reminder_at = 0

    # ------------------------------------------------------------------
    # Boucle interne
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Vérifie toutes les 10 secondes si l'intervalle de rappel est atteint."""
        while True:
            time.sleep(10)

            if not self._enabled or self._timer_engine is None:
                continue

            if not self._timer_engine.is_running or self._timer_engine.is_paused:
                continue

            elapsed = self._timer_engine.elapsed_seconds

            # Combien d'intervalles complets ont été atteints depuis le dernier rappel ?
            if elapsed > 0 and elapsed - self._last_reminder_at >= self._interval_seconds:
                self._last_reminder_at = elapsed
                task_name, _ = self._timer_engine.current_task
                try:
                    self._callback(elapsed, task_name)
                except Exception:
                    pass
