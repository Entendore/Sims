"""
Z-POC: Zombie Pathogen Outbreak Command Center
================================================
Entry point. Run this file to start the application.

Requirements:
  pip install PySide6 numpy matplotlib imageio[ffmpeg]
"""

import sys
from PySide6.QtWidgets import QApplication
from main_window import OutbreakMainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OutbreakMainWindow()
    window.show()
    sys.exit(app.exec())