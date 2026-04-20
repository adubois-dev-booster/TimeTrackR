"""
Thème visuel des fenêtres flottantes de TimeTrackR.
(overlay, notifications, fenêtre de note)

Les fenêtres avec barre de titre (app principale, paramètres) suivent
le thème CustomTkinter dark/light et ne sont pas concernées par ce fichier.

══ COULEURS ══════════════════════════════════════════════════════════════

Pour changer le thème sombre, modifier les valeurs ci-dessous.
Couleur clé TRANSPARENT : rendue invisible par Windows → coins arrondis
sur les fenêtres borderless ; ne pas mettre de fond de la même couleur.
"""

# ── Fonds ─────────────────────────────────────────────────────────────
TRANSPARENT  = "#010101"   # couleur clé → pixels transparents (coins arrondis)
FRAME_BG     = "#262626"   # fond principal des fenêtres flottantes
DD_BG        = "#1e1e1e"   # fond des menus déroulants
ITEM_BG      = "#2e2e2e"   # fond des champs de saisie

# ── Accents ───────────────────────────────────────────────────────────
ACCENT       = "#3b82f6"   # bleu clair (bordures actives, focus)
ACCENT_BTN   = "#1d4ed8"   # fond des boutons primaires
ACCENT_HOVER = "#1e40af"   # hover des boutons primaires

# ── Interactifs ───────────────────────────────────────────────────────
BTN_HOVER    = "#3c3c3c"   # hover des boutons transparents
HANDLE_BG    = "#3a3a3a"   # poignée de resize et séparateurs horizontaux

# ── Texte ─────────────────────────────────────────────────────────────
TEXT         = "#e2e8f0"   # texte principal
TEXT_DIM     = "#64748b"   # texte secondaire / inactif / placeholders

# ── Alertes ───────────────────────────────────────────────────────────
WARNING      = "#f59e0b"   # amber — compteur d'inactivité
TAG_COLOR    = "#f97316"   # orange — badges #tag inline

"""
══ TAILLES DE POLICE ══════════════════════════════════════════════════
Valeurs passées à ctk.CTkFont(size=...).
"""

FONT_SM    = 11   # labels très secondaires (ex : « auto-sauvegardée »)
FONT_BASE  = 13   # texte courant
FONT_LG    = 15   # timer overlay
FONT_XL    = 18   # titres de popup
FONT_TIMER = 30   # grand compteur inactivité

"""
══ DIMENSIONS DES FENÊTRES (pixels) ══════════════════════════════════

Overlay
"""

OVERLAY_H         = 40    # hauteur fixe (non redimensionnable verticalement)
OVERLAY_W_DEFAULT = 340   # largeur au premier lancement

# Popup rappel durée de tâche (bas-droite, discret)
REMINDER_W = 320
REMINDER_H = 110

# Popup inactivité (centrée, modale)
IDLE_W     = 420
IDLE_H     = 360   # état normal (2 boutons)
IDLE_H_EXT = 402   # avec bouton « Reprendre tâche d'origine » visible (+42 px)

# Fenêtre de note
NOTE_H_DEFAULT = 150
NOTE_W_MIN     = 260
NOTE_H_MIN     = 120

"""
══ ICÔNE ══════════════════════════════════════════════════════════════

L'icône est dessinée programmatiquement dans ui/icon.py (create_icon).
Pour utiliser un fichier .ico externe, modifier get_icon_path() afin
qu'elle retourne directement le chemin de votre fichier.
Pour changer les couleurs de l'icône dessinée :
"""

ICON_BODY   = "#2563eb"   # corps (grand cercle)
ICON_CROWN  = "#1d4ed8"   # couronne, aiguilles, point central
ICON_TICKS  = "#94a3b8"   # graduations
ICON_FACE   = "white"     # face intérieure
