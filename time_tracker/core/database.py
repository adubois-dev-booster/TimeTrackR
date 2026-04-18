"""
Couche d'accès à la base de données SQLite.
Le fichier .db est stocké dans %APPDATA%/TimeTracker/timetracker.db
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path


def get_db_path() -> Path:
    """Retourne le chemin vers le fichier SQLite, en créant le répertoire si besoin."""
    appdata = os.environ.get("APPDATA", Path.home())
    db_dir = Path(appdata) / "TimeTracker"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "timetracker.db"


class Database:
    """Gère toutes les opérations de lecture/écriture SQLite."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_db_path()
        self._init_tables()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Ouvre une connexion avec support des foreign keys et retourne des Row."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_tables(self) -> None:
        """Crée les tables si elles n'existent pas encore, puis migre le schéma."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    project     TEXT NOT NULL DEFAULT '',
                    created_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id          INTEGER NOT NULL REFERENCES tasks(id),
                    started_at       TEXT NOT NULL,
                    ended_at         TEXT,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    is_active        INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS config (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
        self._migrate()

    def _migrate(self) -> None:
        """Applique les migrations de schéma incrémentales."""
        with self._connect() as conn:
            # v2 : colonne note sur les sessions
            try:
                conn.execute(
                    "ALTER TABLE sessions ADD COLUMN note TEXT NOT NULL DEFAULT ''"
                )
            except sqlite3.OperationalError:
                pass  # Colonne déjà présente
            # v3 : colonne hidden sur les tâches (masquage dans le dropdown overlay)
            try:
                conn.execute(
                    "ALTER TABLE tasks ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Colonne déjà présente

    # ------------------------------------------------------------------
    # Tâches
    # ------------------------------------------------------------------

    def get_or_create_task(self, name: str, project: str) -> int:
        """
        Retourne l'id de la tâche existante (même nom + projet)
        ou en crée une nouvelle si elle n'existe pas.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM tasks WHERE name = ? AND project = ?",
                (name, project),
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                "INSERT INTO tasks (name, project, created_at) VALUES (?, ?, ?)",
                (name, project, datetime.now().isoformat()),
            )
            return cur.lastrowid

    def get_recent_tasks(self, limit: int = 10) -> list[dict]:
        """
        Retourne les <limit> tâches les plus récemment utilisées
        (triées par dernière session, les tâches masquées exclues).
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.id, t.name, t.project, MAX(s.started_at) AS last_used
                FROM tasks t
                JOIN sessions s ON s.task_id = t.id
                WHERE t.hidden = 0
                GROUP BY t.id
                ORDER BY last_used DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def add_retroactive_session(self, task_name: str, project: str, duration_seconds: int) -> None:
        """
        Crée une session passée pour réaffecter du temps (ex : temps inactif).
        started_at = maintenant - duration_seconds, ended_at = maintenant.
        """
        task_id    = self.get_or_create_task(task_name, project)
        now        = datetime.now()
        started_at = now - timedelta(seconds=duration_seconds)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                    (task_id, started_at, ended_at, duration_seconds, is_active)
                VALUES (?, ?, ?, ?, 0)
                """,
                (task_id, started_at.isoformat(), now.isoformat(), duration_seconds),
            )

    def hide_task(self, task_name: str) -> None:
        """Masque une tâche du dropdown overlay (les sessions sont conservées)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET hidden = 1 WHERE name = ?", (task_name,)
            )

    def unhide_task(self, task_name: str) -> None:
        """Remet une tâche masquée dans la liste du dropdown."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET hidden = 0 WHERE name = ?", (task_name,)
            )

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def save_session(self, task_id: int, started_at: datetime) -> int:
        """Crée une nouvelle session active et retourne son id."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sessions (task_id, started_at, duration_seconds, is_active)
                VALUES (?, ?, 0, 1)
                """,
                (task_id, started_at.isoformat()),
            )
            return cur.lastrowid

    def update_session(
        self,
        session_id: int,
        duration_seconds: int,
        ended_at: datetime | None = None,
        is_active: bool = True,
    ) -> None:
        """Met à jour la durée (et optionnellement la fin) d'une session."""
        with self._connect() as conn:
            if ended_at is not None:
                conn.execute(
                    """
                    UPDATE sessions
                    SET duration_seconds = ?, ended_at = ?, is_active = ?
                    WHERE id = ?
                    """,
                    (duration_seconds, ended_at.isoformat(), int(is_active), session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET duration_seconds = ?, is_active = ? WHERE id = ?",
                    (duration_seconds, int(is_active), session_id),
                )

    def get_today_sessions(self) -> list[dict]:
        """Retourne toutes les sessions du jour avec le nom, projet et note de la tâche."""
        today = datetime.now().date().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, t.name, t.project,
                       s.started_at, s.ended_at,
                       s.duration_seconds, s.is_active, s.note
                FROM sessions s
                JOIN tasks t ON t.id = s.task_id
                WHERE DATE(s.started_at) = ?
                ORDER BY s.started_at DESC
                """,
                (today,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session_note(self, session_id: int) -> str:
        """Retourne la note associée à une session."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT note FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return row["note"] if row else ""

    def set_session_note(self, session_id: int, note: str) -> None:
        """Enregistre ou met à jour la note d'une session."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET note = ? WHERE id = ?", (note, session_id)
            )

    def get_history_sessions(self, days: int = 30) -> list[dict]:
        """Retourne toutes les sessions des <days> derniers jours, du plus récent au plus vieux."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, t.name, t.project,
                       s.started_at, s.ended_at,
                       s.duration_seconds, s.is_active, s.note
                FROM sessions s
                JOIN tasks t ON t.id = s.task_id
                WHERE s.started_at >= date('now', ? || ' days')
                ORDER BY s.started_at DESC
                """,
                (f"-{days}",),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_task_recent_sessions(self, task_name: str, limit: int = 10) -> list[dict]:
        """Retourne les <limit> sessions les plus récentes pour une tâche donnée."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, t.name, t.project,
                       s.started_at, s.ended_at,
                       s.duration_seconds, s.is_active, s.note
                FROM sessions s
                JOIN tasks t ON t.id = s.task_id
                WHERE t.name = ?
                ORDER BY s.started_at DESC
                LIMIT ?
                """,
                (task_name, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_last_active_session(self) -> dict | None:
        """
        Retourne la session marquée is_active=1 la plus récente,
        ou None s'il n'en existe pas.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.id, t.name, t.project,
                       s.started_at, s.duration_seconds
                FROM sessions s
                JOIN tasks t ON t.id = s.task_id
                WHERE s.is_active = 1
                ORDER BY s.started_at DESC
                LIMIT 1
                """,
            ).fetchone()
            return dict(row) if row else None

    def close_all_active_sessions(self) -> None:
        """Marque toutes les sessions actives comme terminées (nettoyage au démarrage)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET is_active = 0, ended_at = ? WHERE is_active = 1",
                (datetime.now().isoformat(),),
            )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def get_config(self, key: str, default: str = "") -> str:
        """Lit une valeur de configuration (retourne <default> si la clé n'existe pas)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_config(self, key: str, value: str) -> None:
        """Enregistre ou met à jour une valeur de configuration."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
