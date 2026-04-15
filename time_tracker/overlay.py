"""
Fenêtre overlay compacte.
Toujours au-dessus des autres fenêtres, sans barre de titre, absente de la barre des tâches.
Permet de voir la tâche en cours et de changer de tâche rapidement.
Draggable via l'icône chronomètre, redimensionnable en largeur via la poignée droite.

Palette sombre fixe (indépendante du thème global de l'application).
Utilise tk.Toplevel pour overrideredirect fiable, et after(10) pour deiconify
après le démarrage du mainloop (sans ça les widgets sont créés mais pas peints).
"""

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from .database import Database
from .icon import get_ctk_image
from .task_manager import TaskManager
from .timer_engine import TimerEngine


# Hauteur fixe de l'overlay en pixels
_HEIGHT = 46

# Option spéciale dans le menu déroulant
_NEW_TASK_LABEL = "＋  Nouvelle tâche"

# ── Palette sombre fixe ───────────────────────────────────────────────
_BG          = "#1c1c1c"   # fond de la fenêtre
_FRAME_BG    = "#262626"   # fond CTkFrame principal
_ITEM_BG     = "#333333"   # fond OptionMenu / Entry
_ACCENT      = "#3b82f6"   # bleu accent (bordure entry, hover dropdown)
_HANDLE_BG   = "#3f3f3f"   # poignée de redimensionnement
_BTN_BG      = "#404040"   # bouton flèche du menu
_BTN_HOVER   = "#555555"   # hover bouton flèche
_DD_BG       = "#1e1e1e"   # fond liste déroulante
_TEXT        = "#e2e8f0"   # texte principal
_TEXT_DIM    = "#94a3b8"   # placeholder


