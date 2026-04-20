"""
Fenêtre principale de TimeTrackR.
Historique par jour avec tâches/sessions expandables (animation fluide),
icônes ▶/⏸ sur la tâche en cours.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
from datetime import date, datetime, timedelta
from typing import Callable

import customtkinter as ctk

from ..core.database import Database
from ..core.tag_utils import format_task_display, segment_text
from .icon import apply_icon_to_window, get_app_icons, get_ctk_image
from .theme import TAG_COLOR as _TAG_COLOR
from ..core.task_manager import TaskManager
from ..core.timer_engine import TimerEngine


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Constantes de style ───────────────────────────────────────────────

_FONT_DAY     = 18   # en-têtes de jours (le plus grand)
_FONT_TASK    = 15   # noms de tâches
_FONT_SESSION = 11   # détails de session (le plus petit, inchangé)

_PAD_TASK    = (14, 4)
_PAD_SESSION = (12, 4)

# Bg de la TaskRow (doit correspondre à fg_color=("gray84","gray22"))
_ROW_BG  = {"Dark": "#383838", "Light": "#D6D6D6"}
_DAY_BG  = {"Dark": "#1e1e1e", "Light": "#ebebeb"}


# ── Utilitaires ───────────────────────────────────────────────────────

_MOIS  = ["janvier","février","mars","avril","mai","juin",
          "juillet","août","septembre","octobre","novembre","décembre"]
_JOURS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]


def _format_date(date_str: str) -> str:
    d = date.fromisoformat(date_str)
    today = date.today()
    delta = (today - d).days
    if delta == 0:
        return "Aujourd'hui"
    if delta == 1:
        return "Hier"
    if delta < 7:
        return _JOURS[d.weekday()]
    return f"{d.day} {_MOIS[d.month - 1]} {d.year}"


def _format_time(dt_str: str | None) -> str:
    if not dt_str:
        return "–"
    try:
        return datetime.fromisoformat(dt_str).strftime("%Hh%M")
    except (ValueError, TypeError):
        return "–"


def _group_by_day(sessions: list[dict]) -> dict[str, dict]:
    days: dict[str, dict] = {}
    for s in sessions:
        day = s["started_at"][:10]
        if day not in days:
            days[day] = {}
        # Clé composite : même nom + tags différents = tâches distinctes
        key = (s["name"], s.get("tags", ""))
        if key not in days[day]:
            days[day][key] = {
                "name":       s["name"],
                "project":    s["project"],
                "tags":       s.get("tags", ""),
                "sessions":   [],
                "has_active": False,
            }
        days[day][key]["sessions"].append(s)
        if s["is_active"]:
            days[day][key]["has_active"] = True
    return days


# ══════════════════════════════════════════════════════════════════════
# Frame scrollable avec ascenseur auto-masqué
# ══════════════════════════════════════════════════════════════════════

class _AutoScrollFrame(tk.Frame):
    """
    Frame scrollable — ascenseur visible uniquement si le contenu dépasse.
    Hérite de tk.Frame (pas CTkFrame) pour éviter les restrictions bind_all de CTk.
    Les widgets enfants sont placés dans self.inner.
    """

    _BG = {"Dark": "#2b2b2b", "Light": "#ebebeb"}

    def __init__(self, parent, fg_color=None, corner_radius=None, **kw):
        bg = self._BG[ctk.get_appearance_mode()]
        super().__init__(parent, bg=bg, **kw)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=bg)
        self._vsb    = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.inner   = tk.Frame(self._canvas, bg=bg)

        self._win = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._on_yscroll)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._vsb.grid_remove()

        self.inner.bind(
            "<Configure>",
            lambda e: self.after_idle(
                lambda: self._canvas.configure(scrollregion=self._canvas.bbox("all"))
            ),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._win, width=e.width),
        )

        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _on_yscroll(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._vsb.grid_remove()
        else:
            self._vsb.grid()
        self._vsb.set(first, last)

    def sync_bg(self) -> None:
        bg = self._BG[ctk.get_appearance_mode()]
        self.configure(bg=bg)
        self._canvas.configure(bg=bg)
        try:
            self.inner.configure(bg=bg)
        except tk.TclError:
            pass

    def _bind_wheel(self, _e) -> None:
        self.bind_all("<MouseWheel>", self._wheel)

    def _unbind_wheel(self, _e) -> None:
        self.unbind_all("<MouseWheel>")

    def _wheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ══════════════════════════════════════════════════════════════════════
# Dialogue de démarrage de tâche
# ══════════════════════════════════════════════════════════════════════

class _StartTaskDialog(ctk.CTkToplevel):
    """Petite fenêtre modale pour sélectionner/créer et démarrer une tâche."""

    def __init__(
        self,
        parent: ctk.CTk,
        task_manager: TaskManager,
        on_started: Callable[[str, str], None],
        icons: dict,
    ):
        super().__init__(parent)
        self.title("Démarrer une tâche")
        self.geometry("340x230")
        self.resizable(False, False)
        self.grab_set()

        self._task_manager = task_manager
        self._on_started   = on_started
        self._icons        = icons

        self._recent_tasks = task_manager.get_recent_tasks()
        display_names = [
            format_task_display(t["name"], t.get("tags", ""))
            for t in self._recent_tasks
        ]

        ctk.CTkLabel(self, text="Tâche", anchor="w").pack(fill="x", padx=16, pady=(16, 2))
        self._task_var = tk.StringVar()
        self._task_cb  = ctk.CTkComboBox(
            self, variable=self._task_var,
            values=display_names,
            command=self._on_task_changed,
        )
        self._task_cb.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Projet (optionnel)", anchor="w").pack(fill="x", padx=16, pady=(0, 2))
        self._proj_var = tk.StringVar()
        self._proj_cb  = ctk.CTkComboBox(
            self, variable=self._proj_var,
            values=task_manager.get_recent_projects(),
        )
        self._proj_cb.pack(fill="x", padx=16, pady=(0, 16))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(
            btns, text="Annuler",
            fg_color="transparent", border_width=1,
            border_color=("gray60", "gray50"),
            hover_color=("gray80", "gray30"),
            command=self.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(
            btns, text="  Démarrer", image=self._icons["start_play"], compound="left",
            fg_color="#2563eb", hover_color="#1d4ed8", text_color="white",
            command=self._confirm,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.bind("<Return>", lambda e: self._confirm())
        self.after(50, self._task_cb.focus_set)

    def _on_task_changed(self, value: str) -> None:
        if self._proj_var.get():
            return
        match = next(
            (t for t in self._recent_tasks
             if format_task_display(t["name"], t.get("tags", "")) == value),
            None,
        )
        if match and match["project"]:
            self._proj_var.set(match["project"])

    def _confirm(self) -> None:
        raw     = self._task_var.get().strip()
        project = self._proj_var.get().strip()
        if not raw:
            return
        self.destroy()
        self._on_started(raw, project)


# ══════════════════════════════════════════════════════════════════════
# Ligne de session individuelle
# ══════════════════════════════════════════════════════════════════════

class _SessionRow(tk.Frame):
    """
    Ligne de session en widgets tk purs (pas CTk) pour une instanciation rapide —
    critique pour que l'animation expand ne freeze pas.
    """

    _PALETTE = {
        "Dark":  {"bg": "#2e2e2e", "fg": "#94a3b8",
                  "active": "#4ade80", "note": "#64748b"},
        "Light": {"bg": "#e8e8e8", "fg": "#475569",
                  "active": "#16a34a", "note": "#94a3b8"},
    }
    _FONT    = ("Segoe UI", _FONT_SESSION)
    _FONT_SM = ("Segoe UI", _FONT_SESSION - 1)

    def __init__(self, parent, session: dict, icons: dict):
        c = self._PALETTE[ctk.get_appearance_mode()]
        super().__init__(parent, bg=c["bg"])

        start    = _format_time(session["started_at"])
        has_note = bool(session.get("note"))

        if session["is_active"]:
            end_text = "en cours"
            end_fg   = c["active"]
        else:
            if session["ended_at"]:
                end_text = _format_time(session["ended_at"])
            else:
                # Estimation depuis started_at + duration (session non fermée proprement)
                try:
                    dt_end = datetime.fromisoformat(session["started_at"]) + timedelta(
                        seconds=session["duration_seconds"]
                    )
                    end_text = dt_end.strftime("%Hh%M")
                except (ValueError, TypeError):
                    end_text = "–"
            end_fg = c["fg"]

        tk.Label(
            self, text=f"{start} → {end_text}",
            bg=c["bg"], fg=end_fg, font=self._FONT, anchor="w",
        ).pack(side="left", padx=(8, 4), pady=(4, 0 if has_note else 4))

        tk.Label(
            self, text=TimerEngine.format_elapsed(session["duration_seconds"]),
            bg=c["bg"], fg=c["fg"], font=self._FONT, anchor="e",
        ).pack(side="right", padx=8, pady=4)

        if has_note:
            note  = session["note"]
            short = note if len(note) <= 60 else note[:57] + "…"
            ctk.CTkLabel(
                self,
                image=icons["session_note"],
                text=f"  {short}",
                compound="left",
                fg_color=c["bg"],
                font=ctk.CTkFont(size=_FONT_SESSION - 1),
                text_color=c["note"],
                anchor="w",
                wraplength=340,
                justify="left",
            ).pack(fill="x", padx=8, pady=(0, 4))


# ══════════════════════════════════════════════════════════════════════
# Ligne de tâche (avec animation expand/collapse)
# ══════════════════════════════════════════════════════════════════════

class _TaskRow(tk.Frame):
    """
    Tâche : icône ▶/⏸ si active, durée totale.
    Clic sur la ligne → expand/collapse instantané.
    Double-clic sur le nom → démarrage immédiat.
    """

    def __init__(
        self,
        parent,
        task_name: str,
        project: str,
        tags: str,
        sessions: list[dict],
        status: str,            # "running" | "paused" | ""
        on_start_task: Callable,
        icons: dict,
    ):
        bg = _ROW_BG[ctk.get_appearance_mode()]
        super().__init__(parent, bg=bg)
        self._sessions        = sessions
        self._task_name       = task_name
        self._project         = project
        self._tags            = tags
        self._on_start        = on_start_task
        self._icons           = icons
        self._expanded        = False
        self._sessions_frame: tk.Frame | None = None

        total = sum(s["duration_seconds"] for s in sessions)

        # ── En-tête ───────────────────────────────────────────────────
        self._hdr = ctk.CTkFrame(self, fg_color=("gray84", "gray22"),
                                  corner_radius=6, cursor="hand2")
        self._hdr.pack(fill="x")

        # Durée totale (droite d'abord pour que le reste remplisse l'espace)
        ctk.CTkLabel(
            self._hdr,
            text=TimerEngine.format_elapsed(total),
            anchor="e",
            font=ctk.CTkFont(size=_FONT_TASK),
        ).pack(side="right", padx=(0, 8), pady=4)

        # Icône statut + nom (segments inline avec tags colorés)
        if status == "running":
            status_img, fg, weight = icons["row_running"], ("#22c55e", "#4ade80"), "bold"
        elif status == "paused":
            status_img, fg, weight = icons["row_paused"],  ("#f59e0b", "#fbbf24"), "bold"
        else:
            status_img, fg, weight = None,                 ("gray10", "gray90"),   "normal"

        mode = ctk.get_appearance_mode()
        normal_fg = fg[0] if mode == "Light" else fg[1]
        name_font = ("Segoe UI", _FONT_TASK, "bold") if weight == "bold" else ("Segoe UI", _FONT_TASK)
        tag_font  = ("Segoe UI", _FONT_TASK - 2, "italic")

        if status_img:
            ctk.CTkLabel(self._hdr, image=status_img, text="", width=16).pack(
                side="left", padx=(8, 0), pady=4
            )

        proj_suffix = f"  [{project}]" if project else ""
        full_name   = task_name + proj_suffix
        first = True
        name_labels: list[tk.Widget] = []
        for seg, is_tag in segment_text(full_name):
            if not seg:
                continue
            lbl_fg = _TAG_COLOR if is_tag else normal_fg
            font   = tag_font if is_tag else name_font
            padx   = ((0 if status_img else 8), 0) if first else (0, 0)
            lbl = tk.Label(self._hdr, text=seg, fg=lbl_fg, bg=bg, font=font)
            lbl.pack(side="left", padx=padx, pady=4)
            lbl.bind("<ButtonPress-1>", self._on_row_click)
            lbl.bind("<Double-Button-1>", lambda e: self._on_start(task_name, project, tags))
            name_labels.append(lbl)
            first = False

        # Clic simple → toggle sur l'en-tête (zone vide)
        self._hdr.bind("<ButtonPress-1>", self._on_row_click)

    # ── Clic ──────────────────────────────────────────────────────────

    def _on_row_click(self, event: tk.Event) -> None:
        self._toggle()

    # ── Animation expand / collapse ───────────────────────────────────

    def _toggle(self) -> None:
        if self._expanded:
            self._start_collapse()
        else:
            self._start_expand()

    def _start_expand(self) -> None:
        self._expanded = True
        if self._sessions_frame is None:
            bg = _ROW_BG[ctk.get_appearance_mode()]
            self._sessions_frame = tk.Frame(self, bg=bg)
            for s in self._sessions:
                _SessionRow(self._sessions_frame, s, self._icons).pack(
                    fill="x", padx=_PAD_SESSION, pady=1
                )
        self._sessions_frame.pack(fill="x", pady=(0, 4))

    def _start_collapse(self) -> None:
        self._expanded = False
        if self._sessions_frame is not None:
            self._sessions_frame.pack_forget()


# ══════════════════════════════════════════════════════════════════════
# Bloc journalier
# ══════════════════════════════════════════════════════════════════════

class _DayBlock(tk.Frame):
    """
    En-tête cliquable (date + total) + liste des tâches expandable.
    Déplié par défaut pour le jour en cours.
    """

    def __init__(
        self,
        parent,
        date_str: str,
        tasks: dict[tuple, dict],
        expanded: bool,
        is_today: bool,
        on_start_task: Callable,
        db: Database,
        timer: TimerEngine,
        icons: dict,
    ):
        super().__init__(parent, bg=_DAY_BG[ctk.get_appearance_mode()])
        self._tasks         = tasks
        self._is_today      = is_today
        self._on_start_task = on_start_task
        self._db            = db
        self._timer         = timer
        self._expanded      = expanded
        self._icons         = icons
        self._content: ctk.CTkFrame | None = None

        total = sum(
            sum(s["duration_seconds"] for s in info["sessions"])
            for info in tasks.values()
        )

        # ── En-tête ──────────────────────────────────────────────────
        hdr = ctk.CTkFrame(
            self, corner_radius=8,
            fg_color=("gray76", "#2e2e2e") if is_today else ("gray82", "#282828"),
        )
        hdr.pack(fill="x")
        hdr.bind("<ButtonPress-1>", lambda e: self._toggle())

        arrow_img = icons["chevron_down"] if expanded else icons["chevron_right"]
        self._arrow = ctk.CTkLabel(
            hdr, image=arrow_img, text="",
            width=18,
        )
        self._arrow.pack(side="left", padx=(8, 2), pady=8)
        self._arrow.bind("<ButtonPress-1>", lambda e: self._toggle())

        date_lbl = ctk.CTkLabel(
            hdr, text=_format_date(date_str),
            font=ctk.CTkFont(size=_FONT_DAY, weight="bold"),
            anchor="w",
        )
        date_lbl.pack(side="left", padx=4, pady=8)
        date_lbl.bind("<ButtonPress-1>", lambda e: self._toggle())

        if total > 0:
            tot_lbl = ctk.CTkLabel(
                hdr, text=TimerEngine.format_elapsed(total),
                font=ctk.CTkFont(size=_FONT_DAY - 2, weight="bold"),
                text_color=("gray30", "gray70"),
                anchor="e",
            )
            tot_lbl.pack(side="right", padx=12, pady=8)
            tot_lbl.bind("<ButtonPress-1>", lambda e: self._toggle())

        if expanded:
            self._build_content()

    def _toggle(self) -> None:
        if self._expanded:
            self._expanded = False
            self._arrow.configure(image=self._icons["chevron_right"])
            if self._content:
                self._content.destroy()
                self._content = None
        else:
            self._expanded = True
            self._arrow.configure(image=self._icons["chevron_down"])
            self._build_content()

    def _build_content(self) -> None:
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="x", pady=(2, 0))

        running_name: str | None = None
        running_tags: str = ""
        running_paused = False
        if self._timer.is_running:
            running_name, _ = self._timer.current_task
            running_tags     = self._timer.current_tags
            running_paused   = self._timer.is_paused

        for task_key, info in self._tasks.items():
            name, tags = task_key
            is_running = (
                info["has_active"]
                and name == running_name
                and tags == running_tags
            )
            status = ("paused" if running_paused else "running") if is_running else ""

            _TaskRow(
                self._content,
                task_name=name,
                project=info["project"],
                tags=tags,
                sessions=info["sessions"],
                status=status,
                on_start_task=self._on_start_task,
                icons=self._icons,
            ).pack(fill="x", padx=_PAD_TASK, pady=2)

        if self._is_today:
            ctk.CTkButton(
                self._content,
                text="  Nouvelle tâche…", image=self._icons["plus"], compound="left",
                height=30,
                anchor="w",
                fg_color=("gray84", "gray22"),
                hover_color=("gray74", "gray32"),
                text_color=("gray50", "gray55"),
                font=ctk.CTkFont(size=_FONT_TASK),
                corner_radius=6,
                command=self._on_start_task,
            ).pack(fill="x", padx=_PAD_TASK, pady=2)


# ══════════════════════════════════════════════════════════════════════
# Fenêtre principale
# ══════════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    """Fenêtre principale TimeTrackR — historique par jour."""

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
        self._timer        = timer_engine
        self._db           = database
        self._on_new_task_requested = on_new_task_requested
        self._on_quit_requested     = on_quit_requested
        self._settings_win = None
        self._drag_x = self._drag_y = 0

        self._app_icons = get_app_icons()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self._refresh_history()
        self._apply_theme()

        self.withdraw()
        self.after(100, lambda: apply_icon_to_window(self))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.title("TimeTrackR")
        self.geometry("500x640")
        self.minsize(400, 480)
        self.resizable(True, True)

        # ── En-tête ──────────────────────────────────────────────────
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(fill="x")
        self._bind_drag(header)

        icon_img = get_ctk_image(size=22)
        ctk.CTkLabel(header, image=icon_img, text="").pack(side="left", padx=(12, 4), pady=10)
        ctk.CTkLabel(
            header, text="TimeTrackR",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", pady=10)

        ctk.CTkButton(
            header, text="", image=self._app_icons["settings"],
            width=36, height=28,
            command=self.open_settings,
            fg_color="transparent", hover_color=("gray80", "gray30"),
        ).pack(side="right", padx=4, pady=10)

        self._theme_btn = ctk.CTkButton(
            header, text="", image=self._app_icons["sun"],
            width=36, height=28,
            command=self._toggle_theme,
            fg_color="transparent", hover_color=("gray80", "gray30"),
        )
        self._theme_btn.pack(side="right", padx=4, pady=10)

        ctk.CTkButton(
            header, text="", image=self._app_icons["refresh"],
            width=36, height=28,
            command=self._refresh_history,
            fg_color="transparent", hover_color=("gray80", "gray30"),
        ).pack(side="right", padx=4, pady=10)

        # ── Historique ────────────────────────────────────────────────
        self._history_scroll = _AutoScrollFrame(self)
        self._history_scroll.pack(fill="both", expand=True, padx=10, pady=(8, 10))

    # ------------------------------------------------------------------
    # Historique
    # ------------------------------------------------------------------

    def _refresh_history(self) -> None:
        for w in self._history_scroll.inner.winfo_children():
            w.destroy()

        sessions = self._db.get_history_sessions(days=30)
        days     = _group_by_day(sessions)

        today = date.today().isoformat()
        if today not in days:
            days = {today: {}, **days}

        for date_str, tasks in days.items():
            is_today = (date_str == today)
            _DayBlock(
                self._history_scroll.inner,
                date_str=date_str,
                tasks=tasks,
                expanded=is_today,
                is_today=is_today,
                on_start_task=self._request_start_task,
                db=self._db,
                timer=self._timer,
                icons=self._app_icons,
            ).pack(fill="x", pady=(0, 4))

    def refresh_sessions(self) -> None:
        self.after(0, self._refresh_history)

    # ------------------------------------------------------------------
    # Démarrage de tâche
    # ------------------------------------------------------------------

    def _request_start_task(self, name: str = "", project: str = "", tags: str = "") -> None:
        """Sans argument → dialogue. Avec nom+tags → démarrage direct (double-clic)."""
        if name:
            self._do_start_known_task(name, project, tags)
        else:
            _StartTaskDialog(self, self._task_manager, self._do_start_raw_task, self._app_icons)

    def _do_start_known_task(self, name: str, project: str, tags: str) -> None:
        """Démarrage direct depuis l'historique (tâche déjà identifiée)."""
        try:
            self._task_manager.start_known_task(name, project, tags)
        except ValueError:
            pass
        self.after(100, self._refresh_history)

    def _do_start_raw_task(self, raw: str, project: str) -> None:
        """Démarrage depuis la dialog (saisie brute, peut contenir des #tags)."""
        # Cherche si raw correspond à un display string connu
        tasks = self._task_manager.get_recent_tasks()
        match = next(
            (t for t in tasks if format_task_display(t["name"], t.get("tags", "")) == raw),
            None,
        )
        try:
            if match:
                self._task_manager.start_known_task(
                    match["name"], project or match["project"], match.get("tags", "")
                )
            else:
                self._task_manager.start_task(raw, project)
        except ValueError:
            pass
        self.after(100, self._refresh_history)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def _bind_drag(self, widget) -> None:
        widget.bind("<ButtonPress-1>", self._drag_start)
        widget.bind("<B1-Motion>",     self._drag_motion)

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_motion(self, event: tk.Event) -> None:
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Paramètres
    # ------------------------------------------------------------------

    def open_settings(self) -> None:
        from .settings_window import SettingsWindow
        if self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_force()
            return
        if not self.winfo_viewable():
            self.deiconify()
        self._settings_win = SettingsWindow(self, self._db)

    # ------------------------------------------------------------------
    # Thème
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        theme = self._db.get_config("theme", "dark")
        ctk.set_appearance_mode(theme)
        img = self._app_icons["moon"] if theme == "light" else self._app_icons["sun"]
        self._theme_btn.configure(image=img)
        self._history_scroll.sync_bg()

    def _toggle_theme(self) -> None:
        current  = ctk.get_appearance_mode()
        new_mode = "light" if current == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        img = self._app_icons["moon"] if new_mode == "light" else self._app_icons["sun"]
        self._theme_btn.configure(image=img)
        self._db.set_config("theme", new_mode)
        self._history_scroll.sync_bg()
        self._refresh_history()

    # ------------------------------------------------------------------
    # Callbacks publics (main.py)
    # ------------------------------------------------------------------

    def _on_stop(self) -> None:
        self.after(0, self._refresh_history)

    def _on_new_task(self) -> None:
        self.show()
        self.after(200, self._request_start_task)

    def restore_running_state(self) -> None:
        self.after(0, self._refresh_history)

    # ------------------------------------------------------------------
    # Visibilité / fermeture
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        if self._db.get_config("close_to_tray", "1") == "1":
            self.withdraw()
        elif self._on_quit_requested:
            self._on_quit_requested()

    def show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self._refresh_history()
