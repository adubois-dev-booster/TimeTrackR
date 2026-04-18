"""
Génération de l'icône chronomètre partagée par toutes les fenêtres de l'application.
L'icône .ico est créée dans %APPDATA%/TimeTracker/ au premier lancement et réutilisée.

Les icônes de contrôle (play, pause, stop) sont dessinées avec Pillow pour garantir
un rendu net sur tous les DPI (supersampling 4× → LANCZOS → 2× → CTkImage).
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
    from ..core.database import get_db_path

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


# ── Icônes de contrôle (play / pause / stop) ──────────────────────────

def _create_play_img(size: int, color: str) -> Image.Image:
    """Triangle ▶ centré, fond transparent."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = size * 0.20
    draw.polygon(
        [(m, m), (m, size - m), (size - m, size / 2)],
        fill=color,
    )
    return img


def _create_pause_img(size: int, color: str) -> Image.Image:
    """Deux barres ⏸ centrées, fond transparent."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bw  = size * 0.22   # largeur d'une barre
    gap = size * 0.12   # demi-écart entre barres
    mv  = size * 0.18   # marge verticale
    cx  = size / 2
    draw.rectangle([cx - gap - bw, mv, cx - gap,      size - mv], fill=color)
    draw.rectangle([cx + gap,      mv, cx + gap + bw, size - mv], fill=color)
    return img


def _create_stop_img(size: int, color: str) -> Image.Image:
    """Carré ⏹ centré, fond transparent."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = size * 0.22
    draw.rectangle([m, m, size - m, size - m], fill=color)
    return img


def _create_note_img(size: int, color: str) -> Image.Image:
    """Icône bloc-notes : contour de page + 3 lignes de texte, fond transparent."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lw = max(2, size // 18)   # épaisseur du trait
    mx = size * 0.18           # marge gauche/droite de la page
    my = size * 0.08           # marge haut/bas de la page
    r  = max(2, size // 14)    # rayon des coins

    # Contour de la page
    draw.rounded_rectangle(
        [mx, my, size - mx, size - my],
        radius=r, outline=color, width=lw,
    )

    # Trois lignes de texte
    lx1 = mx + size * 0.20
    lx2 = size - mx - size * 0.12
    page_h = size - 2 * my
    for i in range(3):
        y = my + page_h * 0.28 + i * page_h * 0.22
        draw.rectangle([lx1, y, lx2, y + lw], fill=color)

    return img


def get_control_icons(size: int = 14) -> dict[str, ctk.CTkImage]:
    """
    Retourne les CTkImage pour play, pause et stop en états normal et dim.
    Rendu à 4× puis redimensionné à 2× (LANCZOS) pour un antialiasing optimal.
    """
    from .theme import TEXT as _TEXT, TEXT_DIM as _TEXT_DIM

    s_render  = size * 4   # dessin haute résolution
    s_hires   = size * 2   # cible 2× pour HiDPI

    def _mk(fn: callable, color: str) -> ctk.CTkImage:
        hi  = fn(s_render, color)
        img = hi.resize((s_hires, s_hires), Image.Resampling.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

    return {
        "play":      _mk(_create_play_img,  _TEXT),
        "play_dim":  _mk(_create_play_img,  _TEXT_DIM),
        "pause":     _mk(_create_pause_img, _TEXT),
        "pause_dim": _mk(_create_pause_img, _TEXT_DIM),
        "stop":      _mk(_create_stop_img,  _TEXT),
        "stop_dim":  _mk(_create_stop_img,  _TEXT_DIM),
        "note":      _mk(_create_note_img,  _TEXT),
        "note_dim":  _mk(_create_note_img,  _TEXT_DIM),
    }


# ── Icônes de la fenêtre principale ───────────────────────────────────

def _create_gear_img(size: int, color: str) -> Image.Image:
    """Engrenage ⚙ (8 dents + trou central)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    r_out  = size * 0.44
    r_in   = size * 0.32
    r_hole = size * 0.16
    n = 8
    pts = []
    for i in range(n):
        a_c    = 2 * math.pi * i / n
        half_w = math.pi / n * 0.55
        for a, r in [
            (a_c - half_w * 1.4, r_in),
            (a_c - half_w * 0.6, r_out),
            (a_c + half_w * 0.6, r_out),
            (a_c + half_w * 1.4, r_in),
        ]:
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    draw.polygon(pts, fill=color)
    draw.ellipse([cx - r_hole, cy - r_hole, cx + r_hole, cy + r_hole], fill=(0, 0, 0, 0))
    return img


def _create_sun_img(size: int, color: str) -> Image.Image:
    """Soleil ☀ (disque + 8 rayons)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    r_body = size * 0.24
    r_near = size * 0.31
    r_far  = size * 0.46
    ray_w  = max(2, size // 14)
    for i in range(8):
        a = 2 * math.pi * i / 8
        draw.line(
            [cx + r_near * math.cos(a), cy + r_near * math.sin(a),
             cx + r_far  * math.cos(a), cy + r_far  * math.sin(a)],
            fill=color, width=ray_w,
        )
    draw.ellipse([cx - r_body, cy - r_body, cx + r_body, cy + r_body], fill=color)
    return img


def _create_moon_img(size: int, color: str) -> Image.Image:
    """Lune 🌙 (croissant)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    r      = size * 0.38
    off_x  = size * 0.20
    off_y  = size * 0.08
    r2     = size * 0.34
    draw.ellipse([cx - r,            cy - r,        cx + r,            cy + r       ], fill=color)
    draw.ellipse([cx - r2 + off_x,   cy - r2 - off_y, cx + r2 + off_x, cy + r2 - off_y], fill=(0, 0, 0, 0))
    return img


