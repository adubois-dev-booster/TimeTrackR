"""
Gestion des tâches et projets : création, sélection, reprise au démarrage.
Fournit l'historique des tâches récentes pour l'autocomplétion de l'UI.
"""

from datetime import datetime, timedelta

from .database import Database
from .tag_utils import (
    display_to_name_tags,
    format_task_display,
    parse_task_input,
    tags_to_str,
)
from .timer_engine import TimerEngine


class TaskManager:
    """
    Fait le lien entre la base de données, le timer engine et l'UI
    pour tout ce qui concerne la sélection et la reprise des tâches.
    """

    def __init__(self, database: Database, timer_engine: TimerEngine):
        self._db = database
        self._timer = timer_engine

    # ------------------------------------------------------------------
    # Démarrage / arrêt de tâches
    # ------------------------------------------------------------------

    def start_task(self, raw_input: str, project: str = "") -> None:
        """
        Parse la saisie brute (peut contenir des #tags), puis démarre la tâche.
        Arrête proprement la session courante si une est en cours.
        """
        name, tags_list = parse_task_input(raw_input.strip())
        project = project.strip()
        if not name:
            raise ValueError("Le nom de la tâche ne peut pas être vide.")
        tags = tags_to_str(tags_list)
        self._timer.start(name, project, tags=tags)
        task_id = self._timer.current_task_id
        if task_id is not None:
            self._db.unhide_task(task_id)

    def start_known_task(self, name: str, project: str, tags: str = "") -> None:
        """
        Démarre une tâche dont on connaît déjà le nom, projet et tags (pas de parsing).
        Utilisé depuis les dropdowns où la tâche est déjà identifiée.
        """
        if not name:
            raise ValueError("Le nom de la tâche ne peut pas être vide.")
        self._timer.start(name, project, tags=tags)
        task_id = self._timer.current_task_id
        if task_id is not None:
            self._db.unhide_task(task_id)

    def stop_task(self) -> None:
        """Arrête le timer et ferme la session courante."""
        self._timer.stop()

    def pause_task(self) -> None:
        """Met le timer en pause."""
        self._timer.pause()

    def resume_task(self) -> None:
        """Reprend le timer après une pause."""
        self._timer.resume()

    # ------------------------------------------------------------------
    # Reprise au démarrage
    # ------------------------------------------------------------------

    def get_resumable_session(self) -> dict | None:
        """
        Retourne la dernière session active non terminée (is_active=1),
        ou None si l'appli s'était terminée proprement.
        """
        return self._db.get_last_active_session()

    def resume_last_session(self, session: dict) -> None:
        """
        Reprend une session existante en restaurant le temps déjà écoulé.
        :param session: Dictionnaire retourné par get_resumable_session().
        """
        self._timer.start(
            task_name=session["name"],
            project=session["project"],
            resume_session_id=session["id"],
            resume_elapsed=session["duration_seconds"],
        )

    def discard_last_session(self, session: dict) -> None:
        """
        Ferme proprement la session orpheline sans la reprendre.
        :param session: Dictionnaire retourné par get_resumable_session().
        """
        self._db.update_session(
            session_id=session["id"],
            duration_seconds=session["duration_seconds"],
            ended_at=None,
            is_active=False,
        )

    # ------------------------------------------------------------------
    # Historique pour l'autocomplétion
    # ------------------------------------------------------------------

    def get_recent_task_names(self, limit: int = 10) -> list[str]:
        """
        Retourne les chaînes d'affichage des tâches récentes (nom + badges tags).
        Chaque entrée est unique ; deux tâches de même nom mais tags différents
        apparaissent séparément.
        """
        tasks = self._db.get_recent_tasks(limit)
        seen: set[str] = set()
        names: list[str] = []
        for t in tasks:
            display = format_task_display(t["name"], t.get("tags", ""))
            if display not in seen:
                seen.add(display)
                names.append(display)
        return names

    def get_recent_projects(self, limit: int = 10) -> list[str]:
        """Retourne les noms des projets récents (dédupliqués)."""
        tasks = self._db.get_recent_tasks(limit)
        seen = set()
        projects = []
        for t in tasks:
            proj = t["project"]
            if proj and proj not in seen:
                seen.add(proj)
                projects.append(proj)
        return projects

    def get_recent_tasks(self, limit: int = 10) -> list[dict]:
        """Retourne les tâches récentes complètes (nom + projet)."""
        return self._db.get_recent_tasks(limit)

    def hide_task(self, task_id: int) -> None:
        """Masque la tâche du dropdown overlay (sessions conservées en base)."""
        self._db.hide_task(task_id)

    # ------------------------------------------------------------------
    # Gestion de l'inactivité
    # ------------------------------------------------------------------

    def handle_idle_resume(self) -> None:
        """Même tâche, reprise simple sans modification de session."""
        self._timer.resume()

    def handle_idle_credit_and_resume(self, task_display: str, idle_seconds: int) -> None:
        """
        Crédite l'inactivité sur la tâche sélectionnée, puis reprend la tâche d'origine.
        task_display est une chaîne d'affichage (peut contenir des [tags]).
        """
        name, tags = display_to_name_tags(task_display)
        original_name, _ = self._timer.current_task
        original_tags     = self._timer.current_tags
        if name == original_name and tags == original_tags:
            self._timer.add_elapsed(idle_seconds)
        else:
            self._db.add_retroactive_session(name, "", idle_seconds, tags)
        self._timer.resume()

    def handle_idle_switch_task(self, task_display: str, idle_seconds: int) -> None:
        """
        Était sur B pendant l'inactivité, continue sur B.
        Session A backdatée au début de l'inactivité ; session B démarre depuis ce même instant.
        task_display est une chaîne d'affichage (peut contenir des [tags]).
        """
        name, tags   = display_to_name_tags(task_display)
        elapsed_A    = self._timer.elapsed_seconds
        session_A_id = self._timer.session_id
        idle_start   = datetime.now() - timedelta(seconds=idle_seconds)

        self._timer.stop()

        if session_A_id is not None:
            self._db.update_session(session_A_id, elapsed_A, ended_at=idle_start, is_active=False)

        task_id_B    = self._db.get_or_create_task(name, "", tags)
        session_B_id = self._db.save_session(task_id_B, started_at=idle_start)
        self._db.unhide_task(task_id_B)
        self._timer.start(name, "", tags=tags, resume_session_id=session_B_id, resume_elapsed=idle_seconds)

    # ------------------------------------------------------------------
    # Notes de session
    # ------------------------------------------------------------------

    def get_current_note(self) -> str:
        """Retourne la note de la session en cours (vide si aucune session active)."""
        sid = self._timer.session_id
        if sid is None:
            return ""
        return self._db.get_session_note(sid)

    def set_current_note(self, note: str) -> None:
        """Enregistre la note pour la session en cours (no-op si aucune session active)."""
        sid = self._timer.session_id
        if sid is None:
            return
        self._db.set_session_note(sid, note)
