"""
Fenêtre overlay compacte.
Toujours au-dessus des autres fenêtres, sans barre de titre, absente de la barre des tâches.

Palette sombre fixe (indépendante du thème global).
Coins arrondis via wm_attributes("-transparentcolor").
Menu déroulant custom (_TaskDropdown) pour garder exactement le même style dark.
"""

import ctypes
import ctypes.wintypes as _wt
import tkinter as tk
import tkinter.font as tkfont
from typing import TYPE_CHECKING, Callable

import customtkinter as ctk


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize",    _wt.DWORD),
        ("rcMonitor", _wt.RECT),
        ("rcWork",    _wt.RECT),
        ("dwFlags",   _wt.DWORD),
    ]

def _monitor_work_area(x: int, y: int) -> _wt.RECT:
    """Retourne la zone de travail (hors taskbar) du moniteur le plus proche de (x, y)."""
    user32 = ctypes.windll.user32
    user32.MonitorFromPoint.restype = ctypes.c_void_p
    user32.MonitorFromPoint.argtypes = [_wt.POINT, _wt.DWORD]
    hmon = user32.MonitorFromPoint(_wt.POINT(x, y), 2)  # MONITOR_DEFAULTTONEAREST
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(info))
    return info.rcWork

from ..core.database import Database
from ..core.tag_utils import format_task_display, segment_text
from .icon import get_ctk_image, get_control_icons
from ..core.task_manager import TaskManager
from ..core.timer_engine import TimerEngine

if TYPE_CHECKING:
    from .note_window import NoteWindow


# Hauteur fixe de l'overlay en pixels
_HEIGHT = 30

# Seuil de collapse : en dessous → icône ▾ à la place du texte de tâche
_COLLAPSE_W     = 320
_COLLAPSE_MIN_W = 280   # largeur plancher (icône + timer + ▾ + boutons)

# Largeur minimale visible quand l'overlay est poussé hors de l'écran (icône + marge)
_MIN_VISIBLE = 40

# Labels spéciaux
_NEW_TASK_LABEL = "＋  Nouvelle tâche"
_IDLE_LABEL     = "aucune tâche"

from .theme import (
    TRANSPARENT  as _TRANSPARENT,
    FRAME_BG     as _FRAME_BG,
    DD_BG        as _DD_BG,
    ITEM_BG      as _ITEM_BG,
    ACCENT       as _ACCENT,
    ACCENT_BTN   as _ACCENT_BTN,
    ACCENT_HOVER as _ACCENT_HOVER,
    BTN_HOVER    as _BTN_HOVER,
    HANDLE_BG    as _HANDLE_BG,
    TEXT         as _TEXT,
    TEXT_DIM     as _TEXT_DIM,
    WARNING      as _WARNING,
    TAG_COLOR    as _TAG_COLOR,
)


# ══════════════════════════════════════════════════════════════════════
# Menu déroulant custom
# ══════════════════════════════════════════════════════════════════════

