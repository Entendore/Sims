#!/usr/bin/env python3
"""
Advanced Cellular Automata Studio
==================================
A feature-rich application for exploring cellular automata with audio visualization.

Features:
  - Vectorized CA engine with 10+ rule presets
  - Interactive drawing & pattern stamping
  - Musical-scale-aware cluster audio synthesis
  - Real-time population history & statistics
  - Video + Audio export, state save/load
  - Dark theme UI with full parameter control
"""

import sys, json, os
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QCheckBox, QFileDialog, QSlider, QSpinBox,
    QGroupBox, QFormLayout, QSplitter, QMessageBox,
    QDoubleSpinBox, QSizePolicy, QScrollArea, QRadioButton, QButtonGroup
)
from PyQt6.QtGui import QGuiApplication, QFont
from PyQt6.QtCore import Qt, QTimer

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.animation import FFMpegWriter

import sounddevice as sd
from scipy.ndimage import label as ndlabel
from scipy.io.wavfile import write as wav_write
from scipy.signal import convolve2d

# ================================================================
#  CONSTANTS
# ================================================================

PRESETS = {
    "Conway's Life":  {"birth": [3],          "survive": [2, 3],          "waveform": "sine",     "desc": "Classic Game of Life"},
    "HighLife":       {"birth": [3, 6],       "survive": [2, 3],          "waveform": "saw",      "desc": "Has replicators"},
    "Seeds":          {"birth": [2],          "survive": [],               "waveform": "square",   "desc": "Explosive growth"},
    "Day & Night":    {"birth": [3,6,7,8],    "survive": [3,4,6,7,8],     "waveform": "triangle", "desc": "Symmetric rule"},
    "Diamoeba":       {"birth": [3,5,6,7,8],  "survive": [5,6,7,8],       "waveform": "sine",     "desc": "Diamond-shaped blobs"},
    "Morley (Move)":  {"birth": [3,6,8],      "survive": [2,4,5],         "waveform": "saw",      "desc": "Moves objects around"},
    "Replicator":     {"birth": [1,3,5,7],    "survive": [1,3,5,7],       "waveform": "triangle", "desc": "Every pattern replicates"},
    "2x2":            {"birth": [3,6],        "survive": [1,2,5],         "waveform": "square",   "desc": "2x2 block patterns"},
    "Anneal":         {"birth": [4,6,7,8],    "survive": [3,5,6,7,8],     "waveform": "sine",     "desc": "Simulates annealing"},
    "Maze":           {"birth": [3],          "survive": [1,2,3,4,5],     "waveform": "square",   "desc": "Maze-like structures"},
    "Maze (alt)":     {"birth": [3],          "survive": [1,2,3,4],       "waveform": "triangle", "desc": "Tendrilled mazes"},
    "Walled Cities":  {"birth": [4,5,6,7,8],  "survive": [2,3,4,5],       "waveform": "sine",     "desc": "Stable walled structures"},
}

MUSICAL_SCALES = {
    "Chromatic":  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    "Major":      [1, 3, 5, 6, 8, 10, 12],
    "Minor":      [1, 3, 4, 6, 8, 9, 11],
    "Pentatonic": [1, 3, 5, 8, 10],
    "Blues":      [1, 4, 6, 7, 8, 11],
    "Dorian":     [1, 3, 4, 6, 8, 9, 11],
    "Whole Tone": [1, 3, 5, 7, 9, 11],
    "Japanese":   [1, 2, 5, 7, 8],
    "Octave":     [1, 8],
}

COLORMAPS = [
    'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    'tab20', 'tab20b', 'tab20c', 'Spectral', 'coolwarm',
    'hot', 'YlOrRd', 'RdYlBu', 'rainbow', 'hsv', 'twilight',
    'gnuplot', 'cubehelix', 'ocean', 'terrain',
]

DISPLAY_MODES = ['Age', 'State', 'Clusters', 'Age+Clusters']

