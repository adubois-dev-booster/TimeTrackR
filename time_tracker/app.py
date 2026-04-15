"""
Fenêtre principale de l'application (CustomTkinter).
Se ferme dans le tray ou quitte selon le paramètre "close_to_tray".
Toute mise à jour de l'UI depuis le thread timer passe par after().
"""

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from .database import Database
from .task_manager import TaskManager
from .timer_engine import TimerEngine


# Apparence par défaut
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    """Fenêtre principale CustomTkinter de TimeTrackR."""

    def __init__(
        self,
        task_manager: TaskManager,
        timer_engine: TimerEngine,
        database: Database,
        on_new_task_requested: Callable | None = None,
        on_quit_requested: Callable | None = None,
    ):
        super().__init__()

        self._task_manager = task_manager
        self._timer = timer_engine
        self._db = database
        self._on_new_task_requested = on_new_task_requested
        self._on_quit_requested = on_quit_requested

        # Référence vers la fenêtre paramètres (singleton)
        self._settings_win = None

        # Fermeture : vers tray ou quitter selon config
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._refresh_today_sessions()
        self._apply_theme()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construit tous les widgets de la fenêtre."""
        self.title("TimeTrackR")
        self.geometry("480x580")
        self.resizable(False, False)

        # ── En-tête ──────────────────────────────────────────────────
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            header, text="⏱  TimeTrackR",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left", padx=16, pady=12)

        # Bouton Paramètres
        ctk.CTkButton(
            header, text="⚙", width=36, height=28,
            command=self.open_settings,
            fg_color="transparent", hover_color=("gray80", "gray30"),
        ).pack(side="right", padx=4, pady=10)

        # Bouton Thème
        self._theme_btn = ctk.CTkButton(
            header, text="☀", width=36, height=28,
            command=self._toggle_theme,
            fg_color="transparent", hover_color=("gray80", "gray30"),
        )
        self._theme_btn.pack(side="right", padx=4, pady=10)

        # ── Saisie de la tâche ────────────────────────────────────────
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(form_frame, text="Tâche", anchor="w").pack(fill="x", padx=8, pady=(8, 0))

        self._task_var = tk.StringVar()
        self._task_entry = ctk.CTkComboBox(
            form_frame,
            variable=self._task_var,
            values=self._task_manager.get_recent_task_names(),
            width=440,
        )
        self._task_entry.pack(fill="x", padx=8, pady=(2, 4))

        ctk.CTkLabel(form_frame, text="Projet / catégorie", anchor="w").pack(fill="x", padx=8, pady=(4, 0))

        self._project_var = tk.StringVar()
        self._project_entry = ctk.CTkComboBox(
            form_frame,
            variable=self._project_var,
            values=self._task_manager.get_recent_projects(),
            width=440,
        )
        self._project_entry.pack(fill="x", padx=8, pady=(2, 8))

        # ── Affichage du timer ────────────────────────────────────────
        timer_frame = ctk.CTkFrame(self)
        timer_frame.pack(fill="x", padx=16, pady=4)

        self._timer_label = ctk.CTkLabel(
            timer_frame, text="00:00:00",
            font=ctk.CTkFont(size=52, weight="bold"),
        )
        self._timer_label.pack(pady=(16, 4))

        self._status_label = ctk.CTkLabel(
            timer_frame, text="En attente",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "gray60"),
        )
        self._status_label.pack(pady=(0, 12))

        # ── Boutons de contrôle ───────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=4)

        self._btn_start = ctk.CTkButton(
            btn_frame, text="▶  Démarrer", width=130,
            command=self._on_start,
            fg_color="#2563eb", hover_color="#1d4ed8",
        )
        self._btn_start.grid(row=0, column=0, padx=4, pady=4)

        self._btn_pause = ctk.CTkButton(
            btn_frame, text="⏸  Pause", width=110,
            command=self._on_pause,
            state="disabled",
            fg_color="#7c3aed", hover_color="#6d28d9",
        )
        self._btn_pause.grid(row=0, column=1, padx=4, pady=4)

        self._btn_stop = ctk.CTkButton(
            btn_frame, text="⏹  Arrêter", width=110,
            command=self._on_stop,
            state="disabled",
            fg_color="#dc2626", hover_color="#b91c1c",
        )
        self._btn_stop.grid(row=0, column=2, padx=4, pady=4)

        self._btn_new = ctk.CTkButton(
            btn_frame, text="＋  Nouvelle tâche", width=150,
            command=self._on_new_task,
            fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
            text_color=("gray10", "gray90"),
        )
        self._btn_new.grid(row=1, column=0, columnspan=3, pady=(4, 0), sticky="ew")
        btn_frame.columnconfigure((0, 1, 2), weight=1)

        # ── Sessions du jour ─────────────────────────────────────────
        today_frame = ctk.CTkFrame(self)
        today_frame.pack(fill="both", expand=True, padx=16, pady=(8, 12))

        ctk.CTkLabel(
            today_frame, text="Aujourd'hui",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 4))

        self._sessions_scroll = ctk.CTkScrollableFrame(today_frame, height=140)
        self._sessions_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ------------------------------------------------------------------
    # Callbacks boutons
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        """Démarre le timer pour la tâche saisie."""
        task_name = self._task_var.get().strip()
        project = self._project_var.get().strip()
        if not task_name:
            self._status_label.configure(text="⚠ Saisissez un nom de tâche", text_color="#f59e0b")
            return
        self._task_manager.start_task(task_name, project)
        self._update_button_states(running=True, paused=False)
        self._status_label.configure(text="En cours…", text_color=("#22c55e", "#4ade80"))
        self._task_entry.configure(values=self._task_manager.get_recent_task_names())
        self._project_entry.configure(values=self._task_manager.get_recent_projects())

    def _on_pause(self) -> None:
        """Bascule pause / reprise."""
        is_paused = self._timer.toggle_pause()
        self._btn_pause.configure(text="▶  Reprendre" if is_paused else "⏸  Pause")
        self._status_label.configure(
            text="En pause" if is_paused else "En cours…",
            text_color=("#f59e0b", "#fbbf24") if is_paused else ("#22c55e", "#4ade80"),
        )

    def _on_stop(self) -> None:
        """Arrête le timer."""
        self._task_manager.stop_task()
        self._timer_label.configure(text="00:00:00")
        self._update_button_states(running=False, paused=False)
        self._status_label.configure(text="Arrêté", text_color=("gray50", "gray60"))
        self._btn_pause.configure(text="⏸  Pause")
        self._refresh_today_sessions()

    def _on_new_task(self) -> None:
        """Arrête la tâche courante et vide les champs pour une nouvelle saisie."""
        if self._timer.is_running:
            self._task_manager.stop_task()
        self._task_var.set("")
        self._project_var.set("")
        self._timer_label.configure(text="00:00:00")
        self._update_button_states(running=False, paused=False)
        self._status_label.configure(text="En attente", text_color=("gray50", "gray60"))
        self._btn_pause.configure(text="⏸  Pause")
        self._refresh_today_sessions()
        if self._on_new_task_requested:
            self._on_new_task_requested()

    # ------------------------------------------------------------------
    # Paramètres (fenêtre séparée)
    # ------------------------------------------------------------------

    def open_settings(self) -> None:
        """Ouvre la fenêtre des paramètres (singleton : une seule instance à la fois)."""
        # Import local pour éviter la dépendance circulaire au niveau module
        from .settings_window import SettingsWindow

        if self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_force()
            return

        # S'assurer que la fenêtre principale est visible (requis pour transient)
        if not self.winfo_viewable():
            self.deiconify()

        self._settings_win = SettingsWindow(self, self._db)

    # ------------------------------------------------------------------
    # Mise à jour depuis le thread timer (via after())
    # ------------------------------------------------------------------

    def on_timer_tick(self, elapsed: int, task_name: str, project: str) -> None:
        """Reçoit le tick du timer engine (autre thread) et délègue à after()."""
        self.after(0, self._update_timer_display, elapsed)

    def _update_timer_display(self, elapsed: int) -> None:
        """Met à jour le label du timer (thread Tkinter uniquement)."""
        self._timer_label.configure(text=TimerEngine.format_elapsed(elapsed))

    # ------------------------------------------------------------------
    # Sessions du jour
    # ------------------------------------------------------------------

    def _refresh_today_sessions(self) -> None:
        """Recharge et affiche la liste des sessions du jour."""
        for widget in self._sessions_scroll.winfo_children():
            widget.destroy()

        sessions = self._db.get_today_sessions()
        if not sessions:
            ctk.CTkLabel(
                self._sessions_scroll,
                text="Aucune session aujourd'hui",
                text_color=("gray50", "gray60"),
            ).pack(padx=8, pady=8)
            return

        total_seconds = sum(s["duration_seconds"] for s in sessions)

        for s in sessions:
            row = ctk.CTkFrame(self._sessions_scroll)
            row.pack(fill="x", pady=2)

            nom = s["name"]
            proj = f" [{s['project']}]" if s["project"] else ""
            duree = TimerEngine.format_elapsed(s["duration_seconds"])
            statut = " ●" if s["is_active"] else ""

            ctk.CTkLabel(
                row, text=f"{nom}{proj}{statut}",
                anchor="w", font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=8, pady=4)
            ctk.CTkLabel(
                row, text=duree,
                anchor="e", font=ctk.CTkFont(size=12),
            ).pack(side="right", padx=8, pady=4)

        # Total du jour
        ctk.CTkFrame(self._sessions_scroll, height=1, fg_color=("gray70", "gray40")).pack(fill="x", pady=4)
        total_row = ctk.CTkFrame(self._sessions_scroll, fg_color="transparent")
        total_row.pack(fill="x")
        ctk.CTkLabel(total_row, text="Total", font=ctk.CTkFont(weight="bold"), anchor="w").pack(side="left", padx=8)
        ctk.CTkLabel(
            total_row,
            text=TimerEngine.format_elapsed(total_seconds),
            font=ctk.CTkFont(weight="bold"), anchor="e",
        ).pack(side="right", padx=8)

    def refresh_sessions(self) -> None:
        """Méthode publique pour forcer le rechargement depuis l'extérieur."""
        self.after(0, self._refresh_today_sessions)

    # ------------------------------------------------------------------
    # Thème
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        """Applique le thème sauvegardé en base."""
        theme = self._db.get_config("theme", "dark")
        ctk.set_appearance_mode(theme)
        self._theme_btn.configure(text="🌙" if theme == "light" else "☀")

    def _toggle_theme(self) -> None:
        """Bascule entre thème sombre et thème clair."""
        current = ctk.get_appearance_mode()
        new_mode = "light" if current == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self._theme_btn.configure(text="🌙" if new_mode == "light" else "☀")
        self._db.set_config("theme", new_mode)

    # ------------------------------------------------------------------
    # Visibilité / fermeture
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        """
        Réaction à la fermeture de la fenêtre (croix).
        Selon le paramètre 'close_to_tray' :
          - 1 (défaut) : masquer dans le tray
          - 0 : quitter l'application
        """
        if self._db.get_config("close_to_tray", "1") == "1":
            self.withdraw()
        else:
            if self._on_quit_requested:
                self._on_quit_requested()

    def show(self) -> None:
        """Affiche et met au premier plan la fenêtre principale."""
        self.deiconify()
        self.lift()
        self.focus_force()

    # ------------------------------------------------------------------
    # États des boutons
    # ------------------------------------------------------------------

    def _update_button_states(self, running: bool, paused: bool) -> None:
        """Active/désactive les boutons selon l'état du timer."""
        if running:
            self._btn_start.configure(state="disabled")
            self._btn_pause.configure(state="normal")
            self._btn_stop.configure(state="normal")
        else:
            self._btn_start.configure(state="normal")
            self._btn_pause.configure(state="disabled")
            self._btn_stop.configure(state="disabled")

    def restore_running_state(self, task_name: str, project: str) -> None:
        """
        Remet l'interface en état "en cours" après une reprise de session au démarrage.
        Appelé par main.py juste après resume_last_session().
        """
        self._task_var.set(task_name)
        self._project_var.set(project)
        self._update_button_states(running=True, paused=False)
        self._status_label.configure(text="En cours… (repris)", text_color=("#22c55e", "#4ade80"))
