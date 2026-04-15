"""
Fenêtre overlay compacte.
Toujours au-dessus des autres fenêtres, sans barre de titre, absente de la barre des tâches.

Palette sombre fixe (indépendante du thème global).
Coins arrondis via wm_attributes("-transparentcolor") : _TRANSPARENT est rendue invisible
par Windows ; les coins du canvas CTkFrame (outside rounded rect) l'utilisent comme fond
→ effet de fenêtre aux bords arrondis sans clip Win32.
Utilise tk.Toplevel + after(10, deiconify) pour un rendu fiable des widgets.
"""

import tkinter as tk
from typing import TYPE_CHECKING, Callable

import customtkinter as ctk

from .database import Database
from .icon import get_ctk_image
from .task_manager import TaskManager
from .timer_engine import TimerEngine

if TYPE_CHECKING:
    from .note_window import NoteWindow


# Hauteur fixe de l'overlay en pixels
_HEIGHT = 46

# Labels spéciaux dans le menu déroulant
_NEW_TASK_LABEL = "＋  Nouvelle tâche"
_IDLE_LABEL     = "aucune tâche"       # affiché quand aucun timer n'est actif

# ── Palette sombre fixe ───────────────────────────────────────────────
_TRANSPARENT = "#010101"   # couleur clé → transparente (coins arrondis)
_FRAME_BG    = "#262626"   # fond CTkFrame principal
_ITEM_BG     = "#2e2e2e"   # fond Entry (mode saisie)
_ACCENT      = "#3b82f6"   # bleu accent (bordure entry)
_HANDLE_BG   = "#3a3a3a"   # poignée de redimensionnement
_BTN_BG      = "#343434"   # fond boutons icône
_BTN_HOVER   = "#484848"   # hover boutons icône
_TEXT        = "#e2e8f0"   # texte principal
_TEXT_DIM    = "#94a3b8"   # placeholder


