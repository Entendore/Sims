import math
import numpy as np
import pygame
from config import PHERO_RES

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

def p2g(x, y):
    """Pixel coords to pheromone grid coords."""
    return int(x / PHERO_RES), int(y / PHERO_RES)

class SoundManager:
    def __init__(self):
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

        self.sounds = {
            "collect": self._generate_tone(880, 0.05),        # Short high-pitched chirp
            "deposit": self._generate_tone(660, 0.1),         # Slightly longer mid-tone
            "attack": self._generate_tone(150, 0.15, 'square', 0.4), # Low harsh thud
            "death": self._generate_slide(400, 100, 0.15),    # Descending tone
            "click": self._generate_tone(1000, 0.03, volume=0.2), # UI Click
            "rain_start": self._generate_noise(0.5, 0.3)      # White noise burst
        }

    def play(self, name):
        if name in self.sounds:
            self.sounds[name].play()

    def _generate_tone(self, freq, duration, wave_type='sine', volume=0.3):
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        if wave_type == 'sine':
            wave = np.sin(2 * np.pi * freq * t)
        elif wave_type == 'square':
            wave = np.sign(np.sin(2 * np.pi * freq * t))
        
        envelope = np.linspace(1, 0, len(t))
        wave = wave * envelope * volume

        audio = (wave * 32767).astype(np.int16)
        stereo = np.column_stack((audio, audio))
        return pygame.sndarray.make_sound(stereo)

    def _generate_slide(self, freq_start, freq_end, duration, volume=0.3):
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        freq = np.linspace(freq_start, freq_end, len(t))
        phase = 2 * np.pi * np.cumsum(freq) / sample_rate
        wave = np.sin(phase)

        envelope = np.linspace(1, 0, len(t))
        wave = wave * envelope * volume

        audio = (wave * 32767).astype(np.int16)
        stereo = np.column_stack((audio, audio))
        return pygame.sndarray.make_sound(stereo)

    def _generate_noise(self, duration, volume=0.2):
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        wave = np.random.uniform(-1, 1, n_samples)
        
        envelope = np.linspace(1, 0, n_samples)
        wave = wave * envelope * volume
        
        audio = (wave * 32767).astype(np.int16)
        stereo = np.column_stack((audio, audio))
        return pygame.sndarray.make_sound(stereo)