PATTERNS = {
    "None":       None,
    "Point":      np.array([[1]]),
    "Block":      np.array([[1,1],[1,1]]),
    "Blinker":    np.array([[1,1,1]]),
    "Toad":       np.array([[0,1,1,1],[1,1,1,0]]),
    "Beacon":     np.array([[1,1,0,0],[1,1,0,0],[0,0,1,1],[0,0,1,1]]),
    "Glider":     np.array([[0,1,0],[0,0,1],[1,1,1]]),
    "LWSS":       np.array([[0,1,0,0,1],[1,0,0,0,0],[1,0,0,0,1],[1,1,1,1,0]]),
    "R-pentomino":np.array([[0,1,1],[1,1,0],[0,1,0]]),
    "Acorn":      np.array([[0,1,0,0,0,0,0],[0,0,0,1,0,0,0],[1,1,0,0,1,1,1]]),
    "Diehard":    np.array([[0,0,0,0,0,0,1,0],[1,1,0,0,0,0,0,0],[0,1,0,0,0,1,1,1]]),
    "Pulsar": (lambda: np.array([
        [0,0,1,1,1,0,0,0,1,1,1,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0],
        [1,0,0,0,0,1,0,1,0,0,0,0,1],
        [1,0,0,0,0,1,0,1,0,0,0,0,1],
        [1,0,0,0,0,1,0,1,0,0,0,0,1],
        [0,0,1,1,1,0,0,0,1,1,1,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,1,1,1,0,0,0,1,1,1,0,0],
        [1,0,0,0,0,1,0,1,0,0,0,0,1],
        [1,0,0,0,0,1,0,1,0,0,0,0,1],
        [1,0,0,0,0,1,0,1,0,0,0,0,1],
        [0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,1,1,1,0,0,0,1,1,1,0,0],
    ], dtype=int))(),
    "Gosper Gun": (lambda: (lambda g: (
        g.__setitem__((0,24),1), g.__setitem__((1,22),1), g.__setitem__((1,24),1),
        g.__setitem__((2,12),1), g.__setitem__((2,13),1), g.__setitem__((2,20),1),
        g.__setitem__((2,21),1), g.__setitem__((2,34),1), g.__setitem__((2,35),1),
        g.__setitem__((3,11),1), g.__setitem__((3,15),1), g.__setitem__((3,20),1),
        g.__setitem__((3,21),1), g.__setitem__((3,34),1), g.__setitem__((3,35),1),
        g.__setitem__((4,0),1),  g.__setitem__((4,1),1),  g.__setitem__((4,10),1),
        g.__setitem__((4,16),1), g.__setitem__((4,20),1), g.__setitem__((4,21),1),
        g.__setitem__((5,0),1),  g.__setitem__((5,1),1),  g.__setitem__((5,10),1),
        g.__setitem__((5,14),1), g.__setitem__((5,16),1), g.__setitem__((5,17),1),
        g.__setitem__((5,22),1), g.__setitem__((5,24),1),
        g.__setitem__((6,10),1), g.__setitem__((6,16),1), g.__setitem__((6,24),1),
        g.__setitem__((7,11),1), g.__setitem__((7,15),1),
        g.__setitem__((8,12),1), g.__setitem__((8,13),1),
        g  # return the array
    )[-1])(np.zeros((9,36),dtype=int)))(),
}


# ================================================================
#  CELLULAR AUTOMATA ENGINE  (fully vectorized)
# ================================================================

class CellularAutomata:
    _kernel = np.array([[1,1,1],[1,0,1],[1,1,1]])

    def __init__(self, shape=(80,80), birth=None, survive=None,
                 name="Custom", toroidal=True, density=0.3):
        self.rows, self.cols = shape
        self.birth = list(birth or [3])
        self.survive = list(survive or [2,3])
        self.name = name
        self.toroidal = toroidal
        self.density = density
        self.grid = (np.random.random((self.rows, self.cols)) < density).astype(int)
        self.age  = np.zeros((self.rows, self.cols), dtype=int)
        self.generation = 0
        self.population_history = []
        self._birth_arr  = np.array(self.birth,  dtype=int)
        self._survive_arr= np.array(self.survive, dtype=int)

    # --- fast vectorized step ---
    def step(self):
        bnd = 'wrap' if self.toroidal else 'fill'
        nbrs = convolve2d(self.grid, self._kernel, mode='same', boundary=bnd, fillvalue=0)
        born   = (self.grid == 0) & np.isin(nbrs, self._birth_arr)
        alive  = (self.grid == 1) & np.isin(nbrs, self._survive_arr)
        new_grid = (born | alive).astype(int)
        new_age  = np.zeros_like(self.age)
        new_age[alive] = self.age[alive] + 1
        new_age[born]  = 1
        self.grid, self.age = new_grid, new_age
        self.generation += 1
        self.population_history.append(int(self.grid.sum()))
        return self.grid, self.age

    def set_rule(self, birth, survive):
        self.birth = list(birth)
        self.survive = list(survive)
        self._birth_arr  = np.array(self.birth,  dtype=int)
        self._survive_arr= np.array(self.survive, dtype=int)

    def reset(self, density=None):
        if density is not None: self.density = density
        self.grid = (np.random.random((self.rows, self.cols)) < self.density).astype(int)
        self.age  = np.zeros((self.rows, self.cols), dtype=int)
        self.generation = 0; self.population_history.clear()

    def clear(self):
        self.grid[:] = 0; self.age[:] = 0
        self.generation = 0; self.population_history.clear()

    def resize(self, shape):
        self.rows, self.cols = shape
        self.reset()

    def set_cell(self, r, c, v=1):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            self.grid[r, c] = v
            self.age[r, c]  = max(1, self.age[r, c]) if v else 0

    def stamp_pattern(self, pattern, row, col):
        pr, pc = pattern.shape
        r0, c0 = row - pr // 2, col - pc // 2
        for dr in range(pr):
            for dc in range(pc):
                rr, cc = r0 + dr, c0 + dc
                if 0 <= rr < self.rows and 0 <= cc < self.cols and pattern[dr, dc]:
                    self.grid[rr, cc] = 1
                    self.age[rr, cc]  = 1

    def population(self):       return int(self.grid.sum())
    def cluster_count(self):    _, n = ndlabel(self.grid > 0); return n
    def largest_cluster(self):
        lab, n = ndlabel(self.grid > 0)
        return int(np.max(lab.sum() if n == 0 else np.bincount(lab.ravel())[1:])) if n else 0

    def to_dict(self):
        return dict(rows=self.rows, cols=self.cols, birth=self.birth, survive=self.survive,
                    name=self.name, toroidal=self.toroidal, density=self.density,
                    grid=self.grid.tolist(), age=self.age.tolist(), generation=self.generation)

    @classmethod
    def from_dict(cls, d):
        ca = cls(shape=(d["rows"],d["cols"]), birth=d["birth"], survive=d["survive"],
                 name=d.get("name","Loaded"), toroidal=d.get("toroidal",True),
                 density=d.get("density",0.3))
        ca.grid = np.array(d["grid"], dtype=int)
        ca.age  = np.array(d["age"],  dtype=int)
        ca.generation = d.get("generation", 0)
        return ca


