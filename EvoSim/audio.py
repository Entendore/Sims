# audio.py
import numpy as np
import sounddevice as sd
from config import FPS, SAMPLE_RATE, DURATION_PER_FRAME, MAX_VOICES, NUM_SPECIES, BASE_MIDI_NOTE
from utils import midi_to_freq

class AudioEngine:
    def __init__(self):
        self.frame_samples = int(DURATION_PER_FRAME * SAMPLE_RATE)
        self.audio_buffer = np.zeros(self.frame_samples, dtype=np.float32)
        self.prev_audio_buf = np.zeros(self.frame_samples, dtype=np.float32)
        self.crossfade_len = min(512, self.frame_samples // 4)

        self.t_audio = np.linspace(0, DURATION_PER_FRAME, self.frame_samples, endpoint=False).astype(np.float32)
        self.fade_in = np.linspace(0, 1, self.crossfade_len, dtype=np.float32)
        self.fade_out = np.linspace(1, 0, self.crossfade_len, dtype=np.float32)

        _env_len = min(128, self.frame_samples // 8)
        self.frame_envelope = np.ones(self.frame_samples, dtype=np.float32)
        self.frame_envelope[:_env_len] = np.linspace(0, 1, _env_len)
        self.frame_envelope[-_env_len:] = np.linspace(1, 0, _env_len)

        self.stream = None

    def synthesize(self, active_notes, volume):
        if not active_notes:
            new = np.zeros(self.frame_samples, dtype=np.float32)
            new[:self.crossfade_len] = self.prev_audio_buf[:self.crossfade_len] * self.fade_out
            self.audio_buffer[:] = new
            self.prev_audio_buf[:] = new
            return

        if len(active_notes) > MAX_VOICES:
            active_notes.sort(key=lambda n: n[1], reverse=True)
            active_notes = active_notes[:MAX_VOICES]

        freqs = np.array([n[0] for n in active_notes], dtype=np.float32)
        amps  = np.array([n[1] for n in active_notes], dtype=np.float32)

        signal = np.zeros(self.frame_samples, dtype=np.float64)
        for h_idx, h_amp in enumerate([1.0, 0.35, 0.12]):
            h_freqs = freqs * (h_idx + 1)
            valid = h_freqs < (SAMPLE_RATE * 0.45)
            if not np.any(valid):
                break
            phases = 2.0 * np.pi * h_freqs[:, None] * self.t_audio[None, :]
            wave   = amps[:, None] * h_amp * np.sin(phases)
            wave[~valid] = 0.0
            signal += wave.sum(axis=0)

        signal *= self.frame_envelope

        for i in range(3):
            ds = int(SAMPLE_RATE * (0.025 + i * 0.018))
            if ds < self.frame_samples:
                signal[ds:] += (0.22 ** (i + 1)) * signal[:self.frame_samples - ds]

        mx = np.max(np.abs(signal))
        if mx > 0:
            signal = signal / mx * volume
        signal = signal.astype(np.float32)

        signal[:self.crossfade_len] = (
            self.prev_audio_buf[:self.crossfade_len] * self.fade_out
            + signal[:self.crossfade_len] * self.fade_in
        )

        self.audio_buffer[:] = signal
        self.prev_audio_buf[:] = signal

    def callback(self, outdata, frames, time_info, status):
        outdata[:] = self.audio_buffer.reshape(-1, 1)

    def start(self):
        self.stream = sd.OutputStream(channels=1, callback=self.callback,
                                      samplerate=SAMPLE_RATE, blocksize=self.frame_samples,
                                      dtype='float32')
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()

def get_active_notes(S, note_map):
    active_notes = []
    cells_per_sp = max(1, MAX_VOICES // NUM_SPECIES)
    total_pop = int(S['alive'].sum())

    for sp in range(NUM_SPECIES):
        mask = S['alive'] & (S['species'] == sp)
        idx  = np.where(mask)
        nc   = len(idx[0])
        if nc == 0:
            continue
        if nc > cells_per_sp:
            chosen = np.random.choice(nc, cells_per_sp, replace=False)
            xs, ys = idx[0][chosen], idx[1][chosen]
        else:
            xs, ys = idx[0], idx[1]

        for x, y in zip(xs, ys):
            midi = note_map[x, y] + S['melody_offset'][x, y]
            freq = midi_to_freq(midi) * S['tone_mod'][x, y]
            freq = float(np.clip(freq, 30, 3500))
            stg  = int(S['stage'][x, y])
            e    = float(S['energy'][x, y])

            if   stg == 1: amp = 0.12
            elif stg == 2: amp = 0.06 + e * 0.12
            elif stg == 3: amp = 0.18; freq *= 1.5
            elif stg == 4: amp = 0.04
            else:          amp = 0.03
            active_notes.append((freq, amp))

    if total_pop > 0:
        active_notes.append((midi_to_freq(BASE_MIDI_NOTE) * 0.5, 0.015))
        
    return active_notes