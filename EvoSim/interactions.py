# interactions.py
import numpy as np
import os
import wave
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSlider,
                               QPushButton, QCheckBox, QGroupBox, QLabel,
                               QComboBox, QScrollArea, QSizePolicy)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen, QPolygonF, QPointF
from config import (GRID_SIZE, NUM_SPECIES, SAMPLE_RATE, FPS, RECORD_FORMATS,
                    ZONE_SIZE, DISASTER_INTERVAL)
from state import init_state
from visuals import render_base_image, PopGraphWidget


def _apply_brush(S, x, y, alive_val):
    r = S.get('brush_radius', 3)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and dx * dx + dy * dy <= r * r:
                S['alive'][nx, ny] = alive_val
                if alive_val:
                    S['energy'][nx, ny] = 0.5
                    S['stage'][nx, ny] = 1
                    S['age'][nx, ny] = 0
                else:
                    S['stage'][nx, ny] = 0
                    S['fade'][nx, ny] = 0.5


class Recorder:
    def __init__(self):
        self.writer = None
        self.audio_frames = []
        self.recording = False
        self.format_key = list(RECORD_FORMATS.keys())[0]
        self.width, self.height = 1920, 1080
        self.video_path = ''

    def start(self, format_key=None):
        if format_key:
            self.format_key = format_key
        fmt = RECORD_FORMATS.get(self.format_key, list(RECORD_FORMATS.values())[0])
        self.width, self.height = fmt['width'], fmt['height']
        tag = 'shorts' if self.height > self.width else 'youtube'
        self.video_path = f'{tag}_{self.width}x{self.height}.mp4'
        try:
            import imageio
            self.writer = imageio.get_writer(self.video_path, fps=FPS, quality=8)
            self.audio_frames = []
            self.recording = True
            print(f"▶ Recording started: {self.video_path}")
            return self.video_path
        except ImportError:
            print("MP4 recording requires `imageio` and `imageio-ffmpeg`.")
            return None
        except Exception as e:
            print(f"Failed to start recording: {e}")
            return None

    def capture_frame(self, S, env, audio_buffer=None):
        if not self.writer:
            return
        try:
            frame = self._render_frame(S, env)
            self.writer.append_data(frame)
            if audio_buffer is not None:
                self.audio_frames.append(audio_buffer.copy())
        except Exception as e:
            print(f"Frame capture error: {e}")

    def stop(self):
        if not self.writer:
            return None
        self.writer.close()
        self.writer = None
        self.recording = False
        audio_path = self.video_path.replace('.mp4', '_audio.wav')
        if self.audio_frames:
            self._save_wav(audio_path)
        merged_path = self.video_path.replace('.mp4', '_final.mp4')
        if self._merge_av(self.video_path, audio_path, merged_path):
            print(f"✔ Saved (with audio): {merged_path}")
            return merged_path
        print(f"✔ Saved video: {self.video_path}")
        if self.audio_frames:
            print(f"✔ Saved audio: {audio_path}\n  Install ffmpeg to auto-merge.")
        return self.video_path

    def _render_frame(self, S, env):
        w, h = self.width, self.height
        img = QImage(w, h, QImage.Format_RGB888)
        img.fill(QColor(18, 18, 32))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        if h > w:
            self._layout_shorts(painter, S, env, w, h)
        else:
            self._layout_youtube(painter, S, env, w, h)
        painter.end()
        ptr = img.constBits()
        ptr.setsize(h * w * 3)
        return np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()

    def _layout_youtube(self, p, S, env, w, h):
        m, gs = 30, h - 60
        self._draw_grid(p, S, env, m, m, gs, gs)
        self._draw_stats(p, S, m + gs + m, m, w - gs - 3 * m, h - 2 * m)

    def _layout_shorts(self, p, S, env, w, h):
        m = 20
        p.setPen(QColor(200, 210, 240))
        p.setFont(QFont('Segoe UI', 22, QFont.Bold))
        p.drawText(QRectF(m, 10, w - 2 * m, 34), Qt.AlignCenter, "Evolutionary CA")
        gs = w - 2 * m
        self._draw_grid(p, S, env, m, 52, gs, gs)
        self._draw_stats(p, S, m, 52 + gs + 16, w - 2 * m, h - 52 - gs - 16 - m)

    def _draw_grid(self, p, S, env, x, y, w, h):
        grid_data = render_base_image(S, env)
        gh, gw, gch = grid_data.shape
        qimg = QImage(grid_data.tobytes(), gw, gh, gch * gw, QImage.Format_RGB888).copy()
        p.drawImage(QRectF(x, y, w, h), qimg)

    def _draw_stats(self, p, S, x, y, w, h):
        p.setPen(QPen(QColor(60, 64, 90), 1))
        p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)
        p.setPen(QColor(180, 192, 225))
        cx, cy = x + 14, y + 30
        total_pop = int(S['alive'].sum())
        p.setFont(QFont('Segoe UI', 16, QFont.Bold))
        p.drawText(cx, cy, "Statistics")
        cy += 28
        p.setFont(QFont('Consolas', 13))
        lines = [f"Generation  {S['generation']}", f"Population  {total_pop}"]
        if S['diversity_hist']:
            lines.append(f"Diversity   {S['diversity_hist'][-1]:.3f}")
        if S['energy_hist']:
            lines.append(f"Avg Energy  {S['energy_hist'][-1]:.3f}")
        for ln in lines:
            p.drawText(cx, cy, ln)
            cy += 22
        cy += 8
        p.setFont(QFont('Segoe UI', 16, QFont.Bold))
        p.drawText(cx, cy, "Species")
        cy += 24
        p.setFont(QFont('Consolas', 11))
        cols = [QColor(255, 97, 71), QColor(56, 235, 173), QColor(255, 194, 46), QColor(173, 107, 255)]
        for sp in range(NUM_SPECIES):
            cnt = int((S['alive'] & (S['species'] == sp)).sum())
            p.setPen(cols[sp % len(cols)])
            p.drawText(cx, cy, f"● Species {sp}: {cnt}")
            cy += 20
        cy += 12
        p.setPen(QColor(180, 192, 225))
        p.setFont(QFont('Segoe UI', 16, QFont.Bold))
        p.drawText(cx, cy, "Population")
        cy += 8
        self._draw_graph(p, S, cx, cy, w - 28, min(120, h - (cy - y) - 20))

    def _draw_graph(self, p, S, x, y, w, h):
        p.setPen(QPen(QColor(50, 54, 80), 1))
        p.drawRect(QRectF(x, y, w, h))
        data = list(S['pop_history'])
        if len(data) < 2:
            return
        max_val = max(max(data), 1)
        n = len(data)
        # BUG FIX: use QPolygonF instead of unpacking *pts
        polygon = QPolygonF()
        for i, v in enumerate(data):
            px = x + (i / (n - 1)) * w
            py = y + h - (v / max_val) * (h - 4) - 2
            polygon.append(QPointF(px, py))
        p.setPen(QPen(QColor(137, 180, 250), 2))
        p.drawPolyline(polygon)

    def _save_wav(self, path):
        if not self.audio_frames:
            return
        audio = np.concatenate(self.audio_frames)
        audio_i16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_i16.tobytes())

    def _merge_av(self, vid, aud, out):
        if not os.path.exists(aud):
            return False
        try:
            import subprocess
            subprocess.run(
                ['ffmpeg', '-y', '-i', vid, '-i', aud,
                 '-c:v', 'copy', '-c:a', 'aac', '-shortest', out],
                check=True, capture_output=True, timeout=60
            )
            os.remove(vid)
            os.remove(aud)
            return True
        except Exception:
            return False


