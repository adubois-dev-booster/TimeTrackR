"""
Génération de l'icône chronomètre partagée par toutes les fenêtres de l'application.
L'icône .ico est créée dans %APPDATA%/TimeTracker/ au premier lancement et réutilisée.
"""

import math
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw


def create_icon(size: int = 64) -> Image.Image:
    """
    Génère l'icône chronomètre à la taille demandée.
    Le dessin s'adapte proportionnellement à n'importe quelle taille.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = size // 2
    # Légèrement décalé vers le bas pour laisser de la place à la couronne
    cy = size // 2 + max(1, size // 14)
    r = int(size * 0.38)
    lw = max(2, size // 22)  # épaisseur de trait de base

    # -- Couronne (tige du haut) --
    cw = max(2, size // 14)   # demi-largeur
    ch = max(3, size // 9)    # hauteur
    draw.rectangle(
        [cx - cw, cy - r - ch, cx + cw, cy - r + lw],
        fill="#1d4ed8",
    )
    # Bouton arrondi sur la couronne
    draw.ellipse(
        [cx - cw - 2, cy - r - ch - max(2, size // 14),
         cx + cw + 2, cy - r - ch + max(2, size // 14)],
        fill="#1d4ed8",
    )

    # -- Corps (grand cercle bleu) --
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#2563eb")

    # -- Face intérieure (cercle blanc) --
    ri = int(r * 0.80)
    draw.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill="white")

    # -- Graduations --
    for i in range(12):
        angle = math.radians(i * 30 - 90)
        ro = ri - max(1, lw // 2)
        rk = ri - (size // 5 if i % 3 == 0 else size // 9)
        rk = max(rk, ri // 2)
        x1 = cx + int(ro * math.cos(angle))
        y1 = cy + int(ro * math.sin(angle))
        x2 = cx + int(rk * math.cos(angle))
        y2 = cy + int(rk * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill="#94a3b8", width=max(1, lw // 2))

    # -- Aiguille des minutes (vers 12h) --
    ml = int(ri * 0.70)
    draw.line([cx, cy, cx, cy - ml], fill="#1e40af", width=lw)

    # -- Aiguille des heures (vers 2h30) --
    hl = int(ri * 0.50)
    ang = math.radians(75 - 90)
    draw.line(
        [cx, cy, cx + int(hl * math.cos(ang)), cy + int(hl * math.sin(ang))],
        fill="#1e40af", width=lw,
    )

    # -- Point central --
    cr = max(2, size // 18)
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill="#1e40af")

    return img


def get_icon_path() -> Path:
    """
    Retourne le chemin vers l'icône .ico (créée si nécessaire dans %APPDATA%/TimeTracker/).
    Utilisé par iconbitmap() sur les fenêtres avec barre de titre.
    """
    # Import local pour éviter la dépendance circulaire au niveau module
    from .database import get_db_path

    icon_path = get_db_path().parent / "timetracker.ico"
    if not icon_path.exists():
        sizes = [16, 32, 48, 64, 256]
        images = [create_icon(s) for s in sizes]
        images[0].save(
            str(icon_path),
            format="ICO",
            append_images=images[1:],
            sizes=[(s, s) for s in sizes],
        )
    return icon_path


def get_ctk_image(size: int = 20) -> ctk.CTkImage:
    """
    Retourne un CTkImage pour utilisation dans les widgets CustomTkinter.
    Génère l'image en x2 pour les écrans haute densité.
    """
    img = create_icon(size * 2)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def apply_icon_to_window(window) -> None:
    """
    Applique l'icône .ico à une fenêtre Tkinter/CTk (barre de titre + barre des tâches).
    Doit être appelé après que la fenêtre soit visible (après mainloop ou update).
    """
    try:
        path = get_icon_path()
        window.iconbitmap(str(path))
    except Exception:
        pass  # Silencieux : l'icône n'est pas critique
