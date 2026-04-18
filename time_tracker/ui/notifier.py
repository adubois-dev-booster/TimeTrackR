"""
Fenêtres de notification Tkinter pour TimeTrackR.

- _ReminderDialog : rappel discret en bas-droite, timer non interrompu.
- _IdleDialog     : alerte inactivité centrée, grande.
                    Affiche la tâche courante, compteur live, et trois boutons
                    d'action dont un "Continuer sur autre tâche" avec combobox.

Les deux fenêtres sont always-on-top et ne se ferment que sur action explicite.
"""

import tkinter as tk
from typing import Callable

import customtkinter as ctk


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

# Sentinels du combo de l'IdleDialog
_NO_TASK       = "— aucune tâche —"
_NEW_TASK_LABEL = "＋  Nouvelle tâche"


# ══════════════════════════════════════════════════════════════════════
# Menu déroulant custom (style identique à overlay._TaskDropdown)
# ══════════════════════════════════════════════════════════════════════

class _SimpleDropdown(tk.Toplevel):
    """
    Popup de sélection pour l'IdleDialog.
    Même charte graphique que l'overlay, sans bouton de masquage.
    """
    _ROW_H = 30

    def __init__(
        self,
        parent: tk.Toplevel,
        values: list[str],
        on_select: Callable[[str], None],
        x: int,
        y: int,
        width: int,
    ):
        super().__init__(parent)
        self._on_select = on_select

        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        self._build(values)

        total_h = len(values) * (self._ROW_H + 2) + 10
        self.geometry(f"{max(width, 180)}x{total_h}+{x}+{y}")

        self.bind("<Escape>", lambda e: self.destroy())
        self.after(10, self.deiconify)
        self.after(20, self.focus_set)
        self.after(30, lambda: self.bind("<FocusOut>", lambda e: self.after(80, self._maybe_close)))

    def _build(self, values: list[str]) -> None:
        frame = ctk.CTkFrame(self, corner_radius=8, fg_color=_DD_BG)
        frame.pack(fill="both", expand=True)
        for value in values:
            is_dim = value in (_NO_TASK, _NEW_TASK_LABEL)
            ctk.CTkButton(
                frame,
                text=value,
                anchor="w",
                height=self._ROW_H,
                fg_color="transparent",
                hover_color=_BTN_HOVER,
                text_color=_TEXT_DIM if is_dim else _TEXT,
                font=ctk.CTkFont(size=13),
                corner_radius=4,
                command=lambda v=value: self._select(v),
            ).pack(fill="x", padx=4, pady=1)

    def _select(self, value: str) -> None:
        self.destroy()
        self._on_select(value)

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
# Rappel de durée de tâche — discret, bas-droite
# ══════════════════════════════════════════════════════════════════════

