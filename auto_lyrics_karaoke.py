#!/usr/bin/env python3
import os
import json
import numpy as np
from typing import List, Dict, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import VideoClip, AudioFileClip, CompositeVideoClip, ImageClip

try:
    import whisper
except ImportError:
    whisper = None

WIDTH, HEIGHT, FPS = 1920, 1080, 30
FONT_SIZE = 72
DEFAULT_FONT_PATH = "C:/Windows/Fonts/arial.ttf"
PRE_SHOW_TIME = 4
NEXT_LINE_TRIGGER = 3

class AutoKaraoke:
    def __init__(self, loi_wav, nhac_wav, lyrics_file, bg_image=None):
        self.loi_wav = loi_wav
        self.nhac_wav = nhac_wav
        self.lyrics_file = lyrics_file
        self.bg_image = bg_image
        self.text_color_default = (255, 255, 255)
        self.text_color_sung = (255, 215, 0)  # vàng sáng
        self.stroke_color = (0, 0, 0)
        self.stroke_width = 4
        self.line1_y = HEIGHT - 300
        self.line2_y = HEIGHT - 200

    def transcribe(self):
        if whisper is None:
            raise RuntimeError("⚠️ Whisper chưa được cài. Chạy: pip install openai-whisper")

        print("→ Nhận dạng lời từ loi.wav bằng Whisper…")
        model = whisper.load_model("small")
        result = model.transcribe(self.loi_wav, language="vi", word_timestamps=True)

        words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append({
                    "word": w["word"].strip(),
                    "start_time": w["start"],
                    "duration": w["end"] - w["start"]
                })
        print(f"✓ Whisper nhận được {len(words)} từ.")
        return words

    def find_first_sing_time(self, words):
        if not words:
            return 0
        return max(0, min(w["start_time"] for w in words if w["word"]))

    def load_lyrics(self):
        with open(self.lyrics_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def build_lines(self, whisper_words, lyrics_data):
        words_iter = iter(whisper_words)
        current_time = 0.0
        lines = []
        
        # Xử lý từng section lyrics
        for section_key in ["lyrics1", "lyrics2"]:
            if section_key in lyrics_data:
                lyrics_lines = lyrics_data[section_key]
                
                for i, text in enumerate(lyrics_lines):
                    toks = text.split()
                    line_words = []
                    for _ in toks:
                        try:
                            line_words.append(next(words_iter))
                        except StopIteration:
                            break
                    
                    if line_words:
                        start = line_words[0]["start_time"]
                        end = line_words[-1]["start_time"] + line_words[-1]["duration"]
                    else:
                        start, end = current_time, current_time + 3
                    
                    lines.append({
                        "text": text, 
                        "start": start, 
                        "end": end,
                        "section": section_key,
                        "is_last_in_section": i == len(lyrics_lines) - 1
                    })
                    current_time = end
                    
                    # Thêm khoảng nghỉ 3 chấm giữa các section
                    if i == len(lyrics_lines) - 1 and section_key == "lyrics1":
                        lines.append({
                            "text": "●  ●  ●",
                            "start": current_time,
                            "end": current_time + 2,
                            "section": "break",
                            "is_break": True
                        })
                        current_time += 2
        
        return lines

    def draw_text_centered(self, draw, text, y, font, fill, alpha=255):
        color = tuple(int(c * alpha / 255) for c in fill)
        w = draw.textlength(text, font=font)
        draw.text(((WIDTH - w) // 2, y), text, font=font, fill=color,
                  stroke_width=self.stroke_width, stroke_fill=self.stroke_color)

    def draw_karaoke_line(self, draw, text, start_time, duration, current_t, y, font, alpha=255):
        """Vẽ một dòng karaoke với hiệu ứng từng từ"""
        elapsed = current_t - start_time
        ratio = np.clip(elapsed / duration, 0, 1)
        n_chars = int(len(text) * ratio)
        
        sung_text = text[:n_chars]
        remaining_text = text[n_chars:]
        
        w_full = draw.textlength(text, font=font)
        x = (WIDTH - w_full) // 2
        
        # Vẽ phần đã hát (màu vàng)
        if sung_text:
            sung_color = tuple(int(c * alpha / 255) for c in self.text_color_sung)
            draw.text((x, y), sung_text, font=font, fill=sung_color,
                      stroke_width=self.stroke_width, stroke_fill=self.stroke_color)
        
        # Vẽ phần chưa hát (màu trắng)
        if remaining_text:
            x_offset = draw.textlength(sung_text, font=font) if sung_text else 0
            remain_color = tuple(int(c * alpha / 255) for c in self.text_color_default)
            draw.text((x + x_offset, y), remaining_text, font=font, fill=remain_color,
                      stroke_width=self.stroke_width, stroke_fill=self.stroke_color)

    def get_animation_alpha(self, progress):
        """Tính toán độ trong suốt cho animation mượt mà"""
        if progress <= 0:
            return 0
        elif progress >= 1:
            return 255
        else:
            # Sử dụng easing function để animation mượt hơn
            smooth_progress = progress * progress * (3 - 2 * progress)  # smoothstep
            return int(255 * smooth_progress)

    def make_frame(self, t, lines, start_sing):
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(DEFAULT_FONT_PATH, FONT_SIZE)
        except:
            font = ImageFont.load_default()

        # Hiệu ứng 3 dấu chấm trước khi bắt đầu hát
        if t < start_sing:
            fade_progress = (PRE_SHOW_TIME - (start_sing - t)) / PRE_SHOW_TIME
            dots_alpha = self.get_animation_alpha(fade_progress)
            
            # Hiệu ứng nhấp nháy của 3 dấu chấm
            dot_phase = (t * 2) % 3
            dots = []
            for i in range(3):
                if int(dot_phase) == i:
                    dots.append("●")
                else:
                    dots.append("○")
            
            dots_text = "  ".join(dots)
            self.draw_text_centered(draw, dots_text, HEIGHT // 2 - 100, font, (255, 255, 255), dots_alpha)
            
            # Hiển thị câu đầu tiên mờ mờ
            if lines and not lines[0].get("is_break"):
                self.draw_text_centered(draw, lines[0]["text"], HEIGHT // 2, font, (180, 180, 180), 180)
            return np.array(img)

        # Tìm dòng đang được hát hiện tại
        current_idx = None
        for i, line in enumerate(lines):
            if line["start"] <= t <= line["end"]:
                current_idx = i
                break

        # Logic karaoke với 2 dòng cố định
        if current_idx is not None:
            current_line = lines[current_idx]
            
            # Kiểm tra nếu là dòng break (3 chấm)
            if current_line.get("is_break"):
                # Hiệu ứng nhấp nháy cho dòng break
                dot_phase = (t * 2) % 3
                dots = []
                for i in range(3):
                    if int(dot_phase) == i:
                        dots.append("●")
                    else:
                        dots.append("○")
                
                dots_text = "  ".join(dots)
                self.draw_text_centered(draw, dots_text, HEIGHT // 2, font, (255, 255, 0), 255)
                return np.array(img)
            
            # *** LOGIC KARAOKE 2 DÒNG CỐ ĐỊNH ***
            
            # Dòng 1: Luôn hiển thị câu trước đó (đã hát xong) nếu có
            if current_idx > 0:
                prev_line = lines[current_idx - 1]
                if not prev_line.get("is_break"):
                    # Hiển thị câu trước đã hát xong (màu mờ hơn)
                    self.draw_text_centered(draw, prev_line["text"], self.line1_y, font, 
                                            (150, 150, 150), 200)
            
            # Dòng 2: Câu đang hát hiện tại với hiệu ứng karaoke
            line_duration = current_line["end"] - current_line["start"]
            self.draw_karaoke_line(draw, current_line["text"], current_line["start"], 
                                   line_duration, t, self.line2_y, font, 255)
            
            # Nếu gần hết câu hiện tại, chuẩn bị hiệu ứng chuyển sang câu tiếp theo
            remain_time = current_line["end"] - t
            if remain_time <= 1.5 and current_idx + 1 < len(lines):  # Khi còn 1.5s
                next_line = lines[current_idx + 1]
                if not next_line.get("is_break"):
                    # Hiển thị preview câu tiếp theo (fade in từ từ)
                    fade_progress = (1.5 - remain_time) / 1.5
                    preview_alpha = int(100 * fade_progress)  # Alpha thấp cho preview
                    
                    # Hiển thị ở vị trí tạm thời (dưới dòng 2)
                    preview_y = self.line2_y + 80
                    self.draw_text_centered(draw, next_line["text"], preview_y, font, 
                                            (200, 200, 200), preview_alpha)
        
        else:
            # Tìm câu sắp được hát (trong vòng 3 giây tới)
            upcoming_idx = None
            for i, line in enumerate(lines):
                if line["start"] > t and line["start"] - t <= 3:
                    upcoming_idx = i
                    break
            
            if upcoming_idx is not None:
                upcoming_line = lines[upcoming_idx]
                if not upcoming_line.get("is_break"):
                    # Hiển thị câu sắp tới với fade in
                    time_until_start = upcoming_line["start"] - t
                    fade_progress = (3 - time_until_start) / 3
                    alpha = int(150 * fade_progress)
                    
                    self.draw_text_centered(draw, upcoming_line["text"], self.line2_y, font, 
                                            self.text_color_default, alpha)
            else:
                # Không có câu nào sắp tới, hiển thị 3 chấm chờ
                dots_text = "●  ●  ●"
                self.draw_text_centered(draw, dots_text, HEIGHT // 2, font, (255, 255, 255), 255)

        return np.array(img)

    def make_video(self, whisper_words, duration):
        lyrics_data = self.load_lyrics()
        lines = self.build_lines(whisper_words, lyrics_data)
        start_sing = self.find_first_sing_time(whisper_words)
        total_dur = duration + PRE_SHOW_TIME + 3

        print(f"🎬 Render video trong {total_dur:.1f}s (bắt đầu hát tại {start_sing:.2f}s)…")
        video = VideoClip(lambda t: self.make_frame(t, lines, start_sing), duration=total_dur)

        # Kiểm tra và gắn file nhạc nền
        if os.path.exists(self.nhac_wav):
            try:
                audio = AudioFileClip(self.nhac_wav)
                video = video.set_audio(audio)
                print(f"✅ Đã gắn nhạc nền: {self.nhac_wav}")
            except Exception as e:
                print(f"⚠️ Lỗi khi gắn nhạc nền: {e}")
        else:
            print(f"⚠️ Không tìm thấy file nhạc: {self.nhac_wav}")

        # Kiểm tra và gắn ảnh nền
        if self.bg_image and os.path.exists(self.bg_image):
            try:
                bg = ImageClip(self.bg_image).set_duration(total_dur).resize((WIDTH, HEIGHT))
                video = CompositeVideoClip([bg, video])
                print(f"✅ Đã gắn ảnh nền: {self.bg_image}")
            except Exception as e:
                print(f"⚠️ Lỗi khi gắn ảnh nền: {e}")
        else:
            print(f"⚠️ Không tìm thấy ảnh nền: {self.bg_image}")

        return video


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    loi = os.path.join(base_dir, "loi_test.wav")
    nhac = os.path.join(base_dir, "nhac_test.wav")
    lyrics = os.path.join(base_dir, "lyrics_test.json")
    bg = os.path.join(base_dir, "anh.jpg")

    # Kiểm tra file đầu vào
    missing_files = []
    if not os.path.exists(loi):
        missing_files.append(loi)
    if not os.path.exists(nhac):
        missing_files.append(nhac)
    if not os.path.exists(lyrics):
        missing_files.append(lyrics)
    
    if missing_files:
        print(f"❌ Thiếu các file sau: {', '.join(missing_files)}")
        return

    try:
        kara = AutoKaraoke(loi, nhac, lyrics, bg)
        words = kara.transcribe()
        
        # Lấy duration từ file nhạc
        audio_clip = AudioFileClip(nhac)
        duration = audio_clip.duration
        audio_clip.close()
        
        video = kara.make_video(words, duration)
        
        output_file = "karaoke_final.mp4"
        print(f"🎬 Đang xuất video: {output_file}")
        video.write_videofile(output_file, fps=FPS, codec="libx264", audio_codec="aac")
        video.close()
        
        print(f"✅ Hoàn thành! Video đã được lưu: {output_file}")
        
    except Exception as e:
        print(f"❌ Lỗi trong quá trình xử lý: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
