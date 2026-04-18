"""
Fenêtre flottante de saisie de note pour la session en cours.
Même palette sombre que l'overlay, coins arrondis via transparentcolor.

Auto-sauvegarde à la fermeture :
  - perte du focus (clic hors fenêtre)
  - touche Échap
Pas de boutons : ouvrir, taper, repartir.
"""

import tkinter as tk

import customtkinter as ctk

from ..core.task_manager import TaskManager

from .icon import get_control_icons
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

_HEIGHT = 150


class NoteWindow(tk.Toplevel):
    """
    Petite fenêtre borderless pour saisir une note liée à la session en cours.
    Pré-remplie si une note existe déjà. Sauvegarde automatiquement à la fermeture.
    Redimensionnable via la poignée bas-droite.
    """

    def __init__(self, parent: tk.Toplevel, task_manager: TaskManager):
        super().__init__(parent)
        self._task_manager = task_manager

        self._drag_x = self._drag_y = 0
        self._resize_x0 = self._resize_y0 = 0
        self._resize_w0 = self._resize_h0 = 0

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        # Positionnée juste en dessous de l'overlay parent, même largeur
        ox = parent.winfo_x()
        oy = parent.winfo_y()
        ow = parent.winfo_width()
        oh = parent.winfo_height()
        self.geometry(f"{ow}x{_HEIGHT}+{ox}+{oy + oh + 4}")

        self._icons = get_control_icons(14)

        self._build_ui()

        # Pré-remplir avec la note existante
        note = self._task_manager.get_current_note()
        if note:
            self._text.insert("1.0", note)

        # Auto-sauvegarde : perte du focus ou Échap
        self._text.bind("<FocusOut>", lambda e: self.after(80, self._maybe_close))
        self.bind("<Escape>", lambda e: self._save_and_close())

        self.after(10, self.deiconify)
        self.after(20, self._text.focus_set)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._frame = ctk.CTkFrame(self, corner_radius=10, fg_color=_FRAME_BG)
        self._frame.pack(fill="both", expand=True)

        # En-tête draggable (titre + indication auto-save)
        header = ctk.CTkFrame(self._frame, fg_color="transparent", cursor="hand2")
        header.pack(fill="x", padx=10, pady=(10, 4))
        header.bind("<ButtonPress-1>", self._drag_start)
        header.bind("<B1-Motion>", self._drag_motion)

        ctk.CTkLabel(
            header,
            image=self._icons["note"],
            text="  Note de session",
            compound="left",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=_TEXT,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="auto-sauvegardée",
            font=ctk.CTkFont(size=12),
            text_color=_TEXT_DIM,
        ).pack(side="right")

        # Zone de texte (remplit tout l'espace disponible)
        self._text = ctk.CTkTextbox(
            self._frame,
            fg_color=_ITEM_BG,
            text_color=_TEXT,
            border_color=_ACCENT,
            border_width=1,
            corner_radius=6,
            wrap="word",
            font=ctk.CTkFont(size=14),
            scrollbar_button_color="#404040",
            scrollbar_button_hover_color="#505050",
        )
        self._text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Poignée de redimensionnement (coin bas-droite)
        grip = tk.Frame(self._frame, width=14, height=14, cursor="size_nw_se", bg=_HANDLE_BG)
        grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        grip.bind("<ButtonPress-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_motion)

    # ------------------------------------------------------------------
    # Auto-sauvegarde
    # ------------------------------------------------------------------

    def _maybe_close(self) -> None:
        """
        Appelée 80 ms après un FocusOut sur la textbox.
        Ferme et sauvegarde seulement si le focus est vraiment sorti de cette fenêtre.
        """
        try:
            focused = self.focus_get()
        except tk.TclError:
            self._save_and_close()
            return

        if focused is not None:
            try:
                if focused.winfo_toplevel() is self:
                    return  # Focus resté dans la fenêtre (ex : grip resize)
            except tk.TclError:
                pass
        self._save_and_close()

    def _save_and_close(self) -> None:
        """Sauvegarde la note et ferme la fenêtre."""
        try:
            note = self._text.get("1.0", "end-1c").strip()
            self._task_manager.set_current_note(note)
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    # ------------------------------------------------------------------
    # Resize (coin bas-droite)
    # ------------------------------------------------------------------

    def _resize_start(self, event: tk.Event) -> None:
        self._resize_x0 = event.x_root
        self._resize_y0 = event.y_root
        self._resize_w0 = self.winfo_width()
        self._resize_h0 = self.winfo_height()

    def _resize_motion(self, event: tk.Event) -> None:
        new_w = max(260, self._resize_w0 + event.x_root - self._resize_x0)
        new_h = max(120, self._resize_h0 + event.y_root - self._resize_y0)
        self.geometry(f"{new_w}x{new_h}")
