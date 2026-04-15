"""
Fenêtre overlay compacte.
Toujours au-dessus des autres fenêtres, sans barre de titre, absente de la barre des tâches.
Permet de voir la tâche en cours et de changer de tâche rapidement.
Draggable via l'icône chronomètre, redimensionnable en largeur via la poignée droite.

Utilise tk.Toplevel (et non CTkToplevel) pour éviter le problème de recréation
du HWND Windows quand overrideredirect() est appelé sur une fenêtre déjà gérée
par CTkToplevel : dans ce cas, les liaisons widget↔fenêtre sont perdues et
le contenu disparaît. tk.Toplevel n'a pas ce setup différé et fonctionne
fiablement avec overrideredirect dès __init__.
"""

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from .database import Database
from .icon import get_ctk_image
from .task_manager import TaskManager
from .timer_engine import TimerEngine


# Hauteur fixe de l'overlay en pixels
_HEIGHT = 44

# Option spéciale dans la liste déroulante
_NEW_TASK_LABEL = "＋  Nouvelle tâche"


class Overlay(tk.Toplevel):
    """
    Fenêtre flottante compacte affichant la tâche en cours et le timer.
    Se déplace par drag sur l'icône, se redimensionne en largeur par le bord droit.
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
        self._ignore_combo = False

        # --- Configuration fenêtre ---
        # Avec tk.Toplevel, overrideredirect(True) fonctionne immédiatement
        # sans recréer le HWND, donc le contenu reste intact.
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Couleur de fond identique au CTkFrame pour éviter les bords visibles
        self._apply_bg_color()

        ox = int(self._db.get_config("overlay_x", "100"))
        oy = int(self._db.get_config("overlay_y", "100"))
        self.geometry(f"{self._resize_w}x{_HEIGHT}+{ox}+{oy}")
        self.resizable(True, False)
        self.minsize(200, _HEIGHT)

        self._build_ui()
        self._refresh_task_list()
        self.deiconify()

    # ------------------------------------------------------------------
    # Couleur de fond
    # ------------------------------------------------------------------

    def _apply_bg_color(self) -> None:
        """Applique la couleur de fond en accord avec le thème CTk courant."""
        mode = ctk.get_appearance_mode()
        # Couleur du CTkFrame utilisé comme fond de l'overlay
        bg = "#242424" if mode == "Dark" else "#ebebeb"
        self.configure(bg=bg)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construit les widgets de l'overlay sur une seule ligne horizontale."""
        # Fond principal — couvre toute la fenêtre
        self._bg = ctk.CTkFrame(self, corner_radius=6, fg_color=("gray88", "gray17"))
        self._bg.pack(fill="both", expand=True, padx=0, pady=0)
        self._bg.columnconfigure(1, weight=1)  # la colonne du combo s'étend

        # -- Colonne 0 : icône (poignée de déplacement) --
        self._icon_img = get_ctk_image(size=20)
        self._icon_lbl = ctk.CTkLabel(
            self._bg,
            image=self._icon_img,
            text="",
            cursor="fleur",
            width=28,
        )
        self._icon_lbl.grid(row=0, column=0, padx=(6, 0), pady=0, sticky="ns")
        self._icon_lbl.bind("<ButtonPress-1>", self._drag_start)
        self._icon_lbl.bind("<B1-Motion>", self._drag_motion)
        self._icon_lbl.bind("<ButtonRelease-1>", self._drag_end)

        # -- Colonne 1 : liste déroulante des tâches --
        self._task_var = tk.StringVar()
        self._combo = ctk.CTkComboBox(
            self._bg,
            variable=self._task_var,
            values=[],
            height=28,
            command=self._on_task_selected,
            font=ctk.CTkFont(size=12),
        )
        self._combo.grid(row=0, column=1, padx=6, pady=8, sticky="ew")

        # -- Colonne 2 : timer --
        self._timer_lbl = ctk.CTkLabel(
            self._bg,
            text="00:00:00",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=80,
            anchor="center",
        )
        self._timer_lbl.grid(row=0, column=2, padx=(0, 4), pady=0)

        # -- Colonne 3 : poignée de redimensionnement --
        self._grip = ctk.CTkFrame(
            self._bg,
            width=6,
            corner_radius=0,
            fg_color=("gray70", "gray30"),
            cursor="size_we",
        )
        self._grip.grid(row=0, column=3, padx=0, pady=0, sticky="ns")
        self._grip.bind("<ButtonPress-1>", self._resize_start)
        self._grip.bind("<B1-Motion>", self._resize_motion)
        self._grip.bind("<ButtonRelease-1>", self._resize_end)

        # Drag depuis le fond (zones vides du frame)
        self._bg.bind("<ButtonPress-1>", self._drag_start)
        self._bg.bind("<B1-Motion>", self._drag_motion)
        self._bg.bind("<ButtonRelease-1>", self._drag_end)

    # ------------------------------------------------------------------
    # Gestion de la liste déroulante
    # ------------------------------------------------------------------

    def _refresh_task_list(self) -> None:
        """Recharge la liste des tâches récentes dans le combo."""
        names = self._task_manager.get_recent_task_names()
        values = [_NEW_TASK_LABEL] + names
        self._combo.configure(values=values)

        if self._timer.is_running:
            current, _ = self._timer.current_task
            self._set_combo_value(current)
        else:
            self._set_combo_value(_NEW_TASK_LABEL)

    def _set_combo_value(self, value: str) -> None:
        """Met à jour le combo sans déclencher le callback de changement."""
        self._ignore_combo = True
        self._task_var.set(value)
        self._ignore_combo = False

    def _on_task_selected(self, value: str) -> None:
        """Appelé par CTkComboBox quand l'utilisateur sélectionne une option."""
        if self._ignore_combo:
            return
        if value == _NEW_TASK_LABEL:
            self._on_open_main()
            return
        # Récupérer le projet associé depuis l'historique
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
        """Reçoit le tick du timer (autre thread) — délègue via after()."""
        self.after(0, self._update_display, elapsed, task_name)

    def _update_display(self, elapsed: int, task_name: str) -> None:
        """Met à jour le label timer et synchronise la sélection du combo."""
        self._timer_lbl.configure(text=TimerEngine.format_elapsed(elapsed))
        if self._task_var.get() != task_name:
            self._set_combo_value(task_name)

    def on_task_stopped(self) -> None:
        """Appelé depuis le thread principal quand le timer s'arrête."""
        self.after(0, self._on_stopped)

    def _on_stopped(self) -> None:
        self._timer_lbl.configure(text="00:00:00")
        self._set_combo_value(_NEW_TASK_LABEL)

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