# ================================================================
#  AUDIO ENGINE  (cluster-based, musical-scale aware)
# ================================================================

class AudioEngine:
    def __init__(self, rate=44100, chunk=0.05, base_freq=220,
                 freq_range=800, harmonics=None, waveform='sine',
                 scale='Pentatonic', volume=0.5,
                 attack=0.01, decay=0.02, sustain=0.7, release=0.02):
        self.rate       = rate
        self.chunk      = chunk
        self.base_freq  = base_freq
        self.freq_range = freq_range
        self.harmonics  = harmonics or [1, 2, 3]
        self.waveform   = waveform
        self.scale      = scale
        self.volume     = volume
        self.attack     = attack
        self.decay      = decay
        self.sustain    = sustain
        self.release    = release

    @staticmethod
    def _wave(freq, t, kind='sine'):
        if kind == 'sine':     return np.sin(2*np.pi*freq*t)
        if kind == 'square':   return np.sign(np.sin(2*np.pi*freq*t))
        if kind == 'saw':      return 2*(freq*t - np.floor(freq*t + 0.5))
        if kind == 'triangle': return 2*np.abs(2*(freq*t - np.floor(freq*t+0.5)))-1
        return np.sin(2*np.pi*freq*t)

    def _adsr(self, n):
        e = np.ones(n)
        a = min(int(self.attack*self.rate), n)
        d = min(int(self.decay*self.rate), max(n-a,0))
        r = min(int(self.release*self.rate), max(n-a-d,0))
        if a: e[:a] = np.linspace(0,1,a)
        if d: e[a:a+d] = np.linspace(1,self.sustain,d)
        if a+d < n-r: e[a+d:n-r] = self.sustain
        if r: e[-r:] = np.linspace(self.sustain,0,r)
        return e

    def _scale_freq(self, idx):
        notes = MUSICAL_SCALES.get(self.scale, MUSICAL_SCALES["Pentatonic"])
        oct_off = idx // len(notes)
        semi = notes[idx % len(notes)] + oct_off*12 - 1
        return self.base_freq * (2**(semi/12.0))

    def generate(self, grid, ages):
        ns = int(self.rate * self.chunk)
        t  = np.linspace(0, self.chunk, ns, endpoint=False)
        L  = np.zeros(ns); R = np.zeros(ns)
        labeled, nc = ndlabel(grid > 0)
        if nc == 0: return np.zeros((ns,2))

        max_age = max(1, int(ages.max()))
        rows, cols = grid.shape
        env = self._adsr(ns)
        wfs = ['sine','square','saw','triangle']

        # Pre-compute cluster properties
        cprops = {}
        for c in range(1, nc+1):
            mask = labeled == c
            ys, xs = np.where(mask)
            sz = len(ys)
            cx, cy = xs.mean(), ys.mean()
            avg_a = ages[mask].mean()
            cprops[c] = dict(sz=sz, cx=cx, cy=cy, avg_age=avg_a)

        # Per-cluster synthesis (fast, O(clusters))
        for c, p in cprops.items():
            wf   = wfs[(c-1)%4]
            freq = self._scale_freq((c-1)*3 + int(p['avg_age'])%7)
            freq = np.clip(freq, 20, 16000)
            pan  = np.clip(p['cx'] / cols, 0, 1)
            amp  = 0.25 * min(1.0, 60.0/max(p['sz'],1)) * (p['avg_age']/max_age)
            sig  = np.zeros(ns)
            for h in self.harmonics:
                sig += (amp/h) * self._wave(np.clip(freq*h, 20, 20000), t, wf)
            sig *= env
            L += sig*(1-pan); R += sig*pan

        # Per-cell micro-detail (only for grids ≤ 120x120 or sparse)
        live = int(grid.sum())
        if live > 0 and live <= 3000:
            live_coords = np.argwhere(grid > 0)
            for (i, j) in live_coords:
                cl = labeled[i, j]
                wf = wfs[(cl-1)%4]
                a  = ages[i, j]
                note = (cl-1)*3 + int(a)%7
                freq = self._scale_freq(note) + a*1.5
                freq = np.clip(freq, 20, 16000)
                pan  = j / cols
                amp  = 0.04 * (a/max_age)
                sig  = np.zeros(ns)
                for h in self.harmonics[:2]:
                    sig += (amp/h) * self._wave(np.clip(freq*h,20,20000), t, wf)
                sig *= env
                L += sig*(1-pan); R += sig*pan

        mx = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
        L = L/mx*self.volume; R = R/mx*self.volume
        return np.stack([L, R], axis=-1)


# ================================================================
#  MAIN GUI
# ================================================================