class Overlay(tk.Toplevel):
    """
    Fenêtre flottante compacte affichant la tâche en cours et le timer.
    Se déplace par drag sur l'icône, se redimensionne en largeur par le bord droit.
    En mode "nouvelle tâche" : l'OptionMenu est remplacé par une Entry inline.
    """

    def __init__(
        self,
        parent: ctk.CTk,
        task_manager: TaskManager,
        timer_engine: TimerEngine,
        database: Database,
        on_open_main: Callable,
    ):
        super().__init__(parent)

        self._task_manager = task_manager
        self._timer = timer_engine
        self._db = database
        self._on_open_main = on_open_main

        # Variables internes
        self._drag_x = self._drag_y = 0
        self._resize_x = 0
        self._resize_w = int(self._db.get_config("overlay_width", "340"))
        self._ignore_option = False

        # --- Configuration fenêtre ---
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_BG)

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

        # Cadre principal
        self._bg = ctk.CTkFrame(self, corner_radius=8, fg_color=_FRAME_BG)
        self._bg.pack(fill="both", expand=True, padx=1, pady=1)

        # -- Icône chronomètre : zone de drag (curseur main) --
        icon_img = get_ctk_image(size=20)
        icon_lbl = ctk.CTkLabel(
            self._bg, image=icon_img, text="", width=28, cursor="hand2",
        )
        icon_lbl.pack(side="left", padx=(6, 2))
        icon_lbl.bind("<ButtonPress-1>", self._drag_start)
        icon_lbl.bind("<B1-Motion>", self._drag_motion)
        icon_lbl.bind("<ButtonRelease-1>", self._drag_end)
        icon_lbl._img = icon_img  # évite le garbage collection

        # -- Poignée de redimensionnement (côté droit, packée en premier) --
        handle = tk.Frame(self._bg, width=6, cursor="size_we", bg=_HANDLE_BG)
        handle.pack(side="right", fill="y")
        handle.pack_propagate(False)
        handle.bind("<ButtonPress-1>", self._resize_start)
        handle.bind("<B1-Motion>", self._resize_motion)
        handle.bind("<ButtonRelease-1>", self._resize_end)

        # -- Label timer (à gauche de la zone centrale) --
        self._timer_lbl = ctk.CTkLabel(
            self._bg,
            text="0h00m00s",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=84,
            anchor="center",
            text_color=_TEXT,
        )
        self._timer_lbl.pack(side="left", padx=(2, 4))

        # -- Zone centrale : OptionMenu ↔ Entry nouvelle tâche --
        self._center = ctk.CTkFrame(self._bg, fg_color="transparent")
        self._center.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Menu déroulant (lecture seule, pas de saisie clavier)
        self._task_var = tk.StringVar(value=_NEW_TASK_LABEL)
        self._option_menu = ctk.CTkOptionMenu(
            self._center,
            variable=self._task_var,
            values=[_NEW_TASK_LABEL],
            command=self._on_task_selected,
            height=30,
            fg_color=_ITEM_BG,
            button_color=_BTN_BG,
            button_hover_color=_BTN_HOVER,
            text_color=_TEXT,
            dropdown_fg_color=_DD_BG,
            dropdown_text_color=_TEXT,
            dropdown_hover_color=_ACCENT,
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
    # Mode saisie nouvelle tâche
    # ------------------------------------------------------------------

    def _show_entry_mode(self) -> None:
        """Passe en mode saisie : masque le menu, affiche l'entry."""
        self._option_menu.pack_forget()
        self._new_task_entry.pack(fill="x", expand=True)
        self._new_task_entry.delete(0, "end")
        self._new_task_entry.focus_set()

    def _show_option_mode(self) -> None:
        """Repasse en mode sélection : masque l'entry, affiche le menu."""
        self._new_task_entry.pack_forget()
        self._option_menu.pack(fill="x", expand=True)

    def _on_new_task_confirm(self, event=None) -> None:
        """Valide la saisie d'une nouvelle tâche (touche Entrée)."""
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
        """Annule la saisie (touche Echap)."""
        self._show_option_mode()

    # ------------------------------------------------------------------
    # Gestion du menu déroulant
    # ------------------------------------------------------------------

    def _refresh_task_list(self) -> None:
        """Recharge la liste des tâches récentes dans le menu."""
        names = self._task_manager.get_recent_task_names()
        values = [_NEW_TASK_LABEL] + names
        self._option_menu.configure(values=values)

        if self._timer.is_running:
            current, _ = self._timer.current_task
            self._set_option_value(current)
        else:
            self._set_option_value(_NEW_TASK_LABEL)

    def _set_option_value(self, value: str) -> None:
        """Met à jour le menu sans déclencher le callback."""
        self._ignore_option = True
        self._task_var.set(value)
        self._ignore_option = False

    def _on_task_selected(self, value: str) -> None:
        """Appelé par CTkOptionMenu quand l'utilisateur sélectionne une option."""
        if self._ignore_option:
            return
        if value == _NEW_TASK_LABEL:
            # Passer en mode saisie inline au lieu d'ouvrir la fenêtre principale
            self._show_entry_mode()
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
        """Retourne le temps au format XhMMmSSs (ex : 1h23m45s)."""
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"{h}h{m:02d}m{s:02d}s"

    # ------------------------------------------------------------------
    # Mise à jour depuis le thread timer
    # ------------------------------------------------------------------

    def on_timer_tick(self, elapsed: int, task_name: str, project: str) -> None:
        """Reçoit le tick du timer (autre thread) — délègue via after()."""
        self.after(0, self._update_display, elapsed, task_name)

    def _update_display(self, elapsed: int, task_name: str) -> None:
        """Met à jour le label timer et synchronise la sélection du menu."""
        self._timer_lbl.configure(text=self._format_timer(elapsed))
        if self._task_var.get() != task_name:
            self._set_option_value(task_name)

    def on_task_stopped(self) -> None:
        """Appelé depuis le thread principal quand le timer s'arrête."""
        self.after(0, self._on_stopped)

    def _on_stopped(self) -> None:
        self._timer_lbl.configure(text="0h00m00s")
        self._set_option_value(_NEW_TASK_LABEL)

    def notify_task_list_changed(self) -> None:
        """Appelé quand la liste des tâches doit être rechargée."""
        self.after(0, self._refresh_task_list)

    # ------------------------------------------------------------------
    # Drag (déplacement de la fenêtre)
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
        delta = event.x_root - self._resize_x
        new_w = max(200, self._resize_w + delta)
        self.geometry(f"{new_w}x{_HEIGHT}")

    def _resize_end(self, event: tk.Event) -> None:
        self._db.set_config("overlay_width", str(self.winfo_width()))
