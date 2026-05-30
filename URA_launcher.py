#!/usr/bin/env python3
"""
Módulo: URA_launcher.py
Propósito: Punto de entrada principal que lanza la aplicación URA.
Dependencias principales: subprocess, sys
Reglas especiales: Solo lanza main_final.py. No contiene lógica de negocio.
"""

import subprocess
import sys


def main():
    subprocess.run([sys.executable, "main_final.py"])


if __name__ == "__main__":
    main()
