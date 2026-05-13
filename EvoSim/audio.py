# audio.py
import numpy as np
import sounddevice as sd
from config import (SAMPLE_RATE, DURATION_PER_FRAME, MAX_VOICES, NUM_SPECIES,
                    BASE_MIDI_NOTE, REVERB_TAPS, WARMTH_ALPHA, GRID_SIZE, midi_to_freq)

_WT_LEN = 2048
_t = np.linspace(0, 1, _WT_LEN, endpoint=False, dtype=np.float32)

def _wt_sine(): return np.sin(2 * np.pi * _t)
def _wt_warm():
    w = (np.sin(2*np.pi*_t)*1.0 + np.sin(4*np.pi*_t)*0.30 + np.sin(6*np.pi*_t)*0.10 + np.sin(8*np.pi*_t)*0.04)
    return w / np.max(np.abs(w))
def _wt_bell():
    w = (np.sin(2*np.pi*_t)*1.0 + np.sin(2*np.pi*_t*2.756)*0.35 + np.sin(2*np.pi*_t*5.404)*0.15 + np.sin(2*np.pi*_t*8.933)*0.07)
    return w / np.max(np.abs(w))
def _wt_pad():
    w = (np.sin(2*np.pi*_t)*1.0 + np.sin(2*np.pi*_t*2.0)*0.40 + np.sin(2*np.pi*_t*3.0)*0.12 + np.sin(2*np.pi*_t*0.5)*0.18)
    return w / np.max(np.abs(w))

WAVETABLES = {
    'sine': _wt_sine().astype(np.float32), 'warm': _wt_warm().astype(np.float32),
    'bell': _wt_bell().astype(np.float32), 'pad': _wt_pad().astype(np.float32),
}

class DelayReverb:
    def __init__(self, taps, sr=SAMPLE_RATE):
        self.delays = [int(d * sr) for d, _ in taps]
        self.decays = [dc for _, dc in taps]
        self.buffers = [np.zeros(dl, dtype=np.float32) for dl in self.delays]
        self.ptrs = [0] * len(self.delays)
        self.wet_gain = 0.30 / max(len(taps), 1)

    def process(self, block: np.ndarray) -> np.ndarray:
        n = len(block)
        wet = np.zeros(n, dtype=np.float32)
        for i, (dl, dc, buf) in enumerate(zip(self.delays, self.decays, self.buffers)):
            ptr = self.ptrs[i]
            read_idx = np.arange(ptr, ptr + n) % dl
            read = buf[read_idx]
            write = block + read * dc
            write_idx = np.arange(ptr, ptr + n) % dl
            buf[write_idx] = write
            wet += read * self.wet_gain
            self.ptrs[i] = (ptr + n) % dl
        return block + wet