class CAStudio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Cellular Automata Studio")
        self.setMinimumSize(1280, 820)
        self._apply_style()

        # State
        self.running = False
        self.drawing = False
        self.draw_value = 1
        self.last_cell = None

        preset = PRESETS["Conway's Life"]
        self.ca = CellularAutomata(shape=(80,80), birth=preset["birth"],
                                   survive=preset["survive"], name="Conway's Life")
        self.audio = AudioEngine(waveform=preset["waveform"])

        self._build_ui()
        self._setup_plots()
        self._refresh_display()

    # ---- dark theme ----
    def _apply_style(self):
        self.setStyleSheet("""
        QWidget{background:#1e1e2e;color:#cdd6f4;font-size:13px}
        QGroupBox{border:1px solid #45475a;border-radius:6px;margin-top:14px;
                  padding-top:14px;font-weight:bold;color:#89b4fa}
        QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px}
        QPushButton{background:#45475a;color:#cdd6f4;border:none;border-radius:4px;
                    padding:6px 12px;font-weight:bold}
        QPushButton:hover{background:#585b70}
        QPushButton:pressed{background:#313244}
        QPushButton:disabled{background:#313244;color:#6c7086}
        QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{background:#313244;color:#cdd6f4;
                    border:1px solid #45475a;border-radius:4px;padding:4px 8px}
        QComboBox::drop-down{border:none}
        QComboBox QAbstractItemView{background:#313244;color:#cdd6f4;
                    selection-background-color:#89b4fa}
        QSlider::groove:horizontal{background:#45475a;height:6px;border-radius:3px}
        QSlider::handle:horizontal{background:#89b4fa;width:16px;margin:-5px 0;border-radius:8px}
        QSlider::sub-page:horizontal{background:#89b4fa;border-radius:3px}
        QCheckBox::indicator{width:16px;height:16px}
        QRadioButton::indicator{width:14px;height:14px}
        QScrollArea{border:none}
        QLabel{color:#bac2de}
        """)

    # ---- build all UI ----
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(6); root.setContentsMargins(6,6,6,6)

        # == LEFT PANEL ==
        left = QWidget(); left.setFixedWidth(310)
        ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        sw = QWidget(); sl = QVBoxLayout(sw); sl.setSpacing(4)

        # -- Rules --
        g = QGroupBox("Rules & Presets"); fl = QFormLayout(); fl.setSpacing(5)
        self.rule_combo = QComboBox(); self.rule_combo.addItems(PRESETS.keys())
        self.rule_combo.currentTextChanged.connect(self._load_preset)
        self.preset_desc = QLabel(""); self.preset_desc.setWordWrap(True)
        self.preset_desc.setStyleSheet("color:#a6adc8;font-size:11px;font-style:italic")
        self.birth_input  = QLineEdit(",".join(map(str,self.ca.birth)))
        self.survive_input= QLineEdit(",".join(map(str,self.ca.survive)))
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(['sine','square','saw','triangle'])
        self.waveform_combo.setCurrentText(self.audio.waveform)
        self.apply_rule_btn = QPushButton("Apply Rule")
        self.apply_rule_btn.clicked.connect(self._apply_rule)
        fl.addRow("Preset:", self.rule_combo)
        fl.addRow("", self.preset_desc)
        fl.addRow("Birth (B):", self.birth_input)
        fl.addRow("Survive (S):", self.survive_input)
        fl.addRow("Waveform:", self.waveform_combo)
        fl.addRow(self.apply_rule_btn)
        g.setLayout(fl); sl.addWidget(g)
        self._load_preset("Conway's Life")  # set desc

        # -- Grid --
        g = QGroupBox("Grid Settings"); fl = QFormLayout(); fl.setSpacing(5)
        self.rows_spin = QSpinBox(); self.rows_spin.setRange(10,500); self.rows_spin.setValue(self.ca.rows)
        self.cols_spin = QSpinBox(); self.cols_spin.setRange(10,500); self.cols_spin.setValue(self.ca.cols)
        self.density_spin = QDoubleSpinBox(); self.density_spin.setRange(0.01,0.99)
        self.density_spin.setSingleStep(0.05); self.density_spin.setValue(self.ca.density)
        self.toroidal_check = QCheckBox("Toroidal (wrap edges)"); self.toroidal_check.setChecked(True)
        self.cmap_combo = QComboBox(); self.cmap_combo.addItems(COLORMAPS)
        self.cmap_combo.setCurrentText('viridis')
        self.display_combo = QComboBox(); self.display_combo.addItems(DISPLAY_MODES)
        self.display_combo.setCurrentText('Age')
        self.gridlines_check = QCheckBox("Show grid lines"); self.gridlines_check.setChecked(False)
        fl.addRow("Rows:", self.rows_spin); fl.addRow("Cols:", self.cols_spin)
        fl.addRow("Density:", self.density_spin); fl.addRow(self.toroidal_check)
        fl.addRow("Colormap:", self.cmap_combo); fl.addRow("Display:", self.display_combo)
        fl.addRow(self.gridlines_check)
        bl = QHBoxLayout()
        b1 = QPushButton("Resize"); b1.clicked.connect(self._resize_grid)
        b2 = QPushButton("Randomize"); b2.clicked.connect(self._randomize)
        b3 = QPushButton("Clear"); b3.clicked.connect(self._clear_grid)
        bl.addWidget(b1); bl.addWidget(b2); bl.addWidget(b3)
        fl.addRow(bl)
        g.setLayout(fl); sl.addWidget(g)

        # -- Simulation --
        g = QGroupBox("Simulation"); vl = QVBoxLayout(); vl.setSpacing(5)
        bl = QHBoxLayout()
        self.start_btn = QPushButton("▶ Start"); self.start_btn.clicked.connect(self._start)
        self.pause_btn = QPushButton("⏸ Pause"); self.pause_btn.clicked.connect(self._pause); self.pause_btn.setEnabled(False)
        self.step_btn  = QPushButton("⏭ Step");  self.step_btn.clicked.connect(self._step_once)
        bl.addWidget(self.start_btn); bl.addWidget(self.pause_btn); bl.addWidget(self.step_btn)
        vl.addLayout(bl)
        hl = QHBoxLayout(); hl.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal); self.speed_slider.setRange(1,60); self.speed_slider.setValue(15)
        self.speed_lbl = QLabel("15 FPS")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_lbl.setText(f"{v} FPS"))
        hl.addWidget(self.speed_slider); hl.addWidget(self.speed_lbl)
        vl.addLayout(hl)
        self.audio_check = QCheckBox("Enable Audio"); self.audio_check.setChecked(True)
        self.draw_check  = QCheckBox("Drawing Mode (L=draw R=erase)"); self.draw_check.setChecked(False)
        vl.addWidget(self.audio_check); vl.addWidget(self.draw_check)
        g.setLayout(vl); sl.addWidget(g)

        # -- Pattern stamp --
        g = QGroupBox("Pattern Stamp"); fl = QFormLayout(); fl.setSpacing(5)
        self.pattern_combo = QComboBox(); self.pattern_combo.addItems(PATTERNS.keys())
        self.pattern_combo.setCurrentText("None")
        self.stamp_btn = QPushButton("Click grid to stamp"); self.stamp_btn.setCheckable(True); self.stamp_btn.setChecked(False)
        self.pattern_preview = QLabel(""); self.pattern_preview.setStyleSheet("font-family:monospace;font-size:10px;color:#a6e3a1")
        self.pattern_combo.currentTextChanged.connect(self._update_pattern_preview)
        fl.addRow("Pattern:", self.pattern_combo)
        fl.addRow(self.stamp_btn)
        fl.addRow(self.pattern_preview)
        g.setLayout(fl); sl.addWidget(g)
        self._update_pattern_preview("None")

        # -- Audio --
        g = QGroupBox("Audio Settings"); fl = QFormLayout(); fl.setSpacing(5)
        self.base_freq_spin = QDoubleSpinBox(); self.base_freq_spin.setRange(20,2000)
        self.base_freq_spin.setValue(self.audio.base_freq); self.base_freq_spin.setSuffix(" Hz")
        self.freq_range_spin = QDoubleSpinBox(); self.freq_range_spin.setRange(0,5000)
        self.freq_range_spin.setValue(self.audio.freq_range); self.freq_range_spin.setSuffix(" Hz")
        self.harmonics_input = QLineEdit(",".join(map(str,self.audio.harmonics)))
        self.scale_combo = QComboBox(); self.scale_combo.addItems(MUSICAL_SCALES.keys())
        self.scale_combo.setCurrentText(self.audio.scale)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal); self.volume_slider.setRange(0,100)
        self.volume_slider.setValue(int(self.audio.volume*100))
        self.vol_lbl = QLabel(f"{int(self.audio.volume*100)}%")
        self.volume_slider.valueChanged.connect(lambda v: self.vol_lbl.setText(f"{v}%"))
        self.apply_audio_btn = QPushButton("Apply Audio"); self.apply_audio_btn.clicked.connect(self._apply_audio)
        fl.addRow("Base freq:", self.base_freq_spin); fl.addRow("Freq range:", self.freq_range_spin)
        fl.addRow("Harmonics:", self.harmonics_input); fl.addRow("Scale:", self.scale_combo)
        fl.addRow("Volume:", self.volume_slider); fl.addRow("", self.vol_lbl)
        fl.addRow(self.apply_audio_btn)
        g.setLayout(fl); sl.addWidget(g)

        # -- Stats --
        g = QGroupBox("Statistics"); fl = QFormLayout(); fl.setSpacing(3)
        self.stat_gen  = QLabel("0"); self.stat_gen.setStyleSheet("color:#a6e3a1;font-weight:bold;font-size:15px")
        self.stat_pop  = QLabel("0"); self.stat_pop.setStyleSheet("color:#f9e2af;font-weight:bold;font-size:15px")
        self.stat_clust= QLabel("0"); self.stat_clust.setStyleSheet("color:#89b4fa;font-weight:bold;font-size:15px")
        self.stat_big  = QLabel("0"); self.stat_big.setStyleSheet("color:#f38ba8;font-weight:bold;font-size:15px")
        self.stat_pct  = QLabel("0%"); self.stat_pct.setStyleSheet("color:#fab387;font-weight:bold;font-size:15px")
        fl.addRow("Generation:", self.stat_gen); fl.addRow("Population:", self.stat_pop)
        fl.addRow("Clusters:", self.stat_clust); fl.addRow("Largest:", self.stat_big)
        fl.addRow("Live %:", self.stat_pct)
        g.setLayout(fl); sl.addWidget(g)

        # -- Export / IO --
        g = QGroupBox("Export & Save/Load"); vl = QVBoxLayout(); vl.setSpacing(4)
        hl = QHBoxLayout(); hl.addWidget(QLabel("Frames:"))
        self.export_frames = QSpinBox(); self.export_frames.setRange(10,10000); self.export_frames.setValue(300)
        hl.addWidget(self.export_frames); vl.addLayout(hl)
        b = QPushButton("🎬 Export Video + Audio"); b.clicked.connect(self._export_video); vl.addWidget(b)
        b = QPushButton("🎵 Export Audio Only");    b.clicked.connect(self._export_audio); vl.addWidget(b)
        b = QPushButton("💾 Save State");           b.clicked.connect(self._save_state);   vl.addWidget(b)
        b = QPushButton("📂 Load State");           b.clicked.connect(self._load_state);   vl.addWidget(b)
        g.setLayout(vl); sl.addWidget(g)

        sl.addStretch()
        scroll.setWidget(sw); ll.addWidget(scroll)
        root.addWidget(left)

        # == RIGHT PANEL (plots) ==
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0)
        self.info_lbl = QLabel("L-click: draw | R-click: erase | Scroll: zoom | Space: start/pause | S: step")
        self.info_lbl.setStyleSheet("color:#6c7086;font-size:11px;padding:2px")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(self.info_lbl)

        self.figure = plt.Figure(figsize=(9,8), facecolor='#1e1e2e')
        gs = self.figure.add_gridspec(5, 1, hspace=0.35)
        self.ax_main = self.figure.add_subplot(gs[0:4, 0])
        self.ax_pop  = self.figure.add_subplot(gs[4, 0])
        self.canvas  = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rl.addWidget(self.canvas, stretch=1)

        self.canvas.mpl_connect('button_press_event',  self._mpl_press)
        self.canvas.mpl_connect('motion_notify_event',  self._mpl_motion)
        self.canvas.mpl_connect('button_release_event', self._mpl_release)

        root.addWidget(right, stretch=1)

        # Timer
        self.timer = QTimer(); self.timer.timeout.connect(self._sim_tick)

    # ---- matplotlib setup ----
    def _setup_plots(self):
        for ax in (self.ax_main, self.ax_pop):
            ax.set_facecolor('#181825')
            for sp in ax.spines.values(): sp.set_color('#45475a')
            ax.tick_params(colors='#6c7086')

        self.img = self.ax_main.imshow(self.ca.age, cmap='viridis', vmin=0, vmax=10,
                                       interpolation='nearest', aspect='equal')
        self.ax_main.set_title("Cellular Automata", color='#cdd6f4', fontsize=13, fontweight='bold')
        self.cbar = self.figure.colorbar(self.img, ax=self.ax_main, fraction=0.046, pad=0.04)
        self.cbar.ax.tick_params(colors='#6c7086', labelsize=8)
        self.cbar.set_label('Age', color='#6c7086', fontsize=9)

        self.pop_line, = self.ax_pop.plot([], [], color='#89b4fa', linewidth=1.2)
        self.pop_fill  = None
        self.ax_pop.set_title("Population", color='#cdd6f4', fontsize=10)
        self.ax_pop.set_xlabel("Generation", color='#6c7086', fontsize=8)
        self.ax_pop.set_ylabel("Cells", color='#6c7086', fontsize=8)
        self.ax_pop.set_xlim(0, 50); self.ax_pop.set_ylim(0, self.ca.rows*self.ca.cols*0.5)
        self.figure.tight_layout(pad=1.0)

    # ---- drawing on canvas ----
    def _grid_coord(self, event):
        if event.inaxes != self.ax_main or event.xdata is None: return None, None
        c, r = int(round(event.xdata)), int(round(event.ydata))
        if 0 <= r < self.ca.rows and 0 <= c < self.ca.cols: return r, c
        return None, None

    def _mpl_press(self, event):
        r, c = self._grid_coord(event)
        if r is None: return

        # Pattern stamping
        if self.stamp_btn.isChecked() and self.pattern_combo.currentText() != "None":
            pat = PATTERNS.get(self.pattern_combo.currentText())
            if pat is not None:
                self.ca.stamp_pattern(pat, r, c)
                self._refresh_display()
                return

        # Drawing
        if self.draw_check.isChecked():
            self.drawing = True
            self.draw_value = 1 if event.button == 1 else 0
            self.ca.set_cell(r, c, self.draw_value)
            self.last_cell = (r, c)
            self._refresh_display()

    def _mpl_motion(self, event):
        if not self.drawing or not self.draw_check.isChecked(): return
        r, c = self._grid_coord(event)
        if r is not None and (r, c) != self.last_cell:
            self.ca.set_cell(r, c, self.draw_value)
            self.last_cell = (r, c)
            self._refresh_display()

    def _mpl_release(self, event):
        self.drawing = False; self.last_cell = None

    # ---- keyboard ----
    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Space:
            self._pause() if self.running else self._start()
        elif k == Qt.Key.Key_S:
            self._step_once()
        elif k == Qt.Key.Key_R:
            self._randomize()
        elif k == Qt.Key.Key_C:
            self._clear_grid()
        else:
            super().keyPressEvent(event)

    # ---- preset / rule ----
    def _load_preset(self, name):
        p = PRESETS.get(name)
        if not p: return
        self.birth_input.setText(",".join(map(str, p["birth"])))
        self.survive_input.setText(",".join(map(str, p["survive"])))
        self.waveform_combo.setCurrentText(p["waveform"])
        self.preset_desc.setText(p.get("desc", ""))
        self._apply_rule()

    def _apply_rule(self):
        try:
            b = [int(x) for x in self.birth_input.text().replace(' ',',').split(',') if x.strip()]
            s = [int(x) for x in self.survive_input.text().replace(' ',',').split(',') if x.strip()]
            self.ca.set_rule(b, s)
            self.audio.waveform = self.waveform_combo.currentText()
            self.ca.name = self.rule_combo.currentText()
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Enter comma-separated integers for B/S rules.")

    def _apply_audio(self):
        try:
            self.audio.base_freq  = self.base_freq_spin.value()
            self.audio.freq_range = self.freq_range_spin.value()
            self.audio.harmonics  = [int(x) for x in self.harmonics_input.text().split(',') if x.strip()]
            self.audio.scale      = self.scale_combo.currentText()
            self.audio.volume     = self.volume_slider.value() / 100.0
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Enter comma-separated integers for harmonics.")

    # ---- grid management ----
    def _resize_grid(self):
        self.ca.toroidal = self.toroidal_check.isChecked()
        self.ca.resize((self.rows_spin.value(), self.cols_spin.value()))
        self.ca.density = self.density_spin.value()
        self.ca.reset(self.ca.density)
        self._rebuild_img(); self._refresh_display()

    def _randomize(self):
        self.ca.reset(self.density_spin.value()); self._refresh_display()

    def _clear_grid(self):
        self.ca.clear(); self._refresh_display()

    def _rebuild_img(self):
        self.ax_main.clear(); self.cbar.remove()
        self.img = self.ax_main.imshow(self.ca.age, cmap=self.cmap_combo.currentText(),
                                       vmin=0, vmax=10, interpolation='nearest', aspect='equal')
        self.ax_main.set_title("Cellular Automata", color='#cdd6f4', fontsize=13, fontweight='bold')
        for sp in self.ax_main.spines.values(): sp.set_color('#45475a')
        self.ax_main.tick_params(colors='#6c7086')
        self.cbar = self.figure.colorbar(self.img, ax=self.ax_main, fraction=0.046, pad=0.04)
        self.cbar.ax.tick_params(colors='#6c7086', labelsize=8)
        self.ax_pop.set_ylim(0, self.ca.rows*self.ca.cols*0.5)
        self.figure.tight_layout(pad=1.0)

    # ---- pattern preview ----
    def _update_pattern_preview(self, name):
        pat = PATTERNS.get(name)
        if pat is None:
            self.pattern_preview.setText("(select a pattern)")
            return
        chars = {0: '·', 1: '█'}
        lines = []
        for row in pat:
            lines.append("".join(chars.get(v, '?') for v in row))
        self.pattern_preview.setText("\n".join(lines))

    # ---- simulation ----
    def _start(self):
        self._apply_rule(); self._apply_audio()
        self.running = True
        self.timer.start(int(1000/self.speed_slider.value()))
        self.start_btn.setEnabled(False); self.pause_btn.setEnabled(True)

    def _pause(self):
        self.running = False; self.timer.stop()
        self.start_btn.setEnabled(True); self.pause_btn.setEnabled(False)

    def _step_once(self):
        self._apply_rule(); self._apply_audio()
        grid, age = self.ca.step()
        if self.audio_check.isChecked(): self._play(grid, age)
        self._refresh_display()

    def _sim_tick(self):
        grid, age = self.ca.step()
        if self.audio_check.isChecked(): self._play(grid, age)
        self._refresh_display()
        self.timer.setInterval(int(1000/self.speed_slider.value()))

    def _play(self, grid, age):
        try:
            sd.stop()
            chunk = self.audio.generate(grid, age)
            sd.play(chunk, self.audio.rate, blocking=False)
        except Exception as e:
            print(f"Audio error: {e}")

    # ---- display ----
    def _refresh_display(self):
        grid, age = self.ca.grid, self.ca.age
        mode = self.display_combo.currentText()
        cmap_name = self.cmap_combo.currentText()

        if mode == 'Age':
            data = age * grid
            self.img.set_data(data); self.img.set_cmap(cmap_name)
            self.img.set_clim(0, max(10, age.max()))
            self.cbar.set_label('Age', color='#6c7086', fontsize=9)
        elif mode == 'State':
            data = grid
            self.img.set_data(data); self.img.set_cmap(cmap_name)
            self.img.set_clim(0, 1)
            self.cbar.set_label('State', color='#6c7086', fontsize=9)
        elif mode == 'Clusters':
            labeled, _ = ndlabel(grid > 0)
            data = labeled
            self.img.set_data(data); self.img.set_cmap(cmap_name)
            self.img.set_clim(0, max(1, data.max()))
            self.cbar.set_label('Cluster', color='#6c7086', fontsize=9)
        elif mode == 'Age+Clusters':
            labeled, _ = ndlabel(grid > 0)
            data = age + labeled * 3
            self.img.set_data(data); self.img.set_cmap(cmap_name)
            self.img.set_clim(0, max(10, data.max()))
            self.cbar.set_label('Age+Cluster', color='#6c7086', fontsize=9)

        # Grid lines
        if self.gridlines_check.isChecked() and self.ca.rows <= 120:
            self.ax_main.set_xticks(np.arange(-.5, self.ca.cols, 1), minor=True)
            self.ax_main.set_yticks(np.arange(-.5, self.ca.rows, 1), minor=True)
            self.ax_main.grid(which='minor', color='#313244', linewidth=0.2)
        else:
            self.ax_main.grid(False, which='minor')

        # Title
        rule = f"B{''.join(map(str,self.ca.birth))}/S{''.join(map(str,self.ca.survive))}"
        self.ax_main.set_title(f"{self.ca.name}  [{rule}]  Gen {self.ca.generation}",
                               color='#cdd6f4', fontsize=12, fontweight='bold')

        # Population plot
        ph = self.ca.population_history
        if ph:
            x = range(len(ph))
            self.pop_line.set_data(x, ph)
            self.ax_pop.set_xlim(0, max(len(ph),20))
            self.ax_pop.set_ylim(0, max(max(ph)*1.15, 10))
            # Fill under curve
            if self.pop_fill is not None:
                self.pop_fill.remove()
            self.pop_fill = self.ax_pop.fill_between(x, ph, alpha=0.15, color='#89b4fa')

        # Stats
        pop = self.ca.population()
        total = self.ca.rows * self.ca.cols
        self.stat_gen.setText(str(self.ca.generation))
        self.stat_pop.setText(f"{pop:,}")
        self.stat_clust.setText(str(self.ca.cluster_count()))
        self.stat_big.setText(str(self.ca.largest_cluster()))
        self.stat_pct.setText(f"{pop/total*100:.1f}%")

        self.canvas.draw_idle()

    # ---- export ----
    def _export_video(self):
        vid, _ = QFileDialog.getSaveFileName(self, "Save Video", "ca_video.mp4", "MP4 (*.mp4)")
        aud, _ = QFileDialog.getSaveFileName(self, "Save Audio", "ca_audio.wav", "WAV (*.wav)")
        if not vid or not aud: return
        was = self.running
        if was: self._pause()
        self._apply_rule(); self._apply_audio()

        saved = self.ca.to_dict()
        nf = self.export_frames.value(); fps = self.speed_slider.value()
        af = []

        fig2, ax2 = plt.subplots(figsize=(8,8), facecolor='#1e1e2e')
        ax2.set_facecolor('#181825')
        im2 = ax2.imshow(self.ca.age, cmap=self.cmap_combo.currentText(), vmin=0, vmax=10,
                         interpolation='nearest', aspect='equal')
        ax2.tick_params(colors='#6c7086')
        for sp in ax2.spines.values(): sp.set_color('#45475a')

        try:
            writer = FFMpegWriter(fps=fps, bitrate=1800)
            with writer.saving(fig2, vid, dpi=100):
                for f in range(nf):
                    g, a = self.ca.step()
                    im2.set_data(a*g); im2.set_clim(0, max(10, a.max()))
                    rule = f"B{''.join(map(str,self.ca.birth))}/S{''.join(map(str,self.ca.survive))}"
                    ax2.set_title(f"{self.ca.name} [{rule}] Gen {self.ca.generation}",
                                  color='#cdd6f4', fontsize=12, fontweight='bold')
                    writer.grab_frame()
                    af.append(self.audio.generate(g, a))
                    if f % 50 == 0: print(f"  Frame {f}/{nf}")
            full = np.concatenate(af, axis=0)
            wav_write(aud, self.audio.rate, (full*32767).astype(np.int16))
            QMessageBox.information(self, "Done", f"Video → {vid}\nAudio → {aud}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            plt.close(fig2)
            self.ca = CellularAutomata.from_dict(saved)
            self._rebuild_img(); self._refresh_display()
            if was: self._start()

    def _export_audio(self):
        aud, _ = QFileDialog.getSaveFileName(self, "Save Audio", "ca_audio.wav", "WAV (*.wav)")
        if not aud: return
        was = self.running
        if was: self._pause()
        self._apply_rule(); self._apply_audio()

        saved = self.ca.to_dict()
        nf = self.export_frames.value(); af = []
        try:
            for f in range(nf):
                g, a = self.ca.step()
                af.append(self.audio.generate(g, a))
                if f % 50 == 0: print(f"  Audio frame {f}/{nf}")
            full = np.concatenate(af, axis=0)
            wav_write(aud, self.audio.rate, (full*32767).astype(np.int16))
            QMessageBox.information(self, "Done", f"Audio → {aud}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            self.ca = CellularAutomata.from_dict(saved)
            self._rebuild_img(); self._refresh_display()
            if was: self._start()

    def _save_state(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save", "ca_state.json", "JSON (*.json)")
        if not path: return
        try:
            d = self.ca.to_dict()
            d["audio"] = dict(base_freq=self.audio.base_freq, freq_range=self.audio.freq_range,
                              harmonics=self.audio.harmonics, waveform=self.audio.waveform,
                              scale=self.audio.scale, volume=self.audio.volume)
            d["cmap"] = self.cmap_combo.currentText()
            d["display"] = self.display_combo.currentText()
            with open(path, 'w') as f: json.dump(d, f)
            QMessageBox.information(self, "Saved", path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _load_state(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path) as f: d = json.load(f)
            self.ca = CellularAutomata.from_dict(d)
            if "audio" in d:
                a = d["audio"]
                self.audio.base_freq  = a.get("base_freq",220)
                self.audio.freq_range = a.get("freq_range",800)
                self.audio.harmonics  = a.get("harmonics",[1,2,3])
                self.audio.waveform   = a.get("waveform","sine")
                self.audio.scale      = a.get("scale","Pentatonic")
                self.audio.volume     = a.get("volume",0.5)
                self.base_freq_spin.setValue(self.audio.base_freq)
                self.freq_range_spin.setValue(self.audio.freq_range)
                self.harmonics_input.setText(",".join(map(str,self.audio.harmonics)))
                self.scale_combo.setCurrentText(self.audio.scale)
                self.volume_slider.setValue(int(self.audio.volume*100))
            if "cmap" in d:     self.cmap_combo.setCurrentText(d["cmap"])
            if "display" in d:  self.display_combo.setCurrentText(d["display"])
            self.rows_spin.setValue(self.ca.rows); self.cols_spin.setValue(self.ca.cols)
            self.density_spin.setValue(self.ca.density); self.toroidal_check.setChecked(self.ca.toroidal)
            self.birth_input.setText(",".join(map(str,self.ca.birth)))
            self.survive_input.setText(",".join(map(str,self.ca.survive)))
            self._rebuild_img(); self._refresh_display()
            QMessageBox.information(self, "Loaded", path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ---- cleanup ----
    def closeEvent(self, event):
        self.timer.stop(); sd.stop(); plt.close('all'); event.accept()


# ================================================================
#  ENTRY POINT
# ================================================================

if __name__ == "__main__":
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CAStudio()
    window.show()
    sys.exit(app.exec())