class SettingsPanel(QWidget):
    def __init__(self, S, recorder, grid_widget, parent=None):
        super().__init__(parent)
        self.S, self.recorder, self.grid_widget = S, recorder, grid_widget
        self.setFixedWidth(290)

        # Main layout with scroll area
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(6)

        # ── Statistics ──
        sg = QGroupBox("📊 Statistics")
        sl = QVBoxLayout()
        self.lbl_stats = QLabel("Gen: 0 | Pop: 0")
        self.lbl_stats.setWordWrap(True)
        sl.addWidget(self.lbl_stats)
        self.pop_graph = PopGraphWidget()
        sl.addWidget(self.pop_graph)
        sg.setLayout(sl)
        layout.addWidget(sg)

        # ── Simulation ──
        sim_g = QGroupBox("🔬 Simulation")
        sim_l = QVBoxLayout()

        self.sld_speed, self.lbl_speed = self._make_slider(
            "Speed", 1, 5, S['sim_speed'],
            lambda v: S.__setitem__('sim_speed', v), sim_l)

        self.sld_density, self.lbl_density = self._make_slider(
            "Init Density %", 5, 50, int(S['init_density'] * 100),
            lambda v: S.__setitem__('init_density', v / 100.0), sim_l)

        self.sld_mut, self.lbl_mut = self._make_slider(
            "Mutation %", 0, 50, int(S['mutation_rate'] * 100),
            lambda v: S.__setitem__('mutation_rate', v / 100.0), sim_l)

        self.sld_disaster, self.lbl_disaster = self._make_slider(
            "Disaster Freq %", 0, 200, int(S['disaster_freq'] * 100),
            lambda v: S.__setitem__('disaster_freq', v / 100.0), sim_l)

        sim_btn_row = QHBoxLayout()
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.clicked.connect(self.toggle_pause)
        sim_btn_row.addWidget(self.btn_pause)
        self.btn_step = QPushButton("⏭ Step")
        self.btn_step.clicked.connect(self.request_single_step)
        sim_btn_row.addWidget(self.btn_step)
        sim_l.addLayout(sim_btn_row)

        sim_l.addWidget(self._btn("🔄 Reset Simulation", self.reset_simulation))
        sim_g.setLayout(sim_l)
        layout.addWidget(sim_g)

        # ── Audio ──
        ag = QGroupBox("🔊 Audio")
        al = QVBoxLayout()
        self.chk_sound = QCheckBox("Sound On")
        self.chk_sound.setChecked(S['sound_on'])
        self.chk_sound.toggled.connect(lambda v: S.__setitem__('sound_on', v))
        al.addWidget(self.chk_sound)

        self.sld_vol, self.lbl_vol = self._make_slider(
            "Volume %", 0, 100, int(S['volume'] * 100),
            lambda v: S.__setitem__('volume', v / 100.0), al)

        self.sld_reverb, self.lbl_reverb = self._make_slider(
            "Reverb %", 0, 150, int(S['reverb_mix'] * 100),
            lambda v: S.__setitem__('reverb_mix', v / 100.0), al)

        self.sld_warmth, self.lbl_warmth = self._make_slider(
            "Warmth %", 0, 100, int(S['warmth'] * 100),
            lambda v: S.__setitem__('warmth', v / 100.0), al)

        ag.setLayout(al)
        layout.addWidget(ag)

        # ── Visuals ──
        vg = QGroupBox("🎨 Visuals")
        vl = QVBoxLayout()
        self.chk_bloom = QCheckBox("Bloom Effect")
        self.chk_bloom.setChecked(S['bloom_on'])
        self.chk_bloom.toggled.connect(lambda v: S.__setitem__('bloom_on', v))
        vl.addWidget(self.chk_bloom)

        self.sld_bloom, self.lbl_bloom = self._make_slider(
            "Bloom Str %", 0, 100, int(S['bloom_strength'] * 100),
            lambda v: S.__setitem__('bloom_strength', v / 100.0), vl)

        self.chk_zones = QCheckBox("Show Zone Lines")
        self.chk_zones.setChecked(S['show_zones'])
        self.chk_zones.toggled.connect(lambda v: S.__setitem__('show_zones', v))
        vl.addWidget(self.chk_zones)

        self.chk_energy = QCheckBox("Show Energy Map")
        self.chk_energy.setChecked(S['show_energy'])
        self.chk_energy.toggled.connect(lambda v: S.__setitem__('show_energy', v))
        vl.addWidget(self.chk_energy)

        vg.setLayout(vl)
        layout.addWidget(vg)

        # ── Brush ──
        bg = QGroupBox("🖌 Brush")
        bl = QVBoxLayout()
        self.sld_brush, self.lbl_brush = self._make_slider(
            "Radius", 1, 10, S['brush_radius'],
            lambda v: S.__setitem__('brush_radius', v), bl)
        bl.addWidget(QLabel("Left-click: paint | Right-click: erase"))
        bg.setLayout(bl)
        layout.addWidget(bg)

        # ── Recording ──
        rg = QGroupBox("🎬 Recording")
        rl = QVBoxLayout()
        rl.addWidget(QLabel("Format:"))
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.addItems(list(RECORD_FORMATS.keys()))
        rl.addWidget(self.cmb_fmt)
        self.btn_rec = QPushButton("⏺  Start Recording")
        self.btn_rec.setStyleSheet("QPushButton { color: #f38ba8; font-weight: bold; }")
        self.btn_rec.clicked.connect(self.toggle_recording)
        rl.addWidget(self.btn_rec)
        self.lbl_rec = QLabel("")
        self.lbl_rec.setWordWrap(True)
        rl.addWidget(self.lbl_rec)
        rg.setLayout(rl)
        layout.addWidget(rg)

        # ── Actions ──
        cg = QGroupBox("⚡ Actions")
        cl = QVBoxLayout()
        cl.addWidget(self._btn("💥 Trigger Disaster", self.trigger_disaster))
        cl.addWidget(self._btn("🎲 Scatter Cells", self.scatter_cells))
        cl.addWidget(self._btn("📷 Save Snapshot", self.save_snapshot))
        cg.setLayout(cl)
        layout.addWidget(cg)

        # ── Keyboard shortcuts info ──
        info = QLabel("Keys: Space=Pause  →=Step  R=Reset")
        info.setStyleSheet("color: #6c7086; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        # Connect mouse signal
        self.grid_widget.mouse_pressed.connect(self.handle_mouse_press)

        # Single-step flag
        self._single_step_requested = False

    def _make_slider(self, label, min_val, max_val, default, callback, layout):
        """Create a slider with a value label, return (slider, label)."""
        row = QHBoxLayout()
        lbl = QLabel(f"{label}: {default}")
        lbl.setMinimumWidth(90)
        sld = QSlider(Qt.Horizontal)
        sld.setRange(min_val, max_val)
        sld.setValue(default)
        sld.setMinimumWidth(80)

        def on_change(v):
            lbl.setText(f"{label}: {v}")
            callback(v)

        sld.valueChanged.connect(on_change)
        row.addWidget(sld, 3)
        row.addWidget(lbl, 2)
        layout.addLayout(row)
        return sld, lbl

    def _btn(self, text, cb):
        b = QPushButton(text)
        b.clicked.connect(cb)
        return b

    def request_single_step(self):
        """Set a flag so the main loop does one step then re-pauses."""
        if self.S['paused']:
            self._single_step_requested = True
            self.S['paused'] = False
            self.btn_pause.setText("⏸ Pause")

    def consume_single_step(self):
        """Called by MainWindow after a step; returns True if we should re-pause."""
        if self._single_step_requested:
            self._single_step_requested = False
            self.S['paused'] = True
            self.btn_pause.setText("▶ Resume")
            return True
        return False

    def reset_simulation(self):
        """Reset the simulation, preserving user settings."""
        saved = {
            'volume': self.S['volume'],
            'mutation_rate': self.S['mutation_rate'],
            'sound_on': self.S['sound_on'],
            'sim_speed': self.S['sim_speed'],
            'brush_radius': self.S['brush_radius'],
            'init_density': self.S['init_density'],
            'reverb_mix': self.S['reverb_mix'],
            'warmth': self.S['warmth'],
            'bloom_on': self.S['bloom_on'],
            'bloom_strength': self.S['bloom_strength'],
            'show_zones': self.S['show_zones'],
            'show_energy': self.S['show_energy'],
            'disaster_freq': self.S['disaster_freq'],
            'paused': False,
        }
        self.S.update(init_state(density=saved['init_density']))
        self.S.update(saved)

    def toggle_recording(self):
        if self.S['recording']:
            path = self.recorder.stop()
            self.S['recording'] = False
            self.btn_rec.setText("⏺  Start Recording")
            self.btn_rec.setStyleSheet("QPushButton { color: #f38ba8; font-weight: bold; }")
            self.lbl_rec.setText(f"Saved: {path}" if path else "")
        else:
            path = self.recorder.start(self.cmb_fmt.currentText())
            if path:
                self.S['recording'] = True
                self.btn_rec.setText("⏹  Stop Recording")
                self.btn_rec.setStyleSheet("QPushButton { color: #a6e3a1; font-weight: bold; }")
                self.lbl_rec.setText("Recording…")
            else:
                self.lbl_rec.setText("Failed to start recording")

    def toggle_pause(self):
        self.S['paused'] = not self.S['paused']
        self._single_step_requested = False
        self.btn_pause.setText("▶ Resume" if self.S['paused'] else "⏸ Pause")

    def trigger_disaster(self):
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = 8
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dm = ((xx - cx) ** 2 + (yy - cy) ** 2 < rad ** 2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.8)
        self.S['alive'][dm] = False
        self.S['stage'][dm] = 0
        self.S['disaster_flash'] = 8

    def scatter_cells(self):
        n = np.random.randint(15, 50)
        xs, ys = np.random.randint(0, GRID_SIZE, n), np.random.randint(0, GRID_SIZE, n)
        self.S['alive'][xs, ys] = True
        self.S['energy'][xs, ys] = 0.4
        self.S['stage'][xs, ys] = 1
        self.S['age'][xs, ys] = 0
        self.S['species'][xs, ys] = np.random.randint(0, NUM_SPECIES, n).astype(np.int8)

    def save_snapshot(self):
        pixmap = self.grid_widget.grab()
        path = f"snapshot_gen{self.S['generation']}.png"
        if pixmap.save(path):
            self.lbl_rec.setText(f"📷 Saved: {path}")
        else:
            self.lbl_rec.setText("Snapshot failed")

    def handle_mouse_press(self, x, y, button):
        if button == Qt.LeftButton:
            _apply_brush(self.S, x, y, True)
        elif button == Qt.RightButton:
            _apply_brush(self.S, x, y, False)

    def update_stats_display(self, total_pop, sp_pops, diversity, avg_e, gen):
        active_sp = sum(1 for p in sp_pops if p > 0)
        rec_stat = "🔴 REC" if self.S['recording'] else "OFF"
        sp_str = "  ".join(f"S{i}:{sp_pops[i]}" for i in range(NUM_SPECIES))
        self.lbl_stats.setText(
            f"Gen: {gen}  |  Pop: {total_pop}\n"
            f"Species: {active_sp}/{NUM_SPECIES}  |  Rec: {rec_stat}\n"
            f"Diversity: {diversity:.3f}  |  Energy: {avg_e:.3f}\n"
            f"{sp_str}"
        )
        # Update mini graph
        self.pop_graph.set_data(self.S['pop_history'], self.S['species_hist'])