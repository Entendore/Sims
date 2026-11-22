# recorder.py
"""
Video recording for CivSim — exports simulation as MP4.

Performance strategy:
  1. STREAMING WRITER — frames written to disk immediately via imageio.v2;
     constant memory regardless of recording length.  Falls back to batch
     v3.imwrite if v2 is unavailable.
  2. CACHED STATIC LAYER — terrain + rivers rendered once into a QImage;
     each frame copies this layer and draws only dynamic elements on top,
     saving hundreds of drawPolygon calls per frame.
  3. PRE-COMPUTED GEOMETRY — hex positions, polygons, brushes cached once.
  4. EFFICIENT CONVERSION — QImage→numpy handles row-stride padding correctly.

Supports:
  - Recording from the GUI (captures QWidget frames in real-time).
  - Recording from the start of the simulation (headless offscreen rendering).
  - Recording from the current state (offscreen, one frame per step).

Requires: pip install imageio[ffmpeg] numpy
"""
import math
import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import (
    QImage, QPainter, QColor, QBrush, QPen, QFont, QPolygonF,
)

from config import CONFIG, active_disasters
from hex_utils import hex_to_pixel
from data import TERRAINS

# ======================================================================
# imageio availability
# ======================================================================
try:
    import imageio.v2 as iio_v2
    _HAS_V2 = True
except ImportError:
    _HAS_V2 = False

try:
    import imageio.v3 as iio_v3
    _HAS_V3 = True
except ImportError:
    _HAS_V3 = False

HAS_IMAGEIO = _HAS_V2 or _HAS_V3

# Approximate compressed bytes per frame (H.264 @ 720p)
_APPROX_BYTES_PER_FRAME = 50_000


# ======================================================================
# QImage ↔ numpy helpers
# ======================================================================
def _qimage_to_array(image: QImage) -> np.ndarray:
    """Convert an RGB888 QImage to an H×W×3 uint8 numpy array (copy).

    Handles potential row-padding in QImage's internal layout (rows are
    padded to 4-byte boundaries at certain widths).
    """
    if image.format() != QImage.Format_RGB888:
        image = image.convertToFormat(QImage.Format_RGB888)
    width = image.width()
    height = image.height()
    bpl = image.bytesPerLine()
    ptr = image.bits()
    ptr.setsize(height * bpl)
    raw = np.frombuffer(ptr, np.uint8)
    if bpl == width * 3:
        # No padding — fast path
        arr = raw.reshape((height, width, 3))
    else:
        # Trim per-row padding
        arr = np.ascontiguousarray(
            raw.reshape((height, bpl))[:, :width * 3].reshape((height, width, 3))
        )
    return arr.copy()


def _capture_widget_as_array(widget, width, height):
    """Grab a QWidget, scale to (width, height), return numpy array or None."""
    try:
        pixmap = widget.grab()
        image = pixmap.toImage().convertToFormat(QImage.Format_RGB888)
        image = image.scaled(width, height, aspectRatioMode=1)  # KeepAspectRatio
        return _qimage_to_array(image)
    except Exception:
        return None


# ======================================================================
# Pre-computed hex polygon
# ======================================================================
def _make_hex_poly(cx, cy, size):
    """Create a flat-top hexagon QPolygonF centred at (cx, cy)."""
    points = []
    for i in range(6):
        angle_rad = math.pi / 180 * (60 * i)
        points.append(QPointF(cx + size * math.cos(angle_rad),
                              cy + size * math.sin(angle_rad)))
    return QPolygonF(points)