class AudioEngine:
    def __init__(self):
        self.frame_samples = int(DURATION_PER_FRAME * SAMPLE_RATE)
        self.audio_buffer  = np.zeros(self.frame_samples, dtype=np.float32)
        self.prev_buf      = np.zeros(self.frame_samples, dtype=np.float32)
        self.crossfade_len = min(2048, self.frame_samples // 2)
        self.t_audio       = np.linspace(0, DURATION_PER_FRAME, self.frame_samples, endpoint=False).astype(np.float32)
        self.fade_in  = np.linspace(0, 1, self.crossfade_len, dtype=np.float32) ** 2
        self.fade_out = np.linspace(1, 0, self.crossfade_len, dtype=np.float32) ** 2

        env_len = min(600, self.frame_samples // 4)
        self.frame_env = np.ones(self.frame_samples, dtype=np.float32)
        self.frame_env[:env_len]  = np.linspace(0, 1, env_len) ** 1.5
        self.frame_env[-env_len:] = np.linspace(1, 0, env_len) ** 1.5

        self.reverb = DelayReverb(REVERB_TAPS)
        self.lpf_state = 0.0
        self.stream = None

    def synthesize(self, active_notes, volume, sound_on):
        new = np.zeros(self.frame_samples, dtype=np.float32)
        if sound_on and active_notes:
            if len(active_notes) > MAX_VOICES:
                active_notes.sort(key=lambda n: n[1], reverse=True)
                active_notes = active_notes[:MAX_VOICES]
            freqs = np.array([n[0] for n in active_notes], dtype=np.float32)
            amps  = np.array([n[1] for n in active_notes], dtype=np.float32)
            wt_names = [n[2] if len(n) > 2 else 'warm' for n in active_notes]
            signal = np.zeros(self.frame_samples, dtype=np.float64)

            for i in range(len(freqs)):
                wt = WAVETABLES.get(wt_names[i], WAVETABLES['warm'])
                phase_inc = freqs[i] * _WT_LEN / SAMPLE_RATE
                phases = np.arange(self.frame_samples, dtype=np.float64) * phase_inc
                idx_f = phases % _WT_LEN
                idx0 = idx_f.astype(np.int32) % _WT_LEN
                idx1 = (idx0 + 1) % _WT_LEN
                frac = (idx_f - np.floor(idx_f)).astype(np.float32)
                wave = wt[idx0] * (1.0 - frac) + wt[idx1] * frac
                signal += wave.astype(np.float64) * amps[i]

            signal *= self.frame_env
            signal = self.reverb.process(signal.astype(np.float32)).astype(np.float64)

            alpha = WARMTH_ALPHA
            out = np.empty_like(signal)
            out[0] = alpha * signal[0] + (1 - alpha) * self.lpf_state
            for i in range(1, len(signal)):
                out[i] = alpha * signal[i] + (1 - alpha) * out[i-1]
            self.lpf_state = out[-1]
            signal = out

            signal = np.tanh(signal * 1.5) * volume
            new = signal.astype(np.float32)
        else:
            new = self.reverb.process(new) * volume

        new[:self.crossfade_len] = (
            self.prev_buf[:self.crossfade_len] * self.fade_out +
            new[:self.crossfade_len] * self.fade_in
        )
        self.audio_buffer[:] = new
        self.prev_buf[:]     = new

    def callback(self, outdata, frames, time_info, status): outdata[:] = self.audio_buffer.reshape(-1, 1)
    def start(self):
        self.stream = sd.OutputStream(channels=1, callback=self.callback, samplerate=SAMPLE_RATE, blocksize=self.frame_samples, dtype='float32')
        self.stream.start()
    def stop(self):
        if self.stream: self.stream.stop(); self.stream.close()
    def get_current_buffer(self):
        return self.audio_buffer.copy()

_SP_WAVEFORMS = ['warm', 'pad', 'bell', 'warm', 'pad', 'bell']

def get_active_notes(S, note_map):
    active_notes = []
    cells_per_sp = max(1, (MAX_VOICES - 4) // NUM_SPECIES)
    total_pop = int(S['alive'].sum())

    for sp in range(NUM_SPECIES):
        mask = S['alive'] & (S['species'] == sp)
        idx  = np.where(mask)
        nc   = len(idx[0])
        if nc == 0: continue
        wt = _SP_WAVEFORMS[sp % len(_SP_WAVEFORMS)]

        cx, cy = float(idx[0].mean()), float(idx[1].mean())
        ci, cj = int(np.clip(cx, 0, GRID_SIZE-1)), int(np.clip(cy, 0, GRID_SIZE-1))
        midi_root = note_map[ci, cj]
        f_root  = float(np.clip(midi_to_freq(midi_root), 40, 800))
        amp_base = min(0.10, 0.015 + nc / (GRID_SIZE * GRID_SIZE) * 1.5)
        active_notes.append((f_root, amp_base, wt))
        active_notes.append((f_root * (2 ** (7/12)), amp_base * 0.45, wt))
        active_notes.append((f_root * 2.0, amp_base * 0.25, 'sine'))

        n_tex = min(cells_per_sp, nc)
        if n_tex > 0:
            chosen = np.random.choice(nc, n_tex, replace=False)
            for ch in chosen:
                x, y = idx[0][ch], idx[1][ch]
                midi = note_map[x, y] + S['melody_offset'][x, y]
                freq = float(np.clip(midi_to_freq(midi) * S['tone_mod'][x, y], 40, 2000))
                e = float(S['energy'][x, y])
                stg = int(S['stage'][x, y])
                if   stg == 1: t_amp, t_wt = 0.025, 'bell'
                elif stg == 2: t_amp, t_wt = 0.015 + e * 0.03, wt
                elif stg == 3: t_amp, t_wt = 0.035 + e * 0.02, 'pad'
                elif stg == 4: t_amp, t_wt = 0.018, 'bell'
                else:          t_amp, t_wt = 0.010, 'sine'
                active_notes.append((freq, t_amp, t_wt))

    if total_pop > 0:
        active_notes.append((midi_to_freq(BASE_MIDI_NOTE) * 0.5, 0.008, 'sine'))

    return active_notes