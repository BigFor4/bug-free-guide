#!/usr/bin/env python3
"""
Script tạo file test cho karaoke
- nhac.wav: file nhạc nền 10 giây
- loi.wav: file lời hát 10 giây  
- lyrics_test.json: lời bài hát ngắn
"""

import numpy as np
import json
from scipy.io import wavfile

def create_background_music(filename, duration=10, sample_rate=44100):
    """Tạo nhạc nền đơn giản với melody"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Tạo melody đơn giản với các note
    frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88]  # C4-B4
    melody = np.zeros_like(t)
    
    note_duration = duration / len(frequencies)
    for i, freq in enumerate(frequencies):
        start_idx = int(i * note_duration * sample_rate)
        end_idx = int((i + 1) * note_duration * sample_rate)
        
        # Tạo note với envelope
        note_t = t[start_idx:end_idx]
        if len(note_t) > 0:
            note = np.sin(2 * np.pi * freq * note_t)
            # Envelope để tránh click
            envelope = np.exp(-note_t * 2)
            melody[start_idx:end_idx] = note * envelope * 0.3
    
    # Thêm bass đơn giản
    bass = np.sin(2 * np.pi * 130.81 * t) * 0.1  # C3 bass
    
    # Mix
    audio = melody + bass
    
    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.7
    
    # Convert to 16-bit
    audio_int16 = (audio * 32767).astype(np.int16)
    
    wavfile.write(filename, sample_rate, audio_int16)
    print(f"✅ Đã tạo file nhạc nền: {filename}")

def create_vocal_track(filename, duration=10, sample_rate=44100):
    """Tạo track vocal giả lập để Whisper nhận dạng"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Tạo vocal với các tần số giống giọng người
    vocal_freq = 220  # A3 - tần số cơ bản cho giọng
    
    # Chia thành các đoạn ngắn giống như từng từ
    words_timing = [
        (0, 1.5),    # "Buồn khóe mắt"
        (1.5, 3),    # "mà lặng"
        (3, 4.5),    # "cả đất trời"
        (5, 6.5),    # "Mưa cũng"
        (6.5, 8),    # "ngừng rơi"
        (8, 10),     # "nhường vỡ tan"
    ]
    
    vocal = np.zeros_like(t)
    for start_time, end_time in words_timing:
        start_idx = int(start_time * sample_rate)
        end_idx = int(end_time * sample_rate)
        
        word_t = t[start_idx:end_idx] - start_time
        if len(word_t) > 0:
            # Tạo vocal với harmonics để giống giọng người
            fundamental = np.sin(2 * np.pi * vocal_freq * word_t)
            harmonic2 = np.sin(2 * np.pi * vocal_freq * 2 * word_t) * 0.3
            harmonic3 = np.sin(2 * np.pi * vocal_freq * 3 * word_t) * 0.1
            
            # Envelope để tạo hiệu ứng từng từ
            envelope = np.exp(-word_t * 1.5) * (1 - np.exp(-word_t * 10))
            
            word_sound = (fundamental + harmonic2 + harmonic3) * envelope * 0.5
            vocal[start_idx:end_idx] = word_sound
    
    # Thêm noise nhẹ để realistic hơn
    noise = np.random.normal(0, 0.01, len(vocal))
    vocal = vocal + noise
    
    # Normalize
    vocal = vocal / np.max(np.abs(vocal)) * 0.6
    
    # Convert to 16-bit
    vocal_int16 = (vocal * 32767).astype(np.int16)
    
    wavfile.write(filename, sample_rate, vocal_int16)
    print(f"✅ Đã tạo file vocal: {filename}")

def create_test_lyrics():
    """Tạo file lyrics test ngắn"""
    lyrics_data = {
        "lyrics1": [
            "Buồn khóe mắt mà lặng cả đất trời",
            "Mưa cũng ngừng rơi nhường vỡ tan cho giọt nước mắt"
        ],
        "lyrics2": [
            "Từng xem nhau là tất cả",
            "Tự dưng ta thành kẻ lạ"
        ]
    }
    
    with open("lyrics_test.json", "w", encoding="utf-8") as f:
        json.dump(lyrics_data, f, ensure_ascii=False, indent=2)
    
    print("✅ Đã tạo file lyrics test: lyrics_test.json")

def main():
    print("🎵 Đang tạo file test...")
    
    # Tạo các file âm thanh
    create_background_music("nhac_test.wav", duration=10)
    create_vocal_track("loi_test.wav", duration=10)

    # Tạo file lyrics
    create_test_lyrics()
    
    print("\n✅ Hoàn thành! Đã tạo:")
    print("  - nhac_test.wav (nhạc nền 10s)")
    print("  - loi_test.wav (vocal 10s)")
    print("  - lyrics_test.json (lời bài hát ngắn)")
    
    print("\n📋 Để test karaoke:")
    print("  1. Chạy: python auto_lyrics_karaoke.py")
    print("  2. Hoặc sửa main() để dùng lyrics_test.json")

if __name__ == "__main__":
    main()