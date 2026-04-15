"""
Fenêtre flottante de saisie de note pour la session en cours.
Même palette sombre que l'overlay, coins arrondis via transparentcolor.
S'ouvre depuis le bouton 📝 de l'overlay.
"""

import tkinter as tk

import customtkinter as ctk

from .task_manager import TaskManager


# Couleur clé rendue transparente par Windows → permet les coins arrondis
_TRANSPARENT = "#010101"

# Palette sombre (identique à overlay.py)
_FRAME_BG  = "#262626"
_ITEM_BG   = "#2e2e2e"
_ACCENT    = "#3b82f6"
_TEXT      = "#e2e8f0"
_TEXT_DIM  = "#94a3b8"

_WIDTH  = 300
_HEIGHT = 190


class NoteWindow(tk.Toplevel):
    """
    Petite fenêtre borderless pour saisir une note liée à la session en cours.
    Pré-remplie si une note existe déjà.
    Entrée/Échap comme raccourcis clavier (Ctrl+Entrée pour valider).
    """

    def __init__(self, parent: tk.Toplevel, task_manager: TaskManager):
        super().__init__(parent)
        self._task_manager = task_manager

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        # Positionnée juste en dessous de l'overlay parent
        ox = parent.winfo_x()
        oy = parent.winfo_y()
        oh = parent.winfo_height()
        self.geometry(f"{_WIDTH}x{_HEIGHT}+{ox}+{oy + oh + 4}")

        self._build_ui()

        # Pré-remplir avec la note existante
        note = self._task_manager.get_current_note()
        if note:
            self._text.insert("1.0", note)

        self.bind("<Escape>", lambda e: self.destroy())

        self.after(10, self.deiconify)
        self.after(20, self._text.focus_set)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._frame = ctk.CTkFrame(self, corner_radius=10, fg_color=_FRAME_BG)
        self._frame.pack(fill="both", expand=True)

        # En-tête avec titre et drag
        header = ctk.CTkFrame(self._frame, fg_color="transparent", cursor="hand2")
        header.pack(fill="x", padx=10, pady=(10, 6))
        header.bind("<ButtonPress-1>", self._drag_start)
        header.bind("<B1-Motion>", self._drag_motion)

        ctk.CTkLabel(
            header,
            text="📝  Note de session",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_TEXT,
        ).pack(side="left")

        # Boutons Annuler / Enregistrer (packés AVANT la textbox pour réserver leur place)
        btn_row = ctk.CTkFrame(self._frame, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=10, pady=(4, 10))

        ctk.CTkButton(
            btn_row,
            text="✕  Annuler",
            width=110,
            height=28,
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            text_color=_TEXT,
            command=self.destroy,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_row,
            text="✓  Enregistrer",
            width=130,
            height=28,
            fg_color="#16a34a",
            hover_color="#15803d",
            text_color="white",
            command=self._save,
        ).pack(side="right")

        # Zone de texte (packée en dernier pour remplir l'espace restant)
        self._text = ctk.CTkTextbox(
            self._frame,
            fg_color=_ITEM_BG,
            text_color=_TEXT,
            border_color="#3a3a3a",
            border_width=1,
            corner_radius=6,
            wrap="word",
            font=ctk.CTkFont(size=12),
            scrollbar_button_color="#404040",
            scrollbar_button_hover_color="#505050",
        )
        self._text.pack(fill="both", expand=True, padx=10, pady=(0, 4))

    # ------------------------------------------------------------------
    # Sauvegarde
    # ------------------------------------------------------------------

    def _save(self) -> None:
        note = self._text.get("1.0", "end-1c").strip()
        self._task_manager.set_current_note(note)
        self.destroy()

    # ------------------------------------------------------------------
    # Drag (déplacer la fenêtre de note)
    # ------------------------------------------------------------------

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")
