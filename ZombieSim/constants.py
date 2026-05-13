"""
Z-POC: Shared constants, city names, and theme configuration.
"""

# ─── City name pool for thematic immersion ────────────
CITY_NAMES = [
    "Haven", "Blackwood", "Cresthill", "Duskfield", "Ironhaven",
    "Millford", "Northgate", "Oakhaven", "Redmoor", "Silverdale",
    "Thornwall", "Ashford", "Brierwood", "Copperwell", "Dawnfield",
    "Eastport", "Fairhaven", "Glenwood", "Hartfield", "Jadecove",
    "Kingsford", "Lakewatch", "Mistwood", "Newhaven", "Pinecrest",
    "Ravensholm", "Stonebridge", "Twilight", "Umberland", "Wraithmoor",
    "Yorkshire", "Zephyr", "Amberdale", "Brookhaven", "Cinderpeak",
    "Driftwood", "Emberfall", "Frosthollow", "Grimstone", "Hollowdale",
]

# ─── YouTube video defaults ──────────────────────────
YOUTUBE_WIDTH  = 1920
YOUTUBE_HEIGHT = 1080
YOUTUBE_FPS    = 30

# ─── Dark theme stylesheet ───────────────────────────
DARK_STYLESHEET = """
    QMainWindow, QWidget { background-color: #14161c; color: #cccccc; }
    QLabel { color: #cccccc; }
    QPushButton { padding: 5px; border: 1px solid #333; border-radius: 3px; background-color: #222; color: white; }
    QPushButton:disabled { background-color: #111; color: #555; }
    QPushButton:checked  { background-color: #444; }
    QSlider::groove:horizontal { height: 6px; background: #333; border-radius: 3px; }
    QSlider::handle:horizontal { background: #888; width: 12px; margin: -4px 0; border-radius: 6px; }
    QProgressBar { text-align: center; border: 1px solid #333; border-radius: 3px; background-color: #111; color: white; }
    QProgressBar::chunk { background-color: #cc3333; }
    QTextEdit { border: 1px solid #333; background-color: #0d0e12; color: #aaa; }
    QComboBox { padding: 4px; border: 1px solid #333; border-radius: 3px; background-color: #222; color: white; }
    QComboBox QAbstractItemView { background-color: #222; color: white; selection-background-color: #444; }
    QComboBox::drop-down { border: none; }
    QSpinBox { padding: 4px; border: 1px solid #333; border-radius: 3px; background-color: #222; color: white; }
    QDialog { background-color: #14161c; color: #cccccc; }
    QCheckBox { color: #cccccc; }
    QCheckBox::indicator { width: 14px; height: 14px; }
    QTabWidget::pane { border: 1px solid #333; background: #14161c; }
    QTabBar::tab { background: #222; color: #aaa; padding: 8px 20px; border: 1px solid #333; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
    QTabBar::tab:selected { background: #14161c; color: white; }
    QGroupBox { border: 1px solid #333; border-radius: 4px; margin-top: 10px; padding-top: 15px; font-weight: bold; color: #aaa; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
    QDoubleSpinBox { padding: 4px; border: 1px solid #333; border-radius: 3px; background-color: #222; color: white; }
"""