class _TaskDropdown(tk.Toplevel):
    """
    Popup de sélection de tâche, même palette que l'overlay.
    Créé sous le bouton déclencheur, fermé sur clic extérieur ou Échap.
    """

    def __init__(
        self,
        parent: tk.Toplevel,
        values: list[str],
        on_select: Callable[[str], None],
        x: int,
        y: int,
        width: int,
        on_dismiss: Callable[[str], None] | None = None,
    ):
        super().__init__(parent)
        self._on_select  = on_select
        self._on_dismiss = on_dismiss

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        self._build(values, width)

        row_h = 30
        total_h = len(values) * (row_h + 2) + 10
        self.geometry(f"{max(width, 160)}x{total_h}+{x}+{y}")

        self.bind("<Escape>", lambda e: self.destroy())
        self.after(10, self.deiconify)
        self.after(20, self.focus_set)
        self.after(30, lambda: self.bind("<FocusOut>", lambda e: self.after(80, self._maybe_close)))

    def _build(self, values: list[str], width: int) -> None:
        self._frame = ctk.CTkFrame(self, corner_radius=8, fg_color=_DD_BG)
        self._frame.pack(fill="both", expand=True)

        for value in values:
            is_special = value == _NEW_TASK_LABEL

            if is_special:
                ctk.CTkButton(
                    self._frame,
                    text=value,
                    anchor="w",
                    height=30,
                    fg_color="transparent",
                    hover_color=_BTN_HOVER,
                    text_color=_TEXT_DIM,
                    font=ctk.CTkFont(size=14),
                    corner_radius=4,
                    command=lambda v=value: self._select(v),
                ).pack(fill="x", padx=4, pady=1)
                continue

            # Ligne tâche : segments inline + [×]
            row = tk.Frame(self._frame, bg=_DD_BG)
            row.pack(fill="x", padx=4, pady=1)

            if self._on_dismiss is not None:
                ctk.CTkButton(
                    row,
                    text="×",
                    width=28,
                    height=30,
                    fg_color="transparent",
                    hover_color="#4a1a1a",
                    text_color=_TEXT_DIM,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    corner_radius=4,
                    command=lambda r=row, v=value: self._dismiss(r, v),
                ).pack(side="right")

            row_labels: list[tk.Widget] = [row]
            for seg, is_tag in segment_text(value):
                if not seg:
                    continue
                fg   = _TAG_COLOR if is_tag else _TEXT
                font = ("Segoe UI", 12, "italic") if is_tag else ("Segoe UI", 13)
                lbl  = tk.Label(row, text=seg, fg=fg, bg=_DD_BG, font=font, cursor="hand2")
                lbl.pack(side="left")
                lbl.bind("<ButtonPress-1>", lambda e, v=value: self._select(v))
                row_labels.append(lbl)

            filler = tk.Label(row, text="", bg=_DD_BG)
            filler.pack(side="left", fill="x", expand=True)
            filler.bind("<ButtonPress-1>", lambda e, v=value: self._select(v))
            row_labels.append(filler)

            self._add_hover(row_labels)

    @staticmethod
    def _add_hover(widgets: list) -> None:
        """Effet hover sur un groupe de widgets tk."""
        def on_enter(e):
            for w in widgets:
                try:
                    w.configure(bg=_BTN_HOVER)
                except Exception:
                    pass
        def on_leave(e):
            for w in widgets:
                try:
                    w.configure(bg=_DD_BG)
                except Exception:
                    pass
        for w in widgets:
            w.bind("<Enter>", on_enter, add=True)
            w.bind("<Leave>", on_leave, add=True)

    def _select(self, value: str) -> None:
        self.destroy()
        self._on_select(value)

    def _dismiss(self, row_frame: tk.Frame, task_name: str) -> None:
        """Masque la tâche et retire sa ligne sans fermer le dropdown."""
        if self._on_dismiss:
            self._on_dismiss(task_name)
        row_h = row_frame.winfo_height() + 2   # +2 = pady haut+bas
        row_frame.destroy()
        new_h = max(40, self.winfo_height() - row_h)
        self.geometry(f"{self.winfo_width()}x{new_h}+{self.winfo_x()}+{self.winfo_y()}")

    def _maybe_close(self) -> None:
        try:
            focused = self.focus_get()
        except tk.TclError:
            self.destroy()
            return
        if focused is not None:
            try:
                if focused.winfo_toplevel() is self:
                    return
            except tk.TclError:
                pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════
# Overlay principal
# ══════════════════════════════════════════════════════════════════════