class _ReminderDialog(tk.Toplevel):
    """
    Petite fenêtre en bas à droite de l'écran.
    Le timer continue de tourner pendant que cette fenêtre est affichée.
    """

    _W = 320
    _H = 110

    def __init__(
        self,
        parent: tk.Tk,
        task_name: str,
        elapsed_seconds: int,
        on_continue: Callable,
        on_new_task: Callable,
    ):
        super().__init__(parent)
        self._on_continue = on_continue
        self._on_new_task = on_new_task

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = sw - self._W - 20
        y  = sh - self._H - 60
        self.geometry(f"{self._W}x{self._H}+{x}+{y}")

        self._build(task_name, elapsed_seconds)
        self.deiconify()

    def _build(self, task_name: str, elapsed_seconds: int) -> None:
        h = elapsed_seconds // 3600
        m = (elapsed_seconds % 3600) // 60
        duree = f"{h}h{m:02d}" if h > 0 else f"{m} min"

        frame = ctk.CTkFrame(self, corner_radius=10, fg_color=_FRAME_BG)
        frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            frame,
            text=f"⏰  Toujours sur « {task_name} » ?",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_TEXT, anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))

        ctk.CTkLabel(
            frame,
            text=f"Timer actif depuis {duree}.",
            font=ctk.CTkFont(size=11),
            text_color=_TEXT_DIM, anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 8))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkButton(
            btns, text="Continuer", height=28,
            font=ctk.CTkFont(size=12),
            fg_color=_ACCENT_BTN, hover_color=_ACCENT_HOVER, text_color="white",
            command=self._do_continue,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        ctk.CTkButton(
            btns, text="Nouvelle tâche", height=28,
            font=ctk.CTkFont(size=12),
            fg_color="transparent", border_width=1,
            border_color="#4b5563",
            hover_color=_BTN_HOVER, text_color=_TEXT,
            command=self._do_new_task,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _do_continue(self) -> None:
        self.destroy()
        self._on_continue()

    def _do_new_task(self) -> None:
        self.destroy()
        self._on_new_task()


# ══════════════════════════════════════════════════════════════════════
# Alerte inactivité — grande fenêtre centrée
# ══════════════════════════════════════════════════════════════════════

class _IdleDialog(tk.Toplevel):
    """
    Grande fenêtre centrée affichée quand l'inactivité est détectée.
    Combo pré-sélectionnée avec la tâche d'origine. Trois cas :
      - combo = tâche d'origine  → crédit de l'inactivité sur la tâche + reprise
      - combo = _NO_TASK         → reprise simple sans crédit (pause déjeuner, etc.)
      - combo = autre tâche YYY  → crédit de l'inactivité sur YYY + switch vers YYY
    """

    _W     = 420
    _H     = 360   # hauteur normale
    _H_EXT = 402   # avec bouton "Reprendre tâche d'origine" visible

    def __init__(
        self,
        parent: tk.Tk,
        idle_seconds: float,
        on_resume: Callable,
        on_stop: Callable,
        original_task: str = "",
        recent_tasks: list | None = None,
        on_other_continue: Callable | None = None,
        on_other_resume_old: Callable | None = None,   # crédit inactivité + reprise tâche d'origine
    ):
        super().__init__(parent)
        self._on_resume          = on_resume
        self._on_stop            = on_stop
        self._on_other_continue  = on_other_continue
        self._on_other_resume_old = on_other_resume_old
        self._original_task      = original_task
        self._idle_total         = int(idle_seconds)

        # Valeurs du combo : tâche d'origine, <aucune tâche>, autres tâches, + nouvelle tâche
        others = [t for t in (recent_tasks or []) if t != original_task]
        base = ([original_task, _NO_TASK] + others) if original_task else ([_NO_TASK] + others)
        self._combo_values = base + [_NEW_TASK_LABEL]

        self._task_var = tk.StringVar(value=original_task)
        self._task_var.trace_add("write", self._on_combo_changed)
        self._dropdown: "_SimpleDropdown | None" = None

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=_TRANSPARENT)
        self.wm_attributes("-transparentcolor", _TRANSPARENT)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{self._W}x{self._H}+{(sw - self._W) // 2}+{(sh - self._H) // 2}")

        self._build()
        self.deiconify()
        self.after(1000, self._tick)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=12, fg_color=_FRAME_BG)
        frame.pack(fill="both", expand=True)

        # Titre ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            frame,
            text="⏸  Inactivité détectée",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=_TEXT,
        ).pack(pady=(22, 4))

        # Compteur live ──────────────────────────────────────────────
        self._timer_lbl = ctk.CTkLabel(
            frame,
            text=self._fmt(self._idle_total),
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=_WARNING,
        )
        self._timer_lbl.pack(pady=(0, 16))

        # Séparateur ─────────────────────────────────────────────────
        ctk.CTkFrame(frame, height=1, fg_color=_HANDLE_BG).pack(fill="x", padx=24, pady=(0, 16))

        # Combo « Vous étiez sur » ───────────────────────────────────
        ctk.CTkLabel(
            frame,
            text="Vous étiez sur :",
            font=ctk.CTkFont(size=12),
            text_color=_TEXT_DIM,
            anchor="w",
        ).pack(anchor="w", padx=24, pady=(0, 4))

        # Conteneur partagé par le bouton-combo et l'entry "nouvelle tâche"
        self._combo_wrap = ctk.CTkFrame(frame, fg_color="transparent")
        self._combo_wrap.pack(fill="x", padx=24, pady=(0, 20))

        init_text  = self._original_task or _NO_TASK
        init_color = _TEXT if self._original_task else _TEXT_DIM
        self._combo_btn = ctk.CTkButton(
            self._combo_wrap,
            text=init_text,
            anchor="w",
            height=32,
            fg_color=_ITEM_BG,
            hover_color=_BTN_HOVER,
            border_color=_ACCENT,
            border_width=1,
            text_color=init_color,
            font=ctk.CTkFont(size=13),
            corner_radius=6,
            command=self._open_dropdown,
        )
        self._combo_btn.pack(fill="x")

        self._new_task_entry = ctk.CTkEntry(
            self._combo_wrap,
            placeholder_text="Nom de la nouvelle tâche…",
            height=32,
            fg_color=_ITEM_BG,
            border_color=_ACCENT,
            border_width=1,
            text_color=_TEXT,
            placeholder_text_color=_TEXT_DIM,
            font=ctk.CTkFont(size=13),
            corner_radius=6,
        )
        self._new_task_entry.bind("<Return>", self._on_new_task_confirm)
        self._new_task_entry.bind("<Escape>", self._on_new_task_cancel)

        # Boutons ────────────────────────────────────────────────────
        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(0, 24))

        # Bouton d'action principal (texte dynamique)
        task_short = _truncate(self._original_task, 22)
        self._action_btn = ctk.CTkButton(
            btns,
            text=f"Reprendre « {task_short} »",
            height=36, font=ctk.CTkFont(size=13),
            fg_color=_ACCENT_BTN, hover_color=_ACCENT_HOVER, text_color="white",
            command=self._do_action,
        )
        self._action_btn.pack(fill="x", pady=(0, 6))

        # Bouton "Reprendre tâche d'origine" — visible uniquement quand combo = autre tâche
        self._resume_orig_btn = ctk.CTkButton(
            btns,
            text=f"Reprendre « {task_short} »",
            height=36, font=ctk.CTkFont(size=13),
            fg_color="transparent", border_width=1,
            border_color=_ACCENT_BTN,
            hover_color=_BTN_HOVER, text_color=_TEXT,
            command=self._do_resume_original,
        )
        # Non packé au départ — affiché dynamiquement par _on_combo_changed

        # Arrêter (secondaire)
        ctk.CTkButton(
            btns,
            text="Arrêter la session",
            height=36, font=ctk.CTkFont(size=13),
            fg_color="transparent", border_width=1,
            border_color="#4b5563",
            hover_color=_BTN_HOVER, text_color=_TEXT,
            command=self._do_stop,
        ).pack(fill="x")

    # ------------------------------------------------------------------
    # Dropdown custom
    # ------------------------------------------------------------------

    def _open_dropdown(self) -> None:
        """Ouvre le popup de sélection, ou le ferme s'il est déjà visible (toggle)."""
        if self._dropdown is not None and self._dropdown.winfo_exists():
            self._dropdown.destroy()
            self._dropdown = None
            return
        x = self._combo_btn.winfo_rootx()
        y = self._combo_btn.winfo_rooty() + self._combo_btn.winfo_height() + 2
        w = self._combo_btn.winfo_width()
        self._dropdown = _SimpleDropdown(
            self, self._combo_values, self._on_task_selected, x, y, w
        )

    def _on_task_selected(self, value: str) -> None:
        """Met à jour le bouton-combo et déclenche la mise à jour de l'action via StringVar."""
        self._dropdown = None
        if value == _NEW_TASK_LABEL:
            self._show_entry_mode()
            return
        self._combo_btn.configure(
            text=value,
            text_color=_TEXT_DIM if value == _NO_TASK else _TEXT,
        )
        self._task_var.set(value)   # → _on_combo_changed → met à jour _action_btn

    # ------------------------------------------------------------------
    # Mode saisie nouvelle tâche
    # ------------------------------------------------------------------

    def _show_entry_mode(self) -> None:
        self._combo_btn.pack_forget()
        self._new_task_entry.delete(0, "end")
        self._new_task_entry.pack(fill="x")
        self._new_task_entry.focus_set()

    def _show_combo_mode(self) -> None:
        self._new_task_entry.pack_forget()
        self._combo_btn.pack(fill="x")

    def _on_new_task_confirm(self, event=None) -> None:
        name = self._new_task_entry.get().strip()
        self._show_combo_mode()
        if not name:
            return
        self._combo_btn.configure(text=name, text_color=_TEXT)
        self._task_var.set(name)    # → _on_combo_changed → met à jour _action_btn

    def _on_new_task_cancel(self, event=None) -> None:
        self._show_combo_mode()

    # ------------------------------------------------------------------
    # Mise à jour dynamique du bouton d'action
    # ------------------------------------------------------------------

    def _on_combo_changed(self, *_args) -> None:
        task_name    = self._task_var.get().strip()
        if task_name == _NEW_TASK_LABEL:
            return  # géré par _show_entry_mode
        orig_short   = _truncate(self._original_task, 22)
        is_other     = task_name and task_name != _NO_TASK and task_name != self._original_task

        if is_other:
            self._action_btn.configure(text=f"Continuer sur « {_truncate(task_name, 22)} »")
            self._resume_orig_btn.configure(text=f"Reprendre « {orig_short} »")
            self._resume_orig_btn.pack(fill="x", pady=(0, 6), after=self._action_btn)
            self._set_height(self._H_EXT)
        else:
            self._action_btn.configure(text=f"Reprendre « {orig_short} »")
            self._resume_orig_btn.pack_forget()
            self._set_height(self._H)

    def _set_height(self, h: int) -> None:
        """Redimensionne la fenêtre en gardant le centre de l'écran."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - self._W) // 2
        y  = (sh - h) // 2
        self.geometry(f"{self._W}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _do_action(self) -> None:
        task_name = self._task_var.get().strip()
        if not task_name or task_name == _NEW_TASK_LABEL:
            return  # saisie non confirmée, on n'agit pas
        self.destroy()
        if task_name == _NO_TASK:
            # Pause / repas → reprise simple, inactivité non créditée
            self._on_resume()
        elif task_name == self._original_task:
            # Tâche d'origine → crédit de l'inactivité sur la tâche + reprise
            if self._on_other_resume_old:
                self._on_other_resume_old(task_name, self._idle_total)
            else:
                self._on_resume()
        else:
            # Autre tâche → crédit de l'inactivité sur YYY + switch
            if self._on_other_continue:
                self._on_other_continue(task_name, self._idle_total)
            else:
                self._on_resume()

    def _do_resume_original(self) -> None:
        """Crédite l'inactivité sur la tâche sélectionnée, puis reprend la tâche d'origine."""
        task_name = self._task_var.get().strip()
        if not task_name or task_name == _NEW_TASK_LABEL:
            return  # saisie non confirmée
        self.destroy()
        if task_name and task_name != _NO_TASK and task_name != self._original_task:
            if self._on_other_resume_old:
                self._on_other_resume_old(task_name, self._idle_total)
                return
        self._on_resume()

    def _do_stop(self) -> None:
        self.destroy()
        self._on_stop()

    # ------------------------------------------------------------------
    # Timer live
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        self._idle_total += 1
        self._timer_lbl.configure(text=self._fmt(self._idle_total))
        self.after(1000, self._tick)

    @staticmethod
    def _fmt(seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}h{m:02d}m{s:02d}s"
        if m > 0:
            return f"{m}m{s:02d}s"
        return f"{s}s"


# ── Helpers ───────────────────────────────────────────────────────────

def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"


# ══════════════════════════════════════════════════════════════════════
# Notifier
# ══════════════════════════════════════════════════════════════════════

class Notifier:
    """
    Crée les fenêtres de notification sur le thread principal via after().
    Doit être instancié après la fenêtre App (nécessite une référence parent).
    """

    def __init__(self, parent: tk.Tk):
        self._parent          = parent
        self._reminder_dialog: "_ReminderDialog | None" = None
        self._idle_dialog:     "_IdleDialog     | None" = None

    def notify_idle(
        self,
        idle_seconds: float,
        on_resume: Callable,
        on_stop: Callable,
        original_task: str = "",
        recent_tasks: list | None = None,
        on_other_continue: Callable | None = None,
        on_other_resume_old: Callable | None = None,
    ) -> None:
        """Ouvre la fenêtre d'inactivité (thread-safe via after)."""
        self._parent.after(
            0,
            lambda: self._open_idle(
                idle_seconds, on_resume, on_stop,
                original_task, recent_tasks or [],
                on_other_continue, on_other_resume_old,
            ),
        )

    def _open_idle(
        self,
        idle_seconds: float,
        on_resume: Callable,
        on_stop: Callable,
        original_task: str,
        recent_tasks: list,
        on_other_continue: Callable | None,
        on_other_resume_old: Callable | None,
    ) -> None:
        if self._reminder_dialog is not None and self._reminder_dialog.winfo_exists():
            self._reminder_dialog.destroy()
        self._idle_dialog = _IdleDialog(
            self._parent, idle_seconds,
            on_resume, on_stop,
            original_task=original_task,
            recent_tasks=recent_tasks,
            on_other_continue=on_other_continue,
            on_other_resume_old=on_other_resume_old,
        )

    def notify_reminder(
        self,
        task_name: str,
        elapsed_seconds: int,
        on_continue: Callable,
        on_new_task: Callable,
    ) -> None:
        """Ouvre la fenêtre de rappel de durée (thread-safe via after)."""
        self._parent.after(
            0,
            lambda: self._open_reminder(task_name, elapsed_seconds, on_continue, on_new_task),
        )

    def _open_reminder(
        self,
        task_name: str,
        elapsed_seconds: int,
        on_continue: Callable,
        on_new_task: Callable,
    ) -> None:
        if self._reminder_dialog is not None and self._reminder_dialog.winfo_exists():
            return
        if self._idle_dialog is not None and self._idle_dialog.winfo_exists():
            return
        self._reminder_dialog = _ReminderDialog(
            self._parent, task_name, elapsed_seconds, on_continue, on_new_task
        )
