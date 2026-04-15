"""
Fenêtre des paramètres (CTkToplevel).
Accessible depuis le menu tray et depuis la fenêtre principale.
Deux sections : Application (démarrage Windows, fermeture dans le tray)
                Rappels (inactivité, durée de tâche).
"""

import os
import sys
import winreg
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from .database import Database


# ------------------------------------------------------------------
# Constantes registre Windows
# ------------------------------------------------------------------

_APP_NAME = "TimeTrackR"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Chemin racine du projet (TimeTrackR/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# pythonw.exe évite d'afficher une console au démarrage
_PYTHONW = sys.executable.replace("python.exe", "pythonw.exe")
if not os.path.isfile(_PYTHONW):
    _PYTHONW = sys.executable  # fallback si pythonw.exe absent

# Script lancé au démarrage
_RUN_SCRIPT = os.path.join(_PROJECT_ROOT, "run.py")


# ------------------------------------------------------------------
# Fonctions registre
# ------------------------------------------------------------------

def _get_startup_command() -> str:
    """Retourne la commande à enregistrer dans le registre de démarrage."""
    return f'"{_PYTHONW}" "{_RUN_SCRIPT}"'


def is_startup_enabled() -> bool:
    """Retourne True si TimeTrackR est configuré pour démarrer avec Windows."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _APP_NAME)
        winreg.CloseKey(key)
        return True
    except (FileNotFoundError, OSError):
        return False


def set_startup(enable: bool) -> None:
    """Ajoute ou supprime TimeTrackR du démarrage automatique Windows."""
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    )
    if enable:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _get_startup_command())
    else:
        try:
            winreg.DeleteValue(key, _APP_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)


# ------------------------------------------------------------------
# Fenêtre paramètres
# ------------------------------------------------------------------

class SettingsWindow(ctk.CTkToplevel):
    """
    Fenêtre modale des paramètres.
    Sauvegarde en base puis émet <<SettingsChanged>> sur la fenêtre parente.
    """

    def __init__(self, parent: ctk.CTk, database: Database):
        super().__init__(parent)

        self._db = database
        self._parent = parent

        self.title("Paramètres — TimeTrackR")
        self.geometry("420x500")
        self.resizable(False, False)

        # Rester au-dessus de la fenêtre principale
        self.transient(parent)
        self.grab_set()

        # Centrer par rapport au parent
        self._center_on_parent()

        # Icône partagée
        from .icon import apply_icon_to_window
        self.after(100, lambda: apply_icon_to_window(self))

        self._build_ui()
        self._load()

        # Fermeture via la croix = annuler
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _center_on_parent(self) -> None:
        """Centre la fenêtre par rapport à son parent."""
        self.update_idletasks()
        px = self._parent.winfo_x()
        py = self._parent.winfo_y()
        pw = self._parent.winfo_width()
        ph = self._parent.winfo_height()
        w, h = 420, 500
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construit les widgets."""

        # ── En-tête ───────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="Paramètres",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 4))

        # ── Section Application ───────────────────────────────────────
        app_frame = ctk.CTkFrame(self)
        app_frame.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(
            app_frame, text="Application",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 6))

        # Démarrage Windows
        startup_row = ctk.CTkFrame(app_frame, fg_color="transparent")
        startup_row.pack(fill="x", padx=14, pady=(0, 4))

        self._startup_var = tk.BooleanVar()
        ctk.CTkSwitch(
            startup_row,
            text="Lancer au démarrage de Windows",
            variable=self._startup_var,
        ).pack(side="left")

        # Fermeture dans le tray
        tray_row = ctk.CTkFrame(app_frame, fg_color="transparent")
        tray_row.pack(fill="x", padx=14, pady=(4, 14))

        self._close_to_tray_var = tk.BooleanVar()
        ctk.CTkSwitch(
            tray_row,
            text="Réduire dans le tray à la fermeture",
            variable=self._close_to_tray_var,
        ).pack(side="left")

        # ── Section Rappels ───────────────────────────────────────────
        reminders_frame = ctk.CTkFrame(self)
        reminders_frame.pack(fill="x", padx=16, pady=(14, 0))

        ctk.CTkLabel(
            reminders_frame, text="Rappels",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 6))

        # ── Rappel inactivité ────
        idle_header = ctk.CTkFrame(reminders_frame, fg_color="transparent")
        idle_header.pack(fill="x", padx=14, pady=(0, 4))

        self._idle_enabled_var = tk.BooleanVar()
        ctk.CTkSwitch(
            idle_header,
            text="Rappel d'inactivité",
            variable=self._idle_enabled_var,
        ).pack(side="left")

        idle_detail = ctk.CTkFrame(reminders_frame, fg_color="transparent")
        idle_detail.pack(fill="x", padx=28, pady=(0, 10))

        ctk.CTkLabel(idle_detail, text="Déclencher après").pack(side="left")
        self._idle_minutes_var = tk.StringVar()
        ctk.CTkEntry(
            idle_detail, textvariable=self._idle_minutes_var,
            width=52, justify="center",
        ).pack(side="left", padx=6)
        ctk.CTkLabel(idle_detail, text="min d'inactivité").pack(side="left")

        # Séparateur
        ctk.CTkFrame(reminders_frame, height=1, fg_color=("gray75", "gray35")).pack(
            fill="x", padx=14, pady=4
        )

        # ── Rappel durée de tâche ────
        dur_header = ctk.CTkFrame(reminders_frame, fg_color="transparent")
        dur_header.pack(fill="x", padx=14, pady=(4, 4))

        self._reminder_enabled_var = tk.BooleanVar()
        ctk.CTkSwitch(
            dur_header,
            text="Rappel durée de tâche",
            variable=self._reminder_enabled_var,
        ).pack(side="left")

        dur_detail = ctk.CTkFrame(reminders_frame, fg_color="transparent")
        dur_detail.pack(fill="x", padx=28, pady=(0, 14))

        ctk.CTkLabel(dur_detail, text="Rappeler tous les").pack(side="left")
        self._reminder_minutes_var = tk.StringVar()
        ctk.CTkEntry(
            dur_detail, textvariable=self._reminder_minutes_var,
            width=52, justify="center",
        ).pack(side="left", padx=6)
        ctk.CTkLabel(dur_detail, text="min sur la même tâche").pack(side="left")

        # ── Boutons Annuler / Sauvegarder ─────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(20, 16))

        ctk.CTkButton(
            btn_row, text="Annuler", width=110,
            fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
            text_color=("gray10", "gray90"),
            command=self.destroy,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_row, text="Sauvegarder", width=130,
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._save,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Chargement / sauvegarde
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Initialise les widgets avec les valeurs actuelles."""
        # Démarrage Windows : lire directement le registre (source de vérité)
        self._startup_var.set(is_startup_enabled())

        # Paramètres en base
        self._close_to_tray_var.set(
            self._db.get_config("close_to_tray", "1") == "1"
        )
        self._idle_enabled_var.set(
            self._db.get_config("idle_enabled", "1") == "1"
        )
        self._idle_minutes_var.set(
            self._db.get_config("idle_minutes", "10")
        )
        self._reminder_enabled_var.set(
            self._db.get_config("reminder_enabled", "1") == "1"
        )
        self._reminder_minutes_var.set(
            self._db.get_config("reminder_minutes", "60")
        )

    def _save(self) -> None:
        """Valide les champs, sauvegarde et notifie le parent."""
        # Validation des saisies numériques
        idle_min = self._parse_positive_int(self._idle_minutes_var.get(), "Inactivité")
        reminder_min = self._parse_positive_int(self._reminder_minutes_var.get(), "Durée de tâche")
        if idle_min is None or reminder_min is None:
            return

        # Démarrage Windows (registre)
        try:
            set_startup(self._startup_var.get())
        except OSError as e:
            messagebox.showerror(
                "Erreur registre",
                f"Impossible de modifier le démarrage automatique :\n{e}",
                parent=self,
            )
            return

        # Paramètres en base
        self._db.set_config("close_to_tray", "1" if self._close_to_tray_var.get() else "0")
        self._db.set_config("idle_enabled", "1" if self._idle_enabled_var.get() else "0")
        self._db.set_config("idle_minutes", str(idle_min))
        self._db.set_config("reminder_enabled", "1" if self._reminder_enabled_var.get() else "0")
        self._db.set_config("reminder_minutes", str(reminder_min))

        # Notifier la fenêtre principale que les paramètres ont changé
        self._parent.event_generate("<<SettingsChanged>>")

        self.destroy()

    def _parse_positive_int(self, value: str, label: str) -> int | None:
        """Retourne l'entier si valide (> 0), sinon affiche une erreur et retourne None."""
        try:
            n = int(value)
            if n <= 0:
                raise ValueError
            return n
        except ValueError:
            messagebox.showerror(
                "Valeur invalide",
                f"« {label} » doit être un entier strictement positif.",
                parent=self,
            )
            return None
