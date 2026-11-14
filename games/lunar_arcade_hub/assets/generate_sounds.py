"""Generate the hub's sound effects procedurally (no external assets needed).

Run:  python assets/generate_sounds.py
Writes 16-bit stereo WAV files into assets/sounds/.
"""

import array
import math
import os
import random
import wave

SR = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


def envelope(i, n, attack=0.01, release=0.35):
    t = i / SR
    a = min(1.0, t / max(attack, 1e-4))
    r_start = n / SR * (1 - release)
    if t < r_start:
        r = 1.0
    else:
        r = max(0.0, 1.0 - (t - r_start) / max(1e-4, n / SR - r_start))
    return a * (r ** 1.6)


def osc(phase, wave_type):
    if wave_type == "sine":
        return math.sin(phase)
    if wave_type == "square":
        return 1.0 if math.sin(phase) >= 0 else -1.0
    if wave_type == "saw":
        frac = (phase / math.tau) % 1.0
        return 2.0 * frac - 1.0
    if wave_type == "triangle":
        frac = (phase / math.tau) % 1.0
        return 4 * abs(frac - 0.5) - 1
    return math.sin(phase)


def tone(freq, dur, vol=0.5, wave_type="sine", attack=0.008, release=0.5,
         freq_end=None, vibrato=0.0):
    n = int(SR * dur)
    samples = []
    phase = 0.0
    for i in range(n):
        t = i / SR
        f = freq if freq_end is None else freq + (freq_end - freq) * (t / dur)
        if vibrato:
            f *= 1.0 + vibrato * math.sin(math.tau * 5 * t)
        phase += math.tau * f / SR
        v = osc(phase, wave_type) * envelope(i, n, attack, release) * vol
        samples.append(v)
    return samples


def silence(dur):
    return [0.0] * int(SR * dur)


def mix(*tracks):
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return out


def seq(*tracks):
    out = []
    for t in tracks:
        out.extend(t)
    return out


def write_wav(name, samples):
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = min(1.0, 0.85 / peak)
    data = array.array("h")
    for s in samples:
        v = int(max(-1.0, min(1.0, s * scale)) * 32767)
        data.append(v)
        data.append(v)
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", path)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    random.seed(3)

    write_wav("click.ogg", tone(1050, 0.05, 0.4, "square", release=0.8))
    write_wav("pop.ogg", tone(380, 0.11, 0.5, "sine", freq_end=900,
                              release=0.7))
    write_wav("hit.ogg", mix(tone(880, 0.16, 0.45, "sine", freq_end=1320),
                             tone(1760, 0.12, 0.18, "sine")))
    write_wav("combo.ogg", seq(tone(1046, 0.07, 0.4), tone(1318, 0.09, 0.4),
                               tone(1568, 0.14, 0.35)))
    write_wav("miss.ogg", tone(190, 0.16, 0.5, "saw", freq_end=120,
                               release=0.6))
    write_wav("error.ogg", tone(150, 0.2, 0.45, "square", release=0.4))
    write_wav("success.ogg", seq(tone(660, 0.09, 0.35), tone(880, 0.09, 0.35),
                                 tone(1100, 0.09, 0.35), tone(1320, 0.22, 0.35)))
    write_wav("countdown.ogg", tone(520, 0.13, 0.4, "sine", release=0.5))
    write_wav("go.ogg", tone(880, 0.24, 0.5, "sine", release=0.6))
    write_wav("gameover.ogg", seq(tone(660, 0.14, 0.35), tone(520, 0.14, 0.35),
                                  tone(392, 0.16, 0.35), tone(262, 0.32, 0.35)))
    write_wav("tick.ogg", tone(1300, 0.03, 0.25, "square", release=0.9))


if __name__ == "__main__":
    main()