# ======================================================================
# Render cache — built once per engine instance
# ======================================================================
class _RenderCache:
    """Caches hex positions, polygons, terrain brushes and builds a static
    terrain QImage that can be copied as the base of every frame.

    Terrain and rivers rarely change, so painting 200+ hex polygons every
    frame is wasteful.  Instead we paint them once and blit the result.
    """

    def __init__(self, hex_size, width, height, terrain, rivers):
        self.hex_size = hex_size
        self.width = width
        self.height = height
        self.offset_x = width / 2
        self.offset_y = height / 2

        # Per-hex data
        self.positions: dict[tuple, tuple[float, float]] = {}
        self.polygons: dict[tuple, QPolygonF] = {}
        self.terrain_type: dict[tuple, str] = {}

        # Shared drawing objects (created once, reused)
        self.terrain_brushes: dict[str, QBrush] = {}
        for t, info in TERRAINS.items():
            self.terrain_brushes[t] = QBrush(QColor(info["color"]))

        self.terrain_pen = QPen(QColor("#333333"), 1)
        self.text_pen = QPen(QColor(0, 0, 0, 140))
        self.terrain_font = QFont("Segoe UI Emoji", 8)

        self.rivers = rivers
        self._precompute(terrain)

    def _precompute(self, terrain):
        hs = self.hex_size
        for h, t in terrain.items():
            px, py = hex_to_pixel(*h, hs)
            cx, cy = px + self.offset_x, py + self.offset_y
            self.positions[h] = (cx, cy)
            self.polygons[h] = _make_hex_poly(cx, cy, hs)
            self.terrain_type[h] = t

    def build_static_layer(self) -> QImage:
        """Render terrain hexes + rivers to a QImage (expensive — call once)."""
        image = QImage(self.width, self.height, QImage.Format_RGB888)
        image.fill(QColor("#1a1a2e"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)

        # --- Terrain hexes ---
        painter.setPen(self.terrain_pen)
        painter.setFont(self.terrain_font)
        for h, t in self.terrain_type.items():
            poly = self.polygons[h]
            painter.setBrush(self.terrain_brushes[t])
            painter.drawPolygon(poly)
            # Terrain symbol
            painter.setPen(self.text_pen)
            painter.drawText(poly.boundingRect(), 0x84, TERRAINS[t]["symbol"])
            painter.setPen(self.terrain_pen)

        # --- Rivers (also static) ---
        river_pen = QPen(QColor("#4a90e2"), 2)
        river_font = QFont("Segoe UI Emoji", 7)
        painter.setPen(river_pen)
        painter.setFont(river_font)
        for h in self.rivers:
            pos = self.positions.get(h)
            if pos:
                cx, cy = pos
                painter.drawText(QPointF(cx - 4, cy + 4), "〰")

        painter.end()
        return image


# ======================================================================
# Dynamic layer renderer (only what changes per turn)
# ======================================================================
_DISASTER_ICONS = {
    "flood": "🌊", "drought": "🔥", "plague": "☣️",
    "volcano": "🌋", "earthquake": "💥", "blizzard": "❄️",
}


def _render_dynamic_layers(painter: QPainter, cache: _RenderCache, engine) -> None:
    """Draw all per-turn dynamic elements onto *painter* using cached geometry.

    This is called once per captured frame.  The expensive terrain layer has
    already been blitted, so we only paint:
      - Territory fills
      - Capital markers
      - Disaster icons
      - HUD (turn counter, victory, scoreboard)
    """
    # ----- Territory overlay -----
    territory_pen = QPen(QColor("black"), 2)
    for civ in engine.alive_civs:
        color = QColor(civ.color)
        color.setAlpha(100)
        painter.setBrush(QBrush(color))
        painter.setPen(territory_pen)
        for h in civ.hexes:
            poly = cache.polygons.get(h)
            if poly:
                painter.drawPolygon(poly)

    # ----- Capitals -----
    capital_pen = QPen(QColor("white"), 2)
    capital_font = QFont("Segoe UI Emoji", 14, QFont.Bold)
    painter.setPen(capital_pen)
    painter.setFont(capital_font)
    for civ in engine.alive_civs:
        if civ.capital in civ.hexes:
            pos = cache.positions.get(civ.capital)
            if pos:
                cx, cy = pos
                star = "🌟" if civ.in_golden_age else "⭐"
                painter.drawText(QPointF(cx - 8, cy + 8), star)

    # ----- Disasters -----
    if active_disasters:
        disaster_pen = QPen(QColor("white"), 1)
        disaster_font = QFont("Segoe UI Emoji", 12)
        painter.setPen(disaster_pen)
        painter.setFont(disaster_font)
        for h, (dt, _) in list(active_disasters.items()):
            pos = cache.positions.get(h)
            if pos:
                cx, cy = pos
                painter.drawText(QPointF(cx - 8, cy + 8),
                                 _DISASTER_ICONS.get(dt, "⚠️"))

    # ----- HUD: turn label -----
    hud_pen = QPen(QColor("white"), 1)
    turn_font = QFont("Arial", 14, QFont.Bold)
    painter.setPen(hud_pen)
    painter.setFont(turn_font)
    painter.drawText(10, 25, f"Turn: {engine.turn}")

    # ----- HUD: victory banner -----
    if engine.victor:
        victory_pen = QPen(QColor("#ffd700"), 2)
        victory_font = QFont("Arial", 18, QFont.Bold)
        painter.setPen(victory_pen)
        painter.setFont(victory_font)
        painter.drawText(10, 55, f"🏆 {engine.victor.name} Wins!")

    # ----- HUD: scoreboard -----
    score_font = QFont("Arial", 10)
    painter.setFont(score_font)
    y_pos = 80
    alive = sorted(engine.alive_civs, key=lambda c: c.power, reverse=True)
    for civ in alive[:8]:
        painter.setPen(QPen(QColor(civ.color), 1))
        text = (f"{civ.name} | Pop:{civ.population} "
                f"Hex:{len(civ.hexes)} Era:{civ.era[:3]}")
        painter.drawText(10, y_pos, text)
        y_pos += 18


# ======================================================================
# VideoRecorder — main public class
# ======================================================================
class VideoRecorder:
    """Captures simulation frames and exports to MP4.

    Two recording modes:
      1. **GUI mode** — call ``capture_widget(widget)`` each timer tick.
      2. **Offscreen mode** — call ``capture_offscreen(engine)`` each step.

    For "record from start" use ``export_from_start()`` which creates a
    fresh engine, runs it headlessly, and saves the video — no GUI needed.

    Frames are streamed to disk (constant memory) via imageio.v2 when
    available, otherwise batched and written at close via imageio.v3.
    """

    def __init__(self, filename="civsim_output.mp4", fps=None,
                 width=None, height=None):
        self.filename = filename
        self.fps = fps or CONFIG["recording_fps"]
        self.width = width or CONFIG["recording_width"]
        self.height = height or CONFIG["recording_height"]
        self.recording = False
        self.frame_count = 0

        # Streaming writer state
        self._writer = None           # imageio v2 writer (streaming)
        self._fallback_frames: list = []  # buffer for v3 fallback
        self._streaming = False

        # Offscreen render cache
        self._cache: _RenderCache | None = None
        self._static_layer: QImage | None = None
        self._engine_id: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @staticmethod
    def check_available():
        """Return True if imageio[ffmpeg] is installed."""
        return HAS_IMAGEIO

    def start(self):
        """Begin recording.  Call before any ``capture_*`` method."""
        if not HAS_IMAGEIO:
            raise ImportError(
                "imageio[ffmpeg] required for video export.\n"
                "Install with: pip install imageio[ffmpeg]"
            )
        self.frame_count = 0
        self._fallback_frames = []
        self._cache = None
        self._static_layer = None
        self._engine_id = None

        if _HAS_V2:
            self._writer = iio_v2.get_writer(
                self.filename, fps=self.fps, codec="libx264",
                output_params=["-pix_fmt", "yuv420p"],
            )
            self._streaming = True
        else:
            self._writer = None
            self._streaming = False

        self.recording = True

    def capture_widget(self, widget):
        """Capture a frame from a QWidget (for real-time GUI recording).

        Call this each timer tick while ``self.recording`` is True.
        """
        if not self.recording:
            return
        arr = _capture_widget_as_array(widget, self.width, self.height)
        if arr is not None:
            self._write_frame(arr)
            self.frame_count += 1

    def capture_offscreen(self, engine):
        """Render and capture a frame offscreen (no widget needed).

        Uses a cached static terrain layer so only dynamic elements are
        re-drawn each frame (territory, capitals, disasters, HUD).
        """
        if not self.recording:
            return
        self._ensure_cache(engine)
        # Blit the pre-rendered static layer
        image = self._static_layer.copy()
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        _render_dynamic_layers(painter, self._cache, engine)
        painter.end()

        arr = _qimage_to_array(image)
        self._write_frame(arr)
        self.frame_count += 1

    def stop_and_save(self):
        """Stop recording and finalize the MP4 file.  Returns True on success."""
        if not self.recording or self.frame_count == 0:
            self.recording = False
            return False
        self.recording = False
        try:
            if self._streaming and self._writer is not None:
                self._writer.close()
                self._writer = None
            elif self._fallback_frames and _HAS_V3:
                iio_v3.imwrite(
                    self.filename, self._fallback_frames,
                    fps=self.fps, codec="libx264",
                    output_params=["-pix_fmt", "yuv420p"],
                )
                self._fallback_frames = []
            return True
        except Exception as e:
            print(f"Error saving video: {e}")
            return False

    def cancel(self):
        """Discard the recording without saving."""
        self.recording = False
        if self._streaming and self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
        self._fallback_frames = []
        self._cache = None
        self._static_layer = None

    @property
    def estimated_size_mb(self):
        """Rough estimate of current output file size in MB."""
        return self.frame_count * _APPROX_BYTES_PER_FRAME / (1024 * 1024)

    # ------------------------------------------------------------------
    # Record-from-start convenience
    # ------------------------------------------------------------------
    @staticmethod
    def export_from_start(
        filename="civsim_from_start.mp4",
        fps=None,
        max_turns=None,
        map_radius=None,
        num_civs=None,
    ) -> bool:
        """Create a fresh simulation and record every turn to MP4.

        This is the "record from start of sim" entry point.  It creates a
        brand-new SimEngine, runs it headlessly, and captures every turn.

        Usage (from any module or script)::

            from recorder import VideoRecorder
            VideoRecorder.export_from_start("my_game.mp4", fps=15, max_turns=500)

        Returns True on success.
        """
        if not HAS_IMAGEIO:
            print("ERROR: imageio[ffmpeg] required. "
                  "Install with: pip install imageio[ffmpeg]")
            return False

        # Import here to avoid circular imports at module level
        from engine import SimEngine
        import config

        # Optionally override config for this recording
        if map_radius is not None:
            config.CONFIG["map_radius"] = map_radius
        if num_civs is not None:
            config.CONFIG["num_initial_civs"] = num_civs

        # Reset shared global state for a clean run
        config.history_log.clear()
        config.active_disasters.clear()
        config.cultural_map.clear()
        config.paused = False
        from civilization import Civilization
        Civilization._cid = 0

        engine = SimEngine()
        turns = max_turns or CONFIG["max_turns"]
        actual_fps = fps or CONFIG["recording_fps"]

        rec = VideoRecorder(filename, fps=actual_fps)
        rec.start()

        print(f"Recording from turn 1 to {turns} → {filename}  "
              f"(streaming, {rec.width}×{rec.height} @ {actual_fps} fps)")

        for i in range(turns):
            if engine.victor:
                break
            engine.step()
            rec.capture_offscreen(engine)
            if (i + 1) % 50 == 0:
                print(f"  Turn {i + 1}/{turns} — "
                      f"{rec.frame_count} frames, "
                      f"~{rec.estimated_size_mb:.1f} MB")

        # Hold the final frame for 2 seconds so the end state is visible
        if engine.victor or engine.alive_civs:
            for _ in range(actual_fps * 2):
                rec.capture_offscreen(engine)

        success = rec.stop_and_save()
        if success:
            print(f"✅ Video saved to {filename}  "
                  f"({rec.frame_count} frames, "
                  f"~{rec.estimated_size_mb:.1f} MB)")
        else:
            print("❌ Failed to save video.")
        return success

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _write_frame(self, arr: np.ndarray):
        """Append one frame to the writer (streaming or buffered)."""
        if self._streaming and self._writer is not None:
            self._writer.append_data(arr)
        else:
            self._fallback_frames.append(arr)

    def _ensure_cache(self, engine):
        """Build or rebuild the render cache if the engine instance changed."""
        eid = id(engine)
        if self._cache is not None and self._engine_id == eid:
            return
        hex_size = CONFIG["hex_size"] * 20
        self._cache = _RenderCache(
            hex_size, self.width, self.height,
            engine.terrain, engine.rivers,
        )
        self._static_layer = self._cache.build_static_layer()
        self._engine_id = eid