class Overlay(tk.Toplevel):
    """
    Fenêtre flottante compacte affichant la tâche en cours et le timer.
    Boutons ▶/⏸ et ⏹ pour contrôler le timer directement depuis l'overlay.
    Bouton 📝 pour saisir une note sur la session en cours (NoteWindow).
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

        # Variables internes
        self._drag_x = self._drag_y = 0
        self._resize_x = 0
        self._resize_w = int(self._db.get_config("overlay_width", "340"))
        self._ignore_option = False
        self._note_win: "NoteWindow | None" = None

        # --- Configuration fenêtre ---
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # _TRANSPARENT rendue invisible → seul le CTkFrame (arrondi) est visible
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        ox = int(self._db.get_config("overlay_x", "100"))
        oy = int(self._db.get_config("overlay_y", "100"))
        self.geometry(f"{self._resize_w}x{_HEIGHT}+{ox}+{oy}")
        self.resizable(True, False)
        self.minsize(200, _HEIGHT)

        self._build_ui()
        self._refresh_task_list()
        # Deiconify via after() : les widgets ne sont peints que quand le mainloop tourne.
        self.after(10, self.deiconify)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construit l'interface complète de l'overlay."""

        # Cadre principal — corner_radius crée les coins arrondis visibles.
        # Les coins du canvas (outside rounded rect) utilisent bg=_TRANSPARENT → invisibles.
        self._bg = ctk.CTkFrame(self, corner_radius=10, fg_color=_FRAME_BG)
        self._bg.pack(fill="both", expand=True)

        # -- Icône chronomètre : zone de drag --
        icon_img = get_ctk_image(size=20)
        icon_lbl = ctk.CTkLabel(
            self._bg, image=icon_img, text="", width=28, cursor="hand2",
        )
        icon_lbl.pack(side="left", padx=(8, 2))
        icon_lbl.bind("<ButtonPress-1>", self._drag_start)
        icon_lbl.bind("<B1-Motion>", self._drag_motion)
        icon_lbl.bind("<ButtonRelease-1>", self._drag_end)
        icon_lbl._img = icon_img  # évite le garbage collection

        # ── Éléments côté droit (packés avant le centre pour la priorité) ──

        # Poignée de redimensionnement (tout à droite)
        handle = tk.Frame(self._bg, width=6, cursor="size_we", bg=_HANDLE_BG)
        handle.pack(side="right", fill="y")
        handle.pack_propagate(False)
        handle.bind("<ButtonPress-1>", self._resize_start)
        handle.bind("<B1-Motion>", self._resize_motion)
        handle.bind("<ButtonRelease-1>", self._resize_end)

        # Bouton note 📝 (désactivé tant qu'aucune tâche n'est en cours)
        self._note_btn = ctk.CTkButton(
            self._bg, text="📝", width=28, height=30,
            fg_color=_BTN_BG, hover_color=_BTN_HOVER,
            text_color=_TEXT, corner_radius=6,
            state="disabled",
            command=self._toggle_note,
        )
        self._note_btn.pack(side="right", padx=(0, 4))

        # Bouton stop ⏹
        self._stop_btn = ctk.CTkButton(
            self._bg, text="⏹", width=28, height=30,
            fg_color=_BTN_BG, hover_color=_BTN_HOVER,
            text_color=_TEXT, corner_radius=6,
            state="disabled",
            command=self._on_stop_btn,
        )
        self._stop_btn.pack(side="right", padx=(0, 2))

        # Bouton play/pause ▶/⏸
        self._play_btn = ctk.CTkButton(
            self._bg, text="▶", width=28, height=30,
            fg_color=_BTN_BG, hover_color=_BTN_HOVER,
            text_color=_TEXT, corner_radius=6,
            state="disabled",
            command=self._on_play_pause,
        )
        self._play_btn.pack(side="right", padx=(0, 2))

        # ── Timer ──

        self._timer_lbl = ctk.CTkLabel(
            self._bg,
            text="0h00m00s",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=84,
            anchor="center",
            text_color=_TEXT,
        )
        self._timer_lbl.pack(side="left", padx=(2, 4))

        # ── Zone centrale : OptionMenu ↔ Entry nouvelle tâche ──

        self._center = ctk.CTkFrame(self._bg, fg_color="transparent")
        self._center.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Menu déroulant — fg_color=_FRAME_BG pour fondre dans l'overlay (pas de cadre visible)
        self._task_var = tk.StringVar(value=_NEW_TASK_LABEL)
        self._option_menu = ctk.CTkOptionMenu(
            self._center,
            variable=self._task_var,
            values=[_NEW_TASK_LABEL],
            command=self._on_task_selected,
            height=30,
            fg_color=_FRAME_BG,
            button_color=_FRAME_BG,
            button_hover_color=_BTN_HOVER,
            text_color=_TEXT,
            dropdown_fg_color="#1e1e1e",
            dropdown_text_color=_TEXT,
            dropdown_hover_color=_BTN_HOVER,
            dynamic_resizing=False,
        )
        self._option_menu.pack(fill="x", expand=True)

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
    # Boutons play/pause et stop
    # ------------------------------------------------------------------

    def _on_play_pause(self) -> None:
        """Bascule pause/reprise."""
        if not self._timer.is_running:
            return
        is_paused = self._timer.toggle_pause()
        self._update_control_buttons(running=True, paused=is_paused)

    def _on_stop_btn(self) -> None:
        """Arrête la tâche en cours."""
        # Déléguer l'arrêt (et la mise à jour de la fenêtre principale) au callback
        if self._on_stop_requested:
            self._on_stop_requested()
        else:
            self._task_manager.stop_task()
        self._on_stopped()

    def _update_control_buttons(self, running: bool, paused: bool) -> None:
        """Met à jour l'état de tous les boutons de contrôle et la couleur du menu."""
        if running:
            self._option_menu.configure(text_color=_TEXT)
            self._play_btn.configure(text="▶" if paused else "⏸", state="normal")
            self._stop_btn.configure(state="normal")
            self._note_btn.configure(state="normal")
        else:
            self._option_menu.configure(text_color=_TEXT_DIM)
            self._play_btn.configure(text="▶", state="disabled")
            self._stop_btn.configure(state="disabled")
            self._note_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    # Fenêtre de note (toggle)
    # ------------------------------------------------------------------

    def _toggle_note(self) -> None:
        """Ouvre ou ferme la fenêtre de note."""
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
        self._option_menu.pack_forget()
        self._new_task_entry.pack(fill="x", expand=True)
        self._new_task_entry.delete(0, "end")
        self._new_task_entry.focus_set()

    def _show_option_mode(self) -> None:
        self._new_task_entry.pack_forget()
        self._option_menu.pack(fill="x", expand=True)

    def _on_new_task_confirm(self, event=None) -> None:
        name = self._new_task_entry.get().strip()
        self._show_option_mode()
        if not name:
            return
        try:
            self._task_manager.start_task(name, "")
        except ValueError:
            pass
        self._refresh_task_list()

    def _on_new_task_cancel(self, event=None) -> None:
        self._show_option_mode()

    # ------------------------------------------------------------------
    # Gestion du menu déroulant
    # ------------------------------------------------------------------

    def _refresh_task_list(self) -> None:
        names = self._task_manager.get_recent_task_names()
        self._option_menu.configure(values=[_NEW_TASK_LABEL] + names)

        if self._timer.is_running:
            current, _ = self._timer.current_task
            self._set_option_value(current)
        else:
            self._set_option_value(_IDLE_LABEL)
            self._update_control_buttons(running=False, paused=False)

    def _set_option_value(self, value: str) -> None:
        self._ignore_option = True
        self._task_var.set(value)
        self._ignore_option = False

    def _on_task_selected(self, value: str) -> None:
        if self._ignore_option:
            return
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
    # Formatage du timer
    # ------------------------------------------------------------------

    @staticmethod
    def _format_timer(elapsed: int) -> str:
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"{h}h{m:02d}m{s:02d}s"

    # ------------------------------------------------------------------
    # Mise à jour depuis le thread timer
    # ------------------------------------------------------------------

    def on_timer_tick(self, elapsed: int, task_name: str, project: str) -> None:
        self.after(0, self._update_display, elapsed, task_name)

    def _update_display(self, elapsed: int, task_name: str) -> None:
        self._timer_lbl.configure(text=self._format_timer(elapsed))
        if self._task_var.get() != task_name:
            self._set_option_value(task_name)
        # Timer ticking → forcément running et non pausé
        self._update_control_buttons(running=True, paused=False)

    def on_task_stopped(self) -> None:
        self.after(0, self._on_stopped)

    def _on_stopped(self) -> None:
        self._timer_lbl.configure(text="")
        self._set_option_value(_IDLE_LABEL)
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
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _drag_end(self, event: tk.Event) -> None:
        self._db.set_config("overlay_x", str(self.winfo_x()))
        self._db.set_config("overlay_y", str(self.winfo_y()))

    # ------------------------------------------------------------------
    # Resize (largeur uniquement)
    # ------------------------------------------------------------------

    def _resize_start(self, event: tk.Event) -> None:
        self._resize_x = event.x_root
        self._resize_w = self.winfo_width()

    def _resize_motion(self, event: tk.Event) -> None:
        new_w = max(200, self._resize_w + event.x_root - self._resize_x)
        self.geometry(f"{new_w}x{_HEIGHT}")

    def _resize_end(self, event: tk.Event) -> None:
        self._db.set_config("overlay_width", str(self.winfo_width()))
