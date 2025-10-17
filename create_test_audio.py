#!/usr/bin/env python3
"""
Script tạo file âm thanh test cho karaoke
- nhac.wav: File nhạc nền với giai điệu đơn giản
- loi.wav: File lời hát với tiếng nói giả lập
"""

import numpy as np
import wave
import json

# Cấu hình âm thanh
SAMPLE_RATE = 44100  # Hz
DURATION = 30        # giây (30s cho test)
AMPLITUDE = 0.3      # Độ lớn âm thanh

def create_music_track():
    """Tạo nhạc nền với giai điệu đơn giản"""
    print("🎵 Tạo file nhac.wav...")
    
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION))
    
    # Tạo giai điệu với các nốt nhạc cơ bản
    # C4=261.63, D4=293.66, E4=329.63, F4=349.23, G4=392, A4=440, B4=493.88
    notes = [261.63, 293.66, 329.63, 349.23, 392, 440, 493.88, 523.25]  # C4 đến C5
    
    music = np.zeros_like(t)
    
    # Tạo chord progression đơn giản
    for i, freq in enumerate(notes):
        # Mỗi nốt kéo dài khoảng 3.75s
        start_time = i * (DURATION / len(notes))
        end_time = (i + 1) * (DURATION / len(notes))
        
        mask = (t >= start_time) & (t < end_time)
        
        # Tạo hợp âm với tần số chính và harmonic
        note = (np.sin(2 * np.pi * freq * t[mask]) * 0.4 +
                np.sin(2 * np.pi * freq * 1.25 * t[mask]) * 0.2 +  # Perfect fifth
                np.sin(2 * np.pi * freq * 1.5 * t[mask]) * 0.15)   # Octave
        
        # Thêm envelope để âm thanh mượt hơn
        fade_in = np.linspace(0, 1, int(0.1 * SAMPLE_RATE))
        fade_out = np.linspace(1, 0, int(0.1 * SAMPLE_RATE))
        
        if len(note) > len(fade_in) + len(fade_out):
            note[:len(fade_in)] *= fade_in
            note[-len(fade_out):] *= fade_out
        
        music[mask] = note * AMPLITUDE

    # Thêm reverb đơn giản
    delay_samples = int(0.1 * SAMPLE_RATE)  # 100ms delay
    if len(music) > delay_samples:
        music[delay_samples:] += music[:-delay_samples] * 0.3
    
    return (music * 32767).astype(np.int16)

def create_vocal_track():
    """Tạo file lời hát giả lập với tiếng bíp tần số khác nhau"""
    print("🎤 Tạo file loi.wav...")
    
    # Load lyrics để biết timing
    with open('lyrics_array.json', 'r', encoding='utf-8') as f:
        lyrics_data = json.load(f)
    
    all_lyrics = lyrics_data['lyrics1'] + lyrics_data['lyrics2']
    
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION))
    vocal = np.zeros_like(t)
    
    # Tạo "từ" giả lập với các tần số khác nhau
    word_frequencies = [200, 250, 300, 350, 400, 450, 500, 550]  # Hz
    
    current_time = 2.0  # Bắt đầu hát sau 2s
    words_per_second = 3  # Tốc độ hát
    
    word_count = 0
    for line_idx, line in enumerate(all_lyrics[:10]):  # Chỉ lấy 10 dòng đầu cho test 30s
        words_in_line = line.split()
        
        for word_idx, word in enumerate(words_in_line):
            if current_time >= DURATION - 1:
                break
                
            # Tần số cho từ này
            freq = word_frequencies[word_count % len(word_frequencies)]
            
            # Thời gian cho 1 từ
            word_duration = 0.3 + len(word) * 0.05  # Từ dài hát lâu hơn
            
            start_sample = int(current_time * SAMPLE_RATE)
            end_sample = int((current_time + word_duration) * SAMPLE_RATE)
            
            if end_sample > len(t):
                break
                
            word_t = t[start_sample:end_sample]
            
            # Tạo âm thanh cho từ với modulation
            word_sound = (np.sin(2 * np.pi * freq * (word_t - current_time)) * 
                         np.exp(-(word_t - current_time) * 2) *  # Decay
                         0.5)
            
            # Thêm formant để giống giọng nói hơn
            word_sound += (np.sin(2 * np.pi * freq * 2.5 * (word_t - current_time)) * 
                          np.exp(-(word_t - current_time) * 3) * 0.2)
            
            vocal[start_sample:end_sample] += word_sound
            
            current_time += word_duration + 0.1  # Khoảng cách giữa các từ
            word_count += 1
        
        # Khoảng cách giữa các dòng
        current_time += 0.5
        
        if current_time >= DURATION - 1:
            break
    
    # Normalize và thêm một chút noise để thực tế hơn
    vocal = vocal * AMPLITUDE
    noise = np.random.normal(0, 0.01, len(vocal))
    vocal += noise
    
    return (vocal * 32767).astype(np.int16)

def save_wav_file(filename, audio_data):
    """Lưu file WAV"""
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_data.tobytes())
    
    print(f"✅ Đã tạo: {filename} ({len(audio_data)/SAMPLE_RATE:.1f}s)")

def main():
    print("🔧 Tạo file âm thanh test cho karaoke...")
    print(f"📊 Cấu hình: {SAMPLE_RATE}Hz, {DURATION}s, Mono")
    
    # Tạo nhạc nền
    music_data = create_music_track()
    save_wav_file('nhac.wav', music_data)
    
    # Tạo lời hát
    vocal_data = create_vocal_track()
    save_wav_file('loi.wav', vocal_data)
    
    print("\n🎉 Hoàn thành! Có thể test karaoke với:")
    print("   python auto_lyrics_karaoke.py")
    
    # Hiển thị thông tin file
    import os
    for filename in ['nhac.wav', 'loi.wav']:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"📁 {filename}: {size:,} bytes ({size/1024/1024:.2f} MB)")

if __name__ == "__main__":
    main()