def _create_refresh_img(size: int, color: str) -> Image.Image:
    """Rechargement ↻ (arc + pointe de flèche)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    r  = size * 0.34
    lw = max(2, size // 14)
    draw.arc([cx - r, cy - r, cx + r, cy + r], start=50, end=340, fill=color, width=lw)
    end_a  = math.radians(340)
    tip_x  = cx + r * math.cos(end_a)
    tip_y  = cy + r * math.sin(end_a)
    tang_a = end_a + math.pi / 2
    aw = size * 0.18
    draw.polygon([
        (tip_x, tip_y),
        (tip_x - aw * math.cos(tang_a - 0.45), tip_y - aw * math.sin(tang_a - 0.45)),
        (tip_x - aw * math.cos(tang_a + 0.45), tip_y - aw * math.sin(tang_a + 0.45)),
    ], fill=color)
    return img


def _create_chevron_down_img(size: int, color: str) -> Image.Image:
    """Chevron bas (deux traits en V)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lw = max(2, size // 14)
    mx = size * 0.22
    yt = size * 0.32
    yb = size * 0.68
    draw.line([mx,        yt, size / 2, yb], fill=color, width=lw)
    draw.line([size - mx, yt, size / 2, yb], fill=color, width=lw)
    return img


def _create_chevron_right_img(size: int, color: str) -> Image.Image:
    """Chevron droit (deux traits en >)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lw = max(2, size // 14)
    my = size * 0.22
    xl = size * 0.32
    xr = size * 0.68
    draw.line([xl, my,        xr, size / 2], fill=color, width=lw)
    draw.line([xl, size - my, xr, size / 2], fill=color, width=lw)
    return img


def _create_plus_img(size: int, color: str) -> Image.Image:
    """Plus +."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lw = max(2, size // 14)
    m  = size * 0.22
    cx, cy = size / 2, size / 2
    draw.line([cx, m,  cx,      size - m], fill=color, width=lw)
    draw.line([m,  cy, size - m, cy      ], fill=color, width=lw)
    return img


_app_icons_cache: dict | None = None


def get_app_icons() -> dict[str, ctk.CTkImage]:
    """
    Retourne toutes les icônes Pillow pour la fenêtre principale.
    Pipeline identique aux icônes de contrôle (4× → LANCZOS → 2×).
    Résultat mis en cache (génération unique par session).
    """
    global _app_icons_cache
    if _app_icons_cache is not None:
        return _app_icons_cache

    from .theme import TEXT_DIM as _TEXT_DIM

    def _mk(fn: callable, size: int, color_l: str, color_d: str | None = None) -> ctk.CTkImage:
        if color_d is None:
            color_d = color_l
        s4, s2 = size * 4, size * 2
        def _r(c):
            return fn(s4, c).resize((s2, s2), Image.Resampling.LANCZOS)
        return ctk.CTkImage(light_image=_r(color_l), dark_image=_r(color_d), size=(size, size))

    # Couleurs adaptées au mode clair / sombre
    _HL, _HD = "#374151", "#e2e8f0"   # en-tête : gris foncé / gris clair
    _AL, _AD = "#595959", "#a6a6a6"   # flèches expand : gray35 / gray65
    _PL, _PD = "#808080", "#8c8c8c"   # bouton grisé : gray50 / gray55
    _NL, _ND = "#94a3b8", "#64748b"   # indicateur note : clair / sombre

    _app_icons_cache = {
        # En-tête (16 px)
        "settings":      _mk(_create_gear_img,         16, _HL, _HD),
        "sun":           _mk(_create_sun_img,           16, _HL, _HD),
        "moon":          _mk(_create_moon_img,          16, _HL, _HD),
        "refresh":       _mk(_create_refresh_img,       16, _HL, _HD),
        # Bouton démarrer (14 px, blanc sur fond bleu)
        "start_play":    _mk(_create_play_img,          14, "white"),
        # Indicateurs de statut sur les lignes de tâche (11 px)
        "row_running":   _mk(_create_play_img,          11, "#22c55e", "#4ade80"),
        "row_paused":    _mk(_create_pause_img,         11, "#f59e0b", "#fbbf24"),
        # Flèches expand/collapse (10 px)
        "chevron_down":  _mk(_create_chevron_down_img,  10, _AL, _AD),
        "chevron_right": _mk(_create_chevron_right_img, 10, _AL, _AD),
        # Bouton nouvelle tâche (12 px)
        "plus":          _mk(_create_plus_img,          12, _PL, _PD),
        # Indicateur note dans les sessions (11 px)
        "session_note":  _mk(_create_note_img,          11, _NL, _ND),
    }
    return _app_icons_cache


def get_ctk_image(size: int = 20) -> ctk.CTkImage:
    """
    Retourne un CTkImage pour utilisation dans les widgets CustomTkinter.
    Rendu à 4× puis LANCZOS→2× pour un antialiasing identique aux icônes de contrôle.
    """
    hi  = create_icon(size * 4)
    img = hi.resize((size * 2, size * 2), Image.Resampling.LANCZOS)
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
