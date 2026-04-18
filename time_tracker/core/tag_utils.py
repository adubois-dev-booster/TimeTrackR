"""
Utilitaires pour le parsing et l'affichage des tags de tâches.
Un tag est un mot préfixé par # dans la saisie : "#monclient faire le site".
"""

import re


def parse_task_input(raw: str) -> tuple[str, list[str]]:
    """
    Extrait les #tags et retourne (nom_nettoyé, tags_triés_lowercase).
    "#monclient faire le site #web" → ("faire le site", ["monclient", "web"])
    """
    tags = sorted(set(t.lower() for t in re.findall(r"#(\w+)", raw)))
    name = re.sub(r"\s*#\w+", "", raw).strip()
    return name, tags


def tags_to_str(tags: list[str]) -> str:
    """Liste de tags → chaîne normalisée stockée en base ("monclient,web")."""
    return ",".join(sorted(t.lower() for t in tags if t))


def str_to_tags(tags_str: str) -> list[str]:
    """Chaîne en base → liste de tags."""
    return [t for t in tags_str.split(",") if t]


def format_task_display(name: str, tags_str: str) -> str:
    """
    Formate nom + tags pour l'affichage.
    "faire le site", "monclient,web" → "faire le site [monclient] [web]"
    """
    if not tags_str:
        return name
    badges = "  ".join(f"[{t}]" for t in str_to_tags(tags_str))
    return f"{name}  {badges}"


def display_to_name_tags(display: str) -> tuple[str, str]:
    """
    Inverse de format_task_display : extrait (nom, tags_str) depuis une chaîne d'affichage.
    "faire le site  [monclient] [web]" → ("faire le site", "monclient,web")
    """
    found = re.findall(r"\[(\w+)\]", display)
    name  = re.sub(r"\s+\[\w+\]", "", display).strip()
    return name, tags_to_str(found)
