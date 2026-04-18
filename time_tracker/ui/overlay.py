"""
Fenêtre overlay compacte.
Toujours au-dessus des autres fenêtres, sans barre de titre, absente de la barre des tâches.

Palette sombre fixe (indépendante du thème global).
Coins arrondis via wm_attributes("-transparentcolor").
Menu déroulant custom (_TaskDropdown) pour garder exactement le même style dark.
"""

import tkinter as tk
from typing import TYPE_CHECKING, Callable

import customtkinter as ctk

from ..core.database import Database
from .icon import get_ctk_image, get_control_icons
from ..core.task_manager import TaskManager
from ..core.timer_engine import TimerEngine

if TYPE_CHECKING:
    from .note_window import NoteWindow


# Hauteur fixe de l'overlay en pixels
_HEIGHT = 40

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
            if is_special or self._on_dismiss is None:
                # Entrée spéciale : bouton pleine largeur, pas de ×
                ctk.CTkButton(
                    self._frame,
                    text=value,
                    anchor="w",
                    height=30,
                    fg_color="transparent",
                    hover_color=_BTN_HOVER,
                    text_color=_TEXT_DIM if is_special else _TEXT,
                    font=ctk.CTkFont(size=14),
                    corner_radius=4,
                    command=lambda v=value: self._select(v),
                ).pack(fill="x", padx=4, pady=1)
            else:
                # Ligne tâche : [nom ────────────] [×]
                row = tk.Frame(self._frame, bg=_DD_BG)
                row.pack(fill="x", padx=4, pady=1)

                ctk.CTkButton(
                    row,
                    text=value,
                    anchor="w",
                    height=30,
                    fg_color="transparent",
                    hover_color=_BTN_HOVER,
                    text_color=_TEXT,
                    font=ctk.CTkFont(size=14),
                    corner_radius=4,
                    command=lambda v=value: self._select(v),
                ).pack(side="left", fill="x", expand=True)

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
        self._drag_x = self._drag_y = 0
        self._resize_x = 0
        self._resize_w = int(self._db.get_config("overlay_width", "340"))
        self._current_task = _IDLE_LABEL
        self._note_win: "NoteWindow | None" = None
        self._dropdown: "_TaskDropdown | None" = None
        # Mémorise le dernier état connu pour éviter les configure() redondants
        self._ctrl_running = False
        self._ctrl_paused  = False

        # --- Configuration fenêtre ---
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        ox = int(self._db.get_config("overlay_x", "100"))
        oy = int(self._db.get_config("overlay_y", "100"))
        self.geometry(f"{self._resize_w}x{_HEIGHT}+{ox}+{oy}")
        self.resizable(True, False)
        self.minsize(200, _HEIGHT)

        self._icons = get_control_icons(14)

        self._build_ui()
        self._refresh_task_list()
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
        icon_lbl.bind("<ButtonPress-1>", self._drag_start)
        icon_lbl.bind("<B1-Motion>",     self._drag_motion)
        icon_lbl.bind("<ButtonRelease-1>", self._drag_end)
        icon_lbl._img = icon_img

        # ── Éléments droite (du plus à droite au plus à gauche) ──

        # Poignée resize
        handle = tk.Frame(self._bg, width=6, cursor="size_we", bg=_HANDLE_BG)
        handle.pack(side="right", fill="y")
        handle.pack_propagate(False)
        handle.bind("<ButtonPress-1>",   self._resize_start)
        handle.bind("<B1-Motion>",       self._resize_motion)
        handle.bind("<ButtonRelease-1>", self._resize_end)

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
        self._timer_lbl.pack(side="left", padx=(2, 4))

        # ── Zone centrale : bouton tâche ↔ Entry nouvelle tâche ──

        self._center = ctk.CTkFrame(self._bg, fg_color="transparent")
        self._center.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Bouton déclencheur du dropdown (texte courant, aucun cadre)
        self._task_btn = ctk.CTkButton(
            self._center,
            text=_IDLE_LABEL,
            anchor="w",
            height=30,
            fg_color="transparent",
            hover_color=_BTN_HOVER,
            text_color=_TEXT_DIM,
            corner_radius=6,
            command=self._open_dropdown,
        )
        self._task_btn.pack(fill="x", expand=True)

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

        names = self._task_manager.get_recent_task_names()
        # Ne pas proposer la tâche déjà en cours
        current = self._current_task if self._timer.is_running else None
        filtered = [n for n in names if n != current]
        values = [_NEW_TASK_LABEL] + filtered

        bx = self._task_btn.winfo_rootx()
        by = self._task_btn.winfo_rooty() + self._task_btn.winfo_height() + 2
        bw = self._task_btn.winfo_width()

        self._dropdown = _TaskDropdown(
            self, values, self._on_task_selected, bx, by, bw,
            on_dismiss=self._on_task_dismissed,
        )

    # ------------------------------------------------------------------
    # Affichage de la tâche courante
    # ------------------------------------------------------------------

    def _set_task_display(self, value: str) -> None:
        """Met à jour le texte du bouton-tâche."""
        self._current_task = value
        self._task_btn.configure(text=value)

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
            self._task_btn.configure(text_color=_TEXT)
            play_img = self._icons["play"] if paused else self._icons["pause"]
            self._play_btn.configure(image=play_img, state="normal")
            self._stop_btn.configure(image=self._icons["stop"], state="normal")
            self._note_btn.configure(image=self._icons["note"], state="normal")
        else:
            self._timer_lbl.configure(text_color=_TEXT)
            self._task_btn.configure(text_color=_TEXT_DIM)
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
        self._task_btn.pack_forget()
        self._new_task_entry.pack(fill="x", expand=True)
        self._new_task_entry.delete(0, "end")
        self._new_task_entry.focus_set()

    def _show_task_mode(self) -> None:
        self._new_task_entry.pack_forget()
        self._task_btn.pack(fill="x", expand=True)

    def _on_new_task_confirm(self, event=None) -> None:
        name = self._new_task_entry.get().strip()
        self._show_task_mode()
        if not name:
            return
        try:
            self._task_manager.start_task(name, "")
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
            current, _ = self._timer.current_task
            self._set_task_display(current)
        else:
            self._set_task_display(_IDLE_LABEL)
            self._update_control_buttons(running=False, paused=False)

    def _on_task_dismissed(self, task_name: str) -> None:
        """Masque la tâche en base ; elle disparaît du dropdown à la prochaine ouverture."""
        self._task_manager.hide_task(task_name)

    def _on_task_selected(self, value: str) -> None:
        if value == _NEW_TASK_LABEL:
            self._show_entry_mode()
            return
        # Ne rien faire si la tâche est déjà en cours
        if self._timer.is_running:
            current, _ = self._timer.current_task
            if current == value:
                return
        tasks = self._task_manager.get_recent_tasks()
        match = next((t for t in tasks if t["name"] == value), None)
        project = match["project"] if match else ""
        try:
            self._task_manager.start_task(value, project)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Mise à jour depuis le thread timer
    # ------------------------------------------------------------------

    def on_timer_tick(self, elapsed: int, task_name: str, project: str) -> None:
        self.after(0, self._update_display, elapsed, task_name)

    def _update_display(self, elapsed: int, task_name: str) -> None:
        self._timer_lbl.configure(text=TimerEngine.format_elapsed(elapsed))
        if self._current_task != task_name:
            self._set_task_display(task_name)
        # Appel conditionnel uniquement si l'état change (pas chaque seconde)
        self._update_control_buttons(running=True, paused=False)

    def on_task_stopped(self) -> None:
        self.after(0, self._on_stopped)

    def _on_stopped(self) -> None:
        self._timer_lbl.configure(text="")
        self._set_task_display(_IDLE_LABEL)
        self._update_control_buttons(running=False, paused=False)

    def notify_task_list_changed(self) -> None:
        self.after(0, self._refresh_task_list)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _drag_end(self, event: tk.Event) -> None:
        self._db.set_config("overlay_x", str(self.winfo_x()))
        self._db.set_config("overlay_y", str(self.winfo_y()))

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def _resize_start(self, event: tk.Event) -> None:
        self._resize_x = event.x_root
        self._resize_w = self.winfo_width()

    def _resize_motion(self, event: tk.Event) -> None:
        new_w = max(200, self._resize_w + event.x_root - self._resize_x)
        self.geometry(f"{new_w}x{_HEIGHT}")

    def _resize_end(self, event: tk.Event) -> None:
        self._db.set_config("overlay_width", str(self.winfo_width()))
