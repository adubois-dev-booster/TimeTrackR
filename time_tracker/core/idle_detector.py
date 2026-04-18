"""
Détection de l'inactivité clavier/souris sous Windows.
Utilise GetLastInputInfo via ctypes pour interroger le temps d'inactivité.
Vérification toutes les 30 secondes ; déclenche un callback si le seuil est dépassé.
"""

import ctypes
import threading
import time


# Intervalle de vérification de l'inactivité (en secondes)
CHECK_INTERVAL = 30


class LASTINPUTINFO(ctypes.Structure):
    """Structure Windows pour GetLastInputInfo."""
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_ulong),
    ]


def get_idle_seconds() -> float:
    """Retourne le nombre de secondes depuis la dernière activité clavier/souris."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    # GetTickCount() retourne le nombre de ms depuis le démarrage du système
    millis_since_last_input = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return millis_since_last_input / 1000.0


class IdleDetector:
    """
    Thread daemon qui surveille l'inactivité et appelle un callback
    quand le seuil est dépassé.
    Le callback reçoit la durée d'inactivité en secondes.
    """

    def __init__(self, on_idle_callback, threshold_minutes: int = 10):
        """
        :param on_idle_callback:  Fonction appelée quand inactivité > seuil.
                                  Signature : callback(idle_seconds: float)
        :param threshold_minutes: Seuil d'inactivité en minutes avant déclenchement.
        """
        self._callback = on_idle_callback
        self._threshold_seconds = threshold_minutes * 60
        self._enabled = True
        self._notified = False  # évite les notifications répétées pour la même période d'inactivité

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Contrôles publics
    # ------------------------------------------------------------------

    def set_threshold(self, minutes: int) -> None:
        """Met à jour le seuil d'inactivité à la volée."""
        self._threshold_seconds = minutes * 60
        self._notified = False

    def enable(self) -> None:
        """Active la surveillance."""
        self._enabled = True

    def disable(self) -> None:
        """Désactive la surveillance (sans arrêter le thread)."""
        self._enabled = False

    def reset(self) -> None:
        """Réinitialise le flag de notification (ex: après reprise du timer)."""
        self._notified = False

    # ------------------------------------------------------------------
    # Boucle interne
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Vérifie l'inactivité toutes les CHECK_INTERVAL secondes."""
        while True:
            time.sleep(CHECK_INTERVAL)

            if not self._enabled:
                continue

            idle = get_idle_seconds()

            if idle >= self._threshold_seconds:
                if not self._notified:
                    # Déclenche le callback une seule fois par période d'inactivité
                    self._notified = True
                    try:
                        self._callback(idle)
                    except Exception:
                        pass
            else:
                # L'utilisateur est revenu actif, on réarme pour la prochaine inactivité
                self._notified = False
