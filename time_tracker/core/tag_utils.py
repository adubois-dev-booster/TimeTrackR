"""
Utilitaires pour le parsing et l'affichage des tags de tâches.
Un tag est un mot préfixé par # dans la saisie : "test #client ma tache".
Le nom est stocké tel quel (tags inline) ; les tags sont extraits pour indexation.
"""

import re


def parse_task_input(raw: str) -> tuple[str, list[str]]:
    """
    Extrait les #tags pour indexation, retourne (nom_brut, tags_triés_lowercase).
    Le nom conserve les tags dans leur position originale.
    "test #client ma tache" → ("test #client ma tache", ["client"])
    "#monclient faire le site" → ("#monclient faire le site", ["monclient"])
    """
    tags = sorted(set(t.lower() for t in re.findall(r"#(\w+)", raw)))
    return raw.strip(), tags


def segment_text(text: str) -> list[tuple[str, bool]]:
    """
    Découpe un nom de tâche en segments (texte, is_tag) pour rendu inline.
    "test #client ma tache" → [("test ", False), ("#client", True), (" ma tache", False)]
    """
    parts: list[tuple[str, bool]] = []
    last = 0
    for m in re.finditer(r"#\w+", text):
        if m.start() > last:
            parts.append((text[last:m.start()], False))
        parts.append((m.group(), True))
        last = m.end()
    if last < len(text):
        parts.append((text[last:], False))
    return parts or [("", False)]


def tags_to_str(tags: list[str]) -> str:
    """Liste de tags → chaîne normalisée stockée en base ("monclient,web")."""
    return ",".join(sorted(t.lower() for t in tags if t))


def str_to_tags(tags_str: str) -> list[str]:
    """Chaîne en base → liste de tags."""
    return [t for t in tags_str.split(",") if t]


def format_task_display(name: str, tags_str: str) -> str:
    """Le nom inclut désormais les tags inline — retourne le nom tel quel."""
    return name


def display_to_name_tags(display: str) -> tuple[str, str]:
    """
    Le display est le nom brut (tags inline).
    Extrait les tags pour retrouver la clé de recherche en base.
    """
    tags = tags_to_str(sorted(set(t.lower() for t in re.findall(r"#(\w+)", display))))
    return display, tags
