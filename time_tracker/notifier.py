"""
Envoi de notifications Windows natives via windows-toasts.
Deux types de notifications : inactivité détectée et rappel de durée de tâche.
Les callbacks sur les boutons sont routés vers le timer engine.
InteractableWindowsToaster est requis pour les toasts avec boutons d'action.
"""

from windows_toasts import (
    Toast,
    InteractableWindowsToaster,
    ToastActivatedEventArgs,
    ToastButton,
)


class Notifier:
    """Encapsule l'envoi de toasts Windows avec callbacks sur les boutons."""

    APP_ID = "TimeTrackR"

    def __init__(self):
        # InteractableWindowsToaster est nécessaire pour les boutons d'action
        self._toaster = InteractableWindowsToaster(self.APP_ID)

    # ------------------------------------------------------------------
    # Notification inactivité
    # ------------------------------------------------------------------

    def notify_idle(
        self,
        idle_seconds: float,
        on_resume,
        on_stop,
    ) -> None:
        """
        Affiche une notification "Inactivité détectée".
        :param idle_seconds: Durée d'inactivité en secondes.
        :param on_resume:    Callback quand l'utilisateur clique "Reprendre".
        :param on_stop:      Callback quand l'utilisateur clique "Arrêter".
        """
        minutes = int(idle_seconds // 60)
        duree = f"{minutes} min" if minutes > 0 else f"{int(idle_seconds)} s"

        toast = Toast(
            text_fields=["Inactivité détectée", f"Aucune activité depuis {duree}. Que faire ?"],
            actions=[
                ToastButton("Reprendre", arguments="reprendre"),
                ToastButton("Arrêter la session", arguments="arreter"),
            ],
            on_activated=lambda args: self._handle_idle_action(args, on_resume, on_stop),
        )
        self._toaster.show_toast(toast)

    # ------------------------------------------------------------------
    # Notification rappel durée de tâche
    # ------------------------------------------------------------------

    def notify_reminder(
        self,
        task_name: str,
        elapsed_seconds: int,
        on_continue,
        on_new_task,
    ) -> None:
        """
        Affiche une notification de rappel "Toujours sur [tâche] ?".
        :param task_name:        Nom de la tâche en cours.
        :param elapsed_seconds:  Durée écoulée en secondes.
        :param on_continue:      Callback "Continuer".
        :param on_new_task:      Callback "Nouvelle tâche".
        """
        h = elapsed_seconds // 3600
        m = (elapsed_seconds % 3600) // 60
        duree = f"{h}h{m:02d}" if h > 0 else f"{m} min"

        toast = Toast(
            text_fields=[
                f"Toujours sur « {task_name} » ?",
                f"Timer actif depuis {duree}. Voulez-vous continuer ?",
            ],
            actions=[
                ToastButton("Continuer", arguments="continuer"),
                ToastButton("Nouvelle tâche", arguments="nouvelle_tache"),
            ],
            on_activated=lambda args: self._handle_reminder_action(args, on_continue, on_new_task),
        )
        self._toaster.show_toast(toast)

    # ------------------------------------------------------------------
    # Notification générique (information)
    # ------------------------------------------------------------------

    def notify_info(self, title: str, message: str) -> None:
        """Affiche un toast informatif sans boutons d'action."""
        toast = Toast(text_fields=[title, message])
        self._toaster.show_toast(toast)

    # ------------------------------------------------------------------
    # Gestion des clics sur les boutons
    # ------------------------------------------------------------------

    def _handle_idle_action(self, args: ToastActivatedEventArgs, on_resume, on_stop) -> None:
        """Redirige l'action du toast d'inactivité vers le bon callback."""
        action = getattr(args, "arguments", "") or ""
        if action == "reprendre":
            try:
                on_resume()
            except Exception:
                pass
        elif action == "arreter":
            try:
                on_stop()
            except Exception:
                pass

    def _handle_reminder_action(self, args: ToastActivatedEventArgs, on_continue, on_new_task) -> None:
        """Redirige l'action du toast de rappel vers le bon callback."""
        action = getattr(args, "arguments", "") or ""
        if action == "continuer":
            try:
                on_continue()
            except Exception:
                pass
        elif action == "nouvelle_tache":
            try:
                on_new_task()
            except Exception:
                pass
