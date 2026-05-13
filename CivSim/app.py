#!/usr/bin/env python3
"""
CivSim — PySide6 Application Entry Point
"""
import sys
from PySide6.QtWidgets import QApplication
from engine import SimEngine
from gui import CivSimWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    engine = SimEngine()
    window = CivSimWindow(engine)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()