class Overlay(tk.Toplevel):
    """
    Fenêtre flottante compacte affichant la tâche en cours et le timer.
    Boutons ▶/⏸ et ⏹ icône seule (fg transparent, pas de cadre).
    """

    def __init__(
        self,
        parent: ctk.CTk,
        task_manager: TaskManager,
        timer_engine: TimerEngine,
        database: Database,
        on_open_main: Callable,
        on_stop_requested: Callable | None = None,
    ):
        super().__init__(parent)

        self._task_manager = task_manager
        self._timer = timer_engine
        self._db = database
        self._on_open_main = on_open_main
        self._on_stop_requested = on_stop_requested

        # État interne
        self._drag_x  = self._drag_y  = 0
        self._drag_sx = self._drag_sy = 0
        self._drag_active = False
        self._resize_x = 0
        self._resize_w = int(self._db.get_config("overlay_width", "340"))
        self._current_task      = _IDLE_LABEL   # chaîne d'affichage (= nom brut)
        self._current_task_name = ""            # même valeur, pour comparaison tick
        self._task_map: dict[str, dict] = {}    # display_str → task dict
        self._note_win: "NoteWindow | None" = None
        self._dropdown: "_TaskDropdown | None" = None
        # Mémorise le dernier état connu pour éviter les configure() redondants
        self._ctrl_running = False
        self._ctrl_paused  = False
        self._collapsed    = False
        self._tooltip_id:  str | None = None
        self._tooltip_win: tk.Toplevel | None = None

        # --- Configuration fenêtre ---
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        ox = int(self._db.get_config("overlay_x", "100"))
        oy = int(self._db.get_config("overlay_y", "100"))
        ox, oy = self._clamp_pos(ox, oy)
        self.geometry(f"{self._resize_w}x{_HEIGHT}+{ox}+{oy}")
        self.resizable(True, False)
        self.minsize(_COLLAPSE_MIN_W, _HEIGHT)

        self._icons = get_control_icons(14)

        self._build_ui()
        self._refresh_task_list()
        if self._resize_w < _COLLAPSE_W:
            self._set_collapsed(True)
        self.after(10, self.deiconify)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._bg = ctk.CTkFrame(self, corner_radius=10, fg_color=_FRAME_BG)
        self._bg.pack(fill="both", expand=True)

        # -- Icône chronomètre : drag --
        icon_img = get_ctk_image(size=20)
        icon_lbl = ctk.CTkLabel(
            self._bg, image=icon_img, text="", width=28, cursor="hand2",
        )
        icon_lbl.pack(side="left", padx=(8, 2))
        self.bind("<ButtonPress-1>",   self._drag_start)
        self.bind("<B1-Motion>",       self._drag_motion)
        self.bind("<ButtonRelease-1>", self._drag_end)
        icon_lbl._img = icon_img

        # ── Éléments droite (du plus à droite au plus à gauche) ──

        # Poignée resize
        handle = tk.Frame(self._bg, width=6, cursor="size_we", bg=_HANDLE_BG)
        handle.pack(side="right", fill="y")
        handle.pack_propagate(False)
        handle.bind("<ButtonPress-1>",   lambda e: (self._resize_start(e), "break")[1])
        handle.bind("<B1-Motion>",       lambda e: (self._resize_motion(e), "break")[1])
        handle.bind("<ButtonRelease-1>", lambda e: (self._resize_end(e),   "break")[1])

        # Bouton note — icône Pillow, fond transparent
        self._note_btn = ctk.CTkButton(
            self._bg, text="", image=self._icons["note_dim"],
            width=24, height=_HEIGHT - 10,
            fg_color="transparent",
            hover_color=_BTN_HOVER,
            corner_radius=6,
            state="disabled",
            command=self._toggle_note,
        )
        self._note_btn.pack(side="right", padx=(0, 2))

        # Bouton stop ⏹ — icône Pillow, fond transparent
        self._stop_btn = ctk.CTkButton(
            self._bg, text="", image=self._icons["stop_dim"],
            width=24, height=_HEIGHT - 10,
            fg_color="transparent",
            hover_color=_BTN_HOVER,
            corner_radius=6,
            state="disabled",
            command=self._on_stop_btn,
        )
        self._stop_btn.pack(side="right", padx=(0, 2))

        # Bouton play/pause — icône Pillow, fond transparent
        self._play_btn = ctk.CTkButton(
            self._bg, text="", image=self._icons["play_dim"],
            width=24, height=_HEIGHT - 10,
            fg_color="transparent",
            hover_color=_BTN_HOVER,
            corner_radius=6,
            state="disabled",
            command=self._on_play_pause,
        )
        self._play_btn.pack(side="right", padx=(0, 2))

        # ── Timer ──

        self._timer_lbl = ctk.CTkLabel(
            self._bg,
            text="",
            font=ctk.CTkFont(size=15, weight="bold"),
            width=84,
            anchor="center",
            text_color=_TEXT,
        )
        self._timer_lbl.pack(side="left", padx=(2, 0))

        # ── Bouton collapse ▾ (remplace _center quand overlay trop étroit) ──

        self._collapse_btn = ctk.CTkButton(
            self._bg,
            text="", image=self._icons["collapse"],
            width=24, height=_HEIGHT - 10,
            fg_color="transparent",
            hover_color=_BTN_HOVER,
            corner_radius=6,
            command=self._open_dropdown,
        )
        self._collapse_btn.bind("<Enter>", self._schedule_tooltip)
        self._collapse_btn.bind("<Leave>", self._cancel_tooltip)

        # Filler transparent cliquable qui comble l'espace entre _collapse_btn et les boutons droite
        self._collapse_filler = tk.Frame(self._bg, bg=_FRAME_BG, cursor="hand2")
        self._collapse_filler.bind("<ButtonPress-1>", lambda e: self._open_dropdown())
        self._collapse_filler.bind("<Enter>", self._schedule_tooltip)
        self._collapse_filler.bind("<Leave>", self._cancel_tooltip)
        # Non packés initialement — gérés par _set_collapsed

        # ── Zone centrale : rangée tâche ↔ Entry nouvelle tâche ──

        self._center = ctk.CTkFrame(self._bg, fg_color="transparent")
        self._center.pack(side="left", fill="x", expand=True)

        # Rangée nom avec segments inline (permutée avec l'entry en mode saisie)
        self._task_row = tk.Frame(self._center, bg=_FRAME_BG)
        self._task_row.pack(fill="x", expand=True)
        # Remplie dynamiquement par _set_task_display

        # Entry saisie nouvelle tâche (masquée par défaut)
        self._new_task_entry = ctk.CTkEntry(
            self._center,
            placeholder_text="Nom de la tâche…",
            height=30,
            fg_color=_ITEM_BG,
            border_color=_ACCENT,
            border_width=2,
            text_color=_TEXT,
            placeholder_text_color=_TEXT_DIM,
        )
        self._new_task_entry.bind("<Return>", self._on_new_task_confirm)
        self._new_task_entry.bind("<Escape>", self._on_new_task_cancel)

    # ------------------------------------------------------------------
    # Menu déroulant custom
    # ------------------------------------------------------------------

    def _open_dropdown(self) -> None:
        """Ouvre le popup de sélection, ou le ferme s'il est déjà visible (toggle)."""
        if self._dropdown is not None and self._dropdown.winfo_exists():
            self._dropdown.destroy()
            self._dropdown = None
            return

        tasks = self._task_manager.get_recent_tasks()
        current_name = self._current_task_name if self._timer.is_running else None
        current_tags = self._timer.current_tags if self._timer.is_running else ""

        self._task_map = {}
        display_items: list[str] = []
        for t in tasks:
            display = format_task_display(t["name"], t.get("tags", ""))
            if t["name"] == current_name and t.get("tags", "") == current_tags:
                continue
            self._task_map[display] = t
            display_items.append(display)

        values = [_NEW_TASK_LABEL] + display_items

        # Largeur : max(overlay, contenu le plus long)
        try:
            _f = tkfont.Font(family="Segoe UI", size=13)
            content_w = max((_f.measure(v) + 80 for v in values), default=160)
        except Exception:
            content_w = 160
        bw = max(self.winfo_width(), content_w)

        # Hauteur estimée du dropdown (même formule que _TaskDropdown)
        dd_h = len(values) * 32 + 10

        # Position X = bord gauche de l'overlay
        bx = self.winfo_rootx()
        anchor_y = (self._collapse_btn if self._collapsed else self._task_row).winfo_rooty()
        below_y  = anchor_y + _HEIGHT + 2
        above_y  = anchor_y - dd_h - 2

        work = _monitor_work_area(bx + bw // 2, below_y)
        by = below_y if (work.bottom - below_y) >= dd_h else above_y

        self._dropdown = _TaskDropdown(
            self, values, self._on_task_selected, bx, by, bw,
            on_dismiss=self._on_task_dismissed,
        )

    # ------------------------------------------------------------------
    # Affichage de la tâche courante (segments inline)
    # ------------------------------------------------------------------

    def _set_task_display(self, name: str, tags_str: str = "") -> None:
        """Recrée les labels inline dans _task_row pour le nom de tâche."""
        self._cancel_tooltip()
        self._current_task_name = name
        self._current_task = name   # display = nom brut (tags inline)

        for w in self._task_row.winfo_children():
            w.destroy()

        if name == _IDLE_LABEL:
            lbl = tk.Label(
                self._task_row, text=_IDLE_LABEL,
                fg=_TEXT_DIM, bg=_FRAME_BG,
                font=("Segoe UI", 13), cursor="hand2",
            )
            lbl.pack(side="left", padx=(8, 4))
            lbl.bind("<ButtonPress-1>", lambda e: self._open_dropdown())
        else:
            first = True
            for seg, is_tag in segment_text(name):
                if not seg:
                    continue
                if is_tag:
                    lbl = tk.Label(
                        self._task_row, text=seg,
                        fg=_TAG_COLOR, bg=_FRAME_BG,
                        font=("Segoe UI", 12, "italic"), cursor="hand2",
                    )
                else:
                    lbl = tk.Label(
                        self._task_row, text=seg,
                        fg=_TEXT, bg=_FRAME_BG,
                        font=("Segoe UI", 13), cursor="hand2",
                    )
                lbl.pack(side="left", padx=(8, 0) if first else (0, 0))
                lbl.bind("<ButtonPress-1>", lambda e: self._open_dropdown())
                first = False

            # Filler pour que toute la zone soit cliquable
            filler = tk.Label(self._task_row, text="", bg=_FRAME_BG, cursor="hand2")
            filler.pack(side="left", fill="x", expand=True)
            filler.bind("<ButtonPress-1>", lambda e: self._open_dropdown())

    def _schedule_tooltip(self, event: tk.Event) -> None:
        self._cancel_tooltip()
        self._tooltip_id = self.after(300, self._show_tooltip)

    def _cancel_tooltip(self, event=None) -> None:
        if self._tooltip_id:
            self.after_cancel(self._tooltip_id)
            self._tooltip_id = None
        if self._tooltip_win and self._tooltip_win.winfo_exists():
            self._tooltip_win.destroy()
            self._tooltip_win = None

    def _show_tooltip(self) -> None:
        if not self._current_task_name or self._current_task_name == _IDLE_LABEL:
            return
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=_TRANSPARENT)
        win.wm_attributes("-transparentcolor", _TRANSPARENT)
        self._tooltip_win = win

        bg = ctk.CTkFrame(win, corner_radius=8, fg_color=_FRAME_BG)
        bg.pack(padx=0, pady=0)

        row = tk.Frame(bg, bg=_FRAME_BG)
        row.pack(padx=10, pady=6)
        first = True
        for seg, is_tag in segment_text(self._current_task_name):
            if not seg:
                continue
            color = _TAG_COLOR if is_tag else _TEXT
            font  = ("Segoe UI", 12, "italic") if is_tag else ("Segoe UI", 12)
            tk.Label(row, text=seg, fg=color, bg=_FRAME_BG, font=font).pack(
                side="left", padx=(4 if first else 0, 0)
            )
            first = False

        win.update_idletasks()
        tw = win.winfo_reqwidth()
        th = win.winfo_reqheight()
        ox, oy = self.winfo_x(), self.winfo_y()
        ow = self.winfo_width()
        win.geometry(f"+{ox + (ow - tw) // 2}+{oy - th - 4}")

    # ------------------------------------------------------------------
    # Boutons play/pause et stop
    # ------------------------------------------------------------------

    def _on_play_pause(self) -> None:
        if not self._timer.is_running:
            return
        is_paused = self._timer.toggle_pause()
        self._update_control_buttons(running=True, paused=is_paused)

    def _on_stop_btn(self) -> None:
        if self._on_stop_requested:
            self._on_stop_requested()
        else:
            self._task_manager.stop_task()
        self._on_stopped()

    def _update_control_buttons(self, running: bool, paused: bool) -> None:
        """
        Met à jour l'état des boutons et la couleur du timer.
        Évite les configure() redondants en mémorisant le dernier état connu.
        """
        if running == self._ctrl_running and paused == self._ctrl_paused:
            return
        self._ctrl_running = running
        self._ctrl_paused  = paused

        if running:
            # Timer : gris quand en pause, blanc quand actif
            self._timer_lbl.configure(text_color=_TEXT_DIM if paused else _TEXT)
            play_img = self._icons["play"] if paused else self._icons["pause"]
            self._play_btn.configure(image=play_img, state="normal")
            self._stop_btn.configure(image=self._icons["stop"], state="normal")
            self._note_btn.configure(image=self._icons["note"], state="normal")
        else:
            self._timer_lbl.configure(text_color=_TEXT)
            self._play_btn.configure(image=self._icons["play_dim"], state="disabled")
            self._stop_btn.configure(image=self._icons["stop_dim"], state="disabled")
            self._note_btn.configure(image=self._icons["note_dim"], state="disabled")

    # ------------------------------------------------------------------
    # Fenêtre de note (toggle)
    # ------------------------------------------------------------------

    def _toggle_note(self) -> None:
        if self._note_win is not None and self._note_win.winfo_exists():
            self._note_win.destroy()
            self._note_win = None
            return
        from .note_window import NoteWindow
        self._note_win = NoteWindow(self, self._task_manager)

    # ------------------------------------------------------------------
    # Mode saisie nouvelle tâche
    # ------------------------------------------------------------------

    def _show_entry_mode(self) -> None:
        self._task_row.pack_forget()
        self._new_task_entry.pack(fill="x", expand=True)
        self._new_task_entry.delete(0, "end")
        self._new_task_entry.focus_set()

    def _show_task_mode(self) -> None:
        self._new_task_entry.pack_forget()
        self._task_row.pack(fill="x", expand=True)

    def _on_new_task_confirm(self, event=None) -> None:
        raw = self._new_task_entry.get().strip()
        self._show_task_mode()
        if not raw:
            return
        try:
            self._task_manager.start_task(raw, "")
        except ValueError:
            pass
        self._refresh_task_list()

    def _on_new_task_cancel(self, event=None) -> None:
        self._show_task_mode()

    # ------------------------------------------------------------------
    # Gestion de la sélection de tâche
    # ------------------------------------------------------------------

    def _refresh_task_list(self) -> None:
        """Synchronise l'affichage avec l'état courant du timer."""
        if self._timer.is_running:
            name, _ = self._timer.current_task
            self._set_task_display(name, self._timer.current_tags)
        else:
            self._set_task_display(_IDLE_LABEL)
            self._update_control_buttons(running=False, paused=False)

    def _on_task_dismissed(self, display: str) -> None:
        """Masque la tâche en base ; elle disparaît du dropdown à la prochaine ouverture."""
        task = self._task_map.get(display)
        if task:
            self._task_manager.hide_task(task["id"])

    def _on_task_selected(self, value: str) -> None:
        if value == _NEW_TASK_LABEL:
            self._show_entry_mode()
            return
        task = self._task_map.get(value)
        if task is None:
            return
        try:
            self._task_manager.start_known_task(
                task["name"], task.get("project", ""), task.get("tags", "")
            )
        except ValueError:
            pass
        self._refresh_task_list()

    # ------------------------------------------------------------------
    # Mise à jour depuis le thread timer
    # ------------------------------------------------------------------

    def on_timer_tick(self, elapsed: int, task_name: str, project: str) -> None:
        self.after(0, self._update_display, elapsed, task_name)

    def _update_display(self, elapsed: int, task_name: str) -> None:
        self._timer_lbl.configure(text=TimerEngine.format_elapsed(elapsed))
        expected = format_task_display(task_name, self._timer.current_tags)
        if self._current_task != expected:
            self._set_task_display(task_name, self._timer.current_tags)
        self._update_control_buttons(running=True, paused=False)

    def on_task_stopped(self) -> None:
        self.after(0, self._on_stopped)

    def _on_stopped(self) -> None:
        self._timer_lbl.configure(text="")
        self._current_task_name = ""
        self._set_task_display(_IDLE_LABEL)
        self._update_control_buttons(running=False, paused=False)

    def notify_task_list_changed(self) -> None:
        self.after(0, self._refresh_task_list)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x    = event.x_root - self.winfo_x()
        self._drag_y    = event.y_root - self.winfo_y()
        self._drag_sx   = event.x_root
        self._drag_sy   = event.y_root
        self._drag_active = False

    def _drag_motion(self, event: tk.Event) -> None:
        if not self._drag_active:
            if abs(event.x_root - self._drag_sx) > 5 or abs(event.y_root - self._drag_sy) > 5:
                self._drag_active = True
            else:
                return
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _clamp_pos(self, x: int, y: int) -> tuple[int, int]:
        w = self.winfo_width()
        r = _monitor_work_area(x + w // 2, y + _HEIGHT // 2)
        cx = max(r.left - w + _MIN_VISIBLE, min(x, r.right  - _MIN_VISIBLE))
        cy = max(r.top,                     min(y, r.bottom - _HEIGHT))
        return cx, cy

    def _drag_end(self, event: tk.Event) -> None:
        if self._drag_active:
            x, y = self._clamp_pos(self.winfo_x(), self.winfo_y())
            self.geometry(f"+{x}+{y}")
            self._db.set_config("overlay_x", str(x))
            self._db.set_config("overlay_y", str(y))
        self._drag_active = False

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def _resize_start(self, event: tk.Event) -> None:
        self._resize_x = event.x_root
        self._resize_w = self.winfo_width()

    def _set_collapsed(self, collapsed: bool) -> None:
        """Bascule entre mode texte tâche et icône ▾ selon la largeur."""
        self._collapsed = collapsed
        if collapsed:
            if self._new_task_entry.winfo_ismapped():
                self._show_task_mode()
            self._center.pack_forget()
            self._collapse_btn.pack(side="left")
            self._collapse_filler.pack(side="left", fill="x", expand=True)
        else:
            self._collapse_btn.pack_forget()
            self._collapse_filler.pack_forget()
            self._center.pack(side="left", fill="x", expand=True)

    def _resize_motion(self, event: tk.Event) -> None:
        new_w = max(_COLLAPSE_MIN_W, self._resize_w + event.x_root - self._resize_x)
        self.geometry(f"{new_w}x{_HEIGHT}")
        should_collapse = new_w < _COLLAPSE_W
        if should_collapse != self._collapsed:
            self._set_collapsed(should_collapse)

    def _resize_end(self, event: tk.Event) -> None:
        self._db.set_config("overlay_width", str(self.winfo_width()))
