"""
Script de lancement de TimeTrackR.
Ce fichier est utilisé par l'entrée de démarrage Windows (registre) afin que
pythonw.exe puisse trouver le package time_tracker sans passer par -m.
"""

import os
import sys

# Ajoute le répertoire du script (racine du projet) dans sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from time_tracker.main import main

if __name__ == "__main__":
    main()
