"""Taskbar-Cat: Pixel-Art-Tamagotchi-Katze für KDE Plasma 6 und GNOME."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("taskbar-cat")
except PackageNotFoundError:  # aus dem Quellverzeichnis gestartet, nicht installiert
    __version__ = "unbekannt (nicht installiert)"
