#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import numpy as np
from typing import List, Dict, Optional

# Fix encoding for Windows console
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
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
        # Đẩy text xuống đáy màn hình như video karaoke thật
        self.line1_y = HEIGHT - 220  # Dòng trên (câu tiếp theo - chưa hát)
        self.line2_y = HEIGHT - 120  # Dòng dưới (câu đang hát - highlight)

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
        """
        Xây dựng các dòng lyrics với timing từ Whisper.
        Hỗ trợ format mảng 2 cấp: [[lyrics1...], [lyrics2...]]
        Tự động kết thúc câu sau 5s nếu không có từ nào được hát.
        """
        words_iter = iter(whisper_words)
        current_time = 0.0
        lines = []
        MAX_LINE_DURATION = 5.0  # Timeout 5 giây cho mỗi câu
        
        # Xử lý format mới: lyrics_data là mảng của mảng
        # [[section1_lines...], [section2_lines...]]
        if isinstance(lyrics_data, list) and len(lyrics_data) > 0:
            sections = lyrics_data
        else:
            # Fallback cho format cũ {lyrics1: [], lyrics2: []}
            sections = []
            if isinstance(lyrics_data, dict):
                if "lyrics1" in lyrics_data:
                    sections.append(lyrics_data["lyrics1"])
                if "lyrics2" in lyrics_data:
                    sections.append(lyrics_data["lyrics2"])
        
        # Xử lý từng section
        for section_idx, section_lines in enumerate(sections):
            for line_idx, text in enumerate(section_lines):
                text = text.strip()
                if not text:
                    continue
                
                toks = text.split()
                line_words = []
                
                # Lấy timing từ Whisper cho từng từ trong câu
                for _ in toks:
                    try:
                        line_words.append(next(words_iter))
                    except StopIteration:
                        break
                
                # Tính toán thời gian bắt đầu và kết thúc
                if line_words:
                    start = line_words[0]["start_time"]
                    natural_end = line_words[-1]["start_time"] + line_words[-1]["duration"]
                    
                    # Áp dụng timeout 5s: nếu câu dài quá, cắt ngắn lại
                    max_end = start + MAX_LINE_DURATION
                    end = min(natural_end, max_end)
                else:
                    # Không có từ nào từ Whisper - dùng timing ước lượng
                    start = current_time
                    end = current_time + 3
                
                lines.append({
                    "text": text,
                    "words": line_words,
                    "start": start,
                    "end": end,
                    "max_end": end,  # Thời điểm tối đa phải kết thúc
                    "section": f"section_{section_idx}",
                    "is_last_in_section": line_idx == len(section_lines) - 1
                })
                current_time = end
            
            # Thêm khoảng nghỉ 3 chấm giữa các section (trừ section cuối)
            if section_idx < len(sections) - 1:
                lines.append({
                    "text": "●  ●  ●",
                    "words": [],
                    "start": current_time,
                    "end": current_time + 2,
                    "max_end": current_time + 2,
                    "section": "break",
                    "is_break": True
                })
                current_time += 2
        
        return lines

    def draw_text_centered(self, draw, text, y, font, fill, alpha=255):
        # Luôn sử dụng RGB với alpha blending
        color = tuple(int(c * alpha / 255) for c in fill[:3]) if len(fill) >= 3 else (alpha, alpha, alpha)
        stroke_color = self.stroke_color
        
        w = draw.textlength(text, font=font)
        x = (WIDTH - w) // 2
        draw.text((x, y), text, font=font, fill=color,
                  stroke_width=self.stroke_width, stroke_fill=stroke_color)

    def draw_karaoke_line(self, draw, line_data, current_t, y, font, alpha=255):
        """Vẽ một dòng karaoke với hiệu ứng highlight theo TỪNG TỪ (word-level timing)"""
        text = line_data["text"]
        words = line_data.get("words", [])
        
        # Setup màu sắc - luôn dùng RGB
        sung_color = tuple(int(c * alpha / 255) for c in self.text_color_sung)
        remain_color = tuple(int(c * alpha / 255) for c in self.text_color_default)
        stroke_color = self.stroke_color
        
        # Tính toán vị trí x để căn giữa
        w_full = draw.textlength(text, font=font)
        x_start = (WIDTH - w_full) // 2
        
        # Nếu không có words timing, fallback sang highlight theo ký tự
        if not words:
            elapsed = current_t - line_data["start"]
            duration = line_data["end"] - line_data["start"]
            ratio = np.clip(elapsed / duration, 0, 1)
            n_chars = int(len(text) * ratio)
            
            sung_text = text[:n_chars]
            remaining_text = text[n_chars:]
            
            if sung_text:
                draw.text((x_start, y), sung_text, font=font, fill=sung_color,
                          stroke_width=self.stroke_width, stroke_fill=stroke_color)
            if remaining_text:
                x_offset = draw.textlength(sung_text, font=font) if sung_text else 0
                draw.text((x_start + x_offset, y), remaining_text, font=font, fill=remain_color,
                          stroke_width=self.stroke_width, stroke_fill=stroke_color)
            return
        
        # Highlight theo từng từ với timing chính xác từ Whisper
        text_parts = text.split()
        x_current = x_start
        
        for i, word_text in enumerate(text_parts):
            # Lấy timing của từ này
            word_timing = words[i] if i < len(words) else None
            
            if word_timing:
                word_start = word_timing["start_time"]
                word_end = word_start + word_timing["duration"]
                
                # Kiểm tra từ này đã được hát chưa
                if current_t >= word_end:
                    # Đã hát xong từ này - màu vàng
                    color = sung_color
                elif current_t >= word_start:
                    # Đang hát từ này - tạo hiệu ứng smooth character-by-character
                    progress = (current_t - word_start) / word_timing["duration"]
                    # Làm mượt hơn với smoothstep
                    smooth_progress = progress * progress * (3 - 2 * progress)
                    n_chars = int(len(word_text) * smooth_progress)
                    
                    # Vẽ phần đã hát của từ này
                    if n_chars > 0:
                        sung_part = word_text[:n_chars]
                        draw.text((x_current, y), sung_part, font=font, fill=sung_color,
                                  stroke_width=self.stroke_width, stroke_fill=stroke_color)
                        x_offset = draw.textlength(sung_part, font=font)
                    else:
                        x_offset = 0
                    
                    # Vẽ phần chưa hát của từ này
                    remaining_part = word_text[n_chars:]
                    if remaining_part:
                        draw.text((x_current + x_offset, y), remaining_part, font=font, fill=remain_color,
                                  stroke_width=self.stroke_width, stroke_fill=stroke_color)
                    
                    x_current += draw.textlength(word_text, font=font)
                    # Thêm khoảng cách giữa các từ
                    if i < len(text_parts) - 1:
                        x_current += draw.textlength(" ", font=font)
                    continue
                else:
                    # Chưa hát đến từ này - màu trắng
                    color = remain_color
            else:
                # Không có timing - mặc định màu trắng
                color = remain_color
            
            # Vẽ từ này
            draw.text((x_current, y), word_text, font=font, fill=color,
                      stroke_width=self.stroke_width, stroke_fill=stroke_color)
            
            # Di chuyển con trỏ x
            x_current += draw.textlength(word_text, font=font)
            # Thêm khoảng cách giữa các từ
            if i < len(text_parts) - 1:
                x_current += draw.textlength(" ", font=font)

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
    
    def make_mask_frame(self, t, lines, start_sing):
        """Tạo mask frame (grayscale) để xác định vùng trong suốt cho overlay"""
        # Tạo mask: trắng (255) = hiển thị, đen (0) = trong suốt
        mask = Image.new("L", (WIDTH, HEIGHT), 0)  # Bắt đầu với toàn bộ trong suốt
        draw = ImageDraw.Draw(mask)
        
        try:
            font = ImageFont.truetype(DEFAULT_FONT_PATH, FONT_SIZE)
        except:
            font = ImageFont.load_default()
        
        # Vẽ mask cho text - chỉ cần vẽ hình dạng của text
        # Logic tương tự make_frame nhưng chỉ vẽ vùng có text
        
        # Hiệu ứng 3 dấu chấm trước khi bắt đầu hát
        if t < start_sing:
            fade_progress = (PRE_SHOW_TIME - (start_sing - t)) / PRE_SHOW_TIME
            dots_alpha = self.get_animation_alpha(fade_progress)
            
            dot_phase = (t * 2) % 3
            dots = []
            for i in range(3):
                if int(dot_phase) == i:
                    dots.append("●")
                else:
                    dots.append("○")
            
            dots_text = "  ".join(dots)
            w = draw.textlength(dots_text, font=font)
            x = (WIDTH - w) // 2
            draw.text((x, self.line2_y), dots_text, font=font, fill=dots_alpha,
                      stroke_width=self.stroke_width, stroke_fill=dots_alpha)
            
            if lines and not lines[0].get("is_break"):
                w2 = draw.textlength(lines[0]["text"], font=font)
                x2 = (WIDTH - w2) // 2
                draw.text((x2, self.line2_y + 100), lines[0]["text"], font=font, fill=180,
                          stroke_width=self.stroke_width, stroke_fill=180)
            
            return np.array(mask)
        
        # Tìm câu đang hát
        current_idx = None
        for i, line in enumerate(lines):
            if line["start"] <= t <= line["end"]:
                current_idx = i
                break
        
        if current_idx is None:
            for i, line in enumerate(lines):
                if t < line["start"]:
                    current_idx = i
                    break
        
        # Vẽ mask cho các dòng text đang hiển thị
        if current_idx is not None:
            current_line = lines[current_idx]
            
            if current_line.get("is_break"):
                dot_phase = (t * 2) % 3
                dots = []
                for i in range(3):
                    if int(dot_phase) == i:
                        dots.append("●")
                    else:
                        dots.append("○")
                dots_text = "  ".join(dots)
                w = draw.textlength(dots_text, font=font)
                x = (WIDTH - w) // 2
                draw.text((x, HEIGHT // 2), dots_text, font=font, fill=255,
                          stroke_width=self.stroke_width, stroke_fill=255)
                return np.array(mask)
            
            # Vẽ mask cho text chính (bất kể ở dòng nào)
            non_break_lines = [l for l in lines if not l.get("is_break")]
            try:
                current_actual_idx = non_break_lines.index(current_line)
            except ValueError:
                current_actual_idx = current_idx
            
            is_odd = (current_actual_idx % 2 == 0)
            current_y = self.line1_y if is_odd else self.line2_y
            
            # Vẽ mask cho câu hiện tại
            w = draw.textlength(current_line["text"], font=font)
            x = (WIDTH - w) // 2
            draw.text((x, current_y), current_line["text"], font=font, fill=255,
                      stroke_width=self.stroke_width, stroke_fill=255)
            
            # Vẽ mask cho câu tiếp theo nếu có
            if current_idx + 1 < len(lines):
                next_line = lines[current_idx + 1]
                if not next_line.get("is_break"):
                    is_singing = (current_line["start"] <= t <= current_line["end"])
                    if is_singing:
                        elapsed_in_current = t - current_line["start"]
                        duration_current = current_line["end"] - current_line["start"]
                        progress = elapsed_in_current / duration_current
                        if progress >= 0.4:
                            alpha = int(200 * ((progress - 0.4) / 0.6))
                            if alpha > 0:
                                try:
                                    next_actual_idx = non_break_lines.index(next_line)
                                except ValueError:
                                    next_actual_idx = current_idx + 1
                                is_next_odd = (next_actual_idx % 2 == 0)
                                next_y = self.line1_y if is_next_odd else self.line2_y
                                w2 = draw.textlength(next_line["text"], font=font)
                                x2 = (WIDTH - w2) // 2
                                draw.text((x2, next_y), next_line["text"], font=font, fill=alpha,
                                          stroke_width=self.stroke_width, stroke_fill=alpha)
        
        return np.array(mask)

    def make_frame(self, t, lines, start_sing, has_background=False):
        if has_background:
            # Nếu có ảnh nền, tạo frame RGB với nền ĐEN để làm overlay
            # Text sẽ hiển thị, phần đen sẽ trong suốt nhờ set_mask
            img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        else:
            # Nếu không có ảnh nền, tạo frame với gradient background
            img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
            # Vẽ nền gradient đẹp
            pixels = img.load()
            for y in range(HEIGHT):
                r = int(10 + 30 * (y / HEIGHT))
                g = int(10 + 30 * (y / HEIGHT)) 
                b = int(20 + 60 * (y / HEIGHT))
                for x in range(WIDTH):
                    pixels[x, y] = (r, g, b)
        
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(DEFAULT_FONT_PATH, FONT_SIZE)
        except:
            font = ImageFont.load_default()

        # Hiệu ứng 3 dấu chấm trước khi bắt đầu hát
        if t < start_sing:
            fade_progress = (PRE_SHOW_TIME - (start_sing - t)) / PRE_SHOW_TIME
            dots_alpha = self.get_animation_alpha(fade_progress)
            
            # Hiệu ứng nhấp nháy của 3 dấu chấm - ĐẨY XUỐNG DƯỚI CÙNG
            dot_phase = (t * 2) % 3
            dots = []
            for i in range(3):
                if int(dot_phase) == i:
                    dots.append("●")
                else:
                    dots.append("○")
            
            dots_text = "  ".join(dots)
            # Đẩy dots xuống vị trí giữa 2 dòng karaoke
            self.draw_text_centered(draw, dots_text, self.line1_y + 50, font, (255, 255, 255), dots_alpha)
            
            # Hiển thị câu đầu tiên preview ở vị trí dòng 2
            if lines and not lines[0].get("is_break"):
                self.draw_text_centered(draw, lines[0]["text"], self.line2_y, font, (255, 255, 255), 150)
            
            return np.array(img)

        # *** LOGIC KARAOKE 2 DÒNG LUÂN PHIÊN - KHÔNG BAO GIỜ NHẢY VỊ TRÍ ***
        # Quy tắc: Câu lẻ (index 0,2,4...) hát ở DÒNG 1
        #          Câu chẵn (index 1,3,5...) hát ở DÒNG 2
        # Khi hết câu, text mới xuất hiện ở dòng còn lại
        
        # Tìm câu đang hát hoặc sắp hát
        current_idx = None
        for i, line in enumerate(lines):
            if line["start"] <= t <= line["end"]:
                current_idx = i
                break
        
        if current_idx is None:
            for i, line in enumerate(lines):
                if t < line["start"]:
                    current_idx = i
                    break
        
        if current_idx is not None:
            current_line = lines[current_idx]
            
            # Xử lý dòng break (3 chấm)
            if current_line.get("is_break"):
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
            
            # Xác định dòng nào sẽ hiển thị câu này (dựa vào index)
            # Lọc bỏ các dòng break để đếm chính xác
            non_break_lines = [l for l in lines if not l.get("is_break")]
            try:
                actual_idx = non_break_lines.index(current_line)
            except ValueError:
                actual_idx = current_idx
            
            is_odd_line = (actual_idx % 2 == 0)  # Index 0,2,4... là câu lẻ
            current_y = self.line1_y if is_odd_line else self.line2_y
            
            is_singing = (current_line["start"] <= t <= current_line["end"])
            
            # ========== VẼ CÂU HIỆN TẠI ==========
            if is_singing:
                # Đang hát - highlight với timing chính xác
                self.draw_karaoke_line(draw, current_line, t, current_y, font, 255)
            else:
                # Chưa hát - fade in
                time_until_start = current_line["start"] - t
                if time_until_start <= 2:
                    fade_progress = (2 - time_until_start) / 2
                    alpha = int(255 * fade_progress)
                    self.draw_text_centered(draw, current_line["text"], current_y, font, 
                                            (255, 255, 255), alpha)
            
            # ========== VẼ CÂU TIẾP THEO (ở dòng còn lại) ==========
            if current_idx + 1 < len(lines):
                next_line = lines[current_idx + 1]
                if not next_line.get("is_break"):
                    # Xác định dòng của câu tiếp theo
                    try:
                        next_actual_idx = non_break_lines.index(next_line)
                    except ValueError:
                        next_actual_idx = current_idx + 1
                    
                    is_next_odd = (next_actual_idx % 2 == 0)
                    next_y = self.line1_y if is_next_odd else self.line2_y
                    
                    if is_singing:
                        # Khi đang hát, bắt đầu fade in câu tiếp theo
                        elapsed = t - current_line["start"]
                        duration = current_line["end"] - current_line["start"]
                        progress = elapsed / duration
                        
                        # Bắt đầu fade in từ 50% của câu hiện tại
                        if progress >= 0.5:
                            alpha = int(200 * ((progress - 0.5) / 0.5))
                            self.draw_text_centered(draw, next_line["text"], next_y, font, 
                                                    (200, 200, 200), alpha)
                    else:
                        # Chưa hát câu hiện tại, preview câu tiếp theo nhẹ nhàng
                        time_until_current = current_line["start"] - t
                        if time_until_current <= 1:
                            alpha = int(120 * (1 - time_until_current))
                            if alpha > 0:
                                self.draw_text_centered(draw, next_line["text"], next_y, font, 
                                                        (180, 180, 180), alpha)
            
            # ========== VẼ CÂU ĐÃ HÁT (ở dòng kia nếu có) ==========
            # Hiển thị câu vừa hát xong trong 1-2 giây
            if current_idx > 0 and is_singing:
                prev_line = lines[current_idx - 1]
                if not prev_line.get("is_break"):
                    # Tính thời gian đã trôi qua kể từ khi hết câu trước
                    time_since_prev = t - prev_line["end"]
                    
                    # Hiển thị trong 1.5 giây sau khi hết câu, rồi fade out
                    if time_since_prev <= 1.5:
                        try:
                            prev_actual_idx = non_break_lines.index(prev_line)
                        except ValueError:
                            prev_actual_idx = current_idx - 1
                        
                        is_prev_odd = (prev_actual_idx % 2 == 0)
                        prev_y = self.line1_y if is_prev_odd else self.line2_y
                        
                        # Fade out từ từ
                        fade_out_progress = time_since_prev / 1.5
                        alpha = int(150 * (1 - fade_out_progress))
                        
                        if alpha > 0:
                            self.draw_text_centered(draw, prev_line["text"], prev_y, font, 
                                                    (180, 180, 180), alpha)
        else:
            # Không có câu nào
            pass
        
        # Luôn return RGB array cho MoviePy
        return np.array(img)

    def make_video(self, whisper_words, duration):
        lyrics_data = self.load_lyrics()
        lines = self.build_lines(whisper_words, lyrics_data)
        start_sing = self.find_first_sing_time(whisper_words)
        
        # Sử dụng duration của file nhạc làm chuẩn
        total_dur = duration
        
        print(f"🎬 Render video trong {total_dur:.1f}s (bắt đầu hát tại {start_sing:.2f}s)…")
        
        # Kiểm tra ảnh nền trước
        has_background = self.bg_image and os.path.exists(self.bg_image)
        
        # Tạo video karaoke
        if has_background:
            # Khi có ảnh nền, tạo video với mask để làm transparent overlay
            print(f"🖼️ Đang xử lý ảnh nền: {self.bg_image}")
            
            # Tạo background clip
            bg_clip = ImageClip(self.bg_image, duration=total_dur).resize((WIDTH, HEIGHT))
            
            # Tạo text overlay clip với mask
            text_clip = VideoClip(lambda t: self.make_frame(t, lines, start_sing, True), duration=total_dur)
            mask_clip = VideoClip(lambda t: self.make_mask_frame(t, lines, start_sing), duration=total_dur, ismask=True)
            text_clip = text_clip.set_mask(mask_clip)
            
            # Composite
            final_video = CompositeVideoClip([bg_clip, text_clip])
            print(f"✅ Đã gắn ảnh nền thành công")
        else:
            # Không có ảnh nền - dùng gradient background
            print(f"⚠️ Không tìm thấy ảnh nền: {self.bg_image}")
            final_video = VideoClip(lambda t: self.make_frame(t, lines, start_sing, False), duration=total_dur)
        
        # Xử lý âm thanh
        if os.path.exists(self.nhac_wav):
            try:
                print(f"🎵 Đang xử lý âm thanh: {self.nhac_wav}")
                audio = AudioFileClip(self.nhac_wav)
                
                # Cắt audio nếu dài hơn video
                if audio.duration > total_dur:
                    audio = audio.subclip(0, total_dur)
                
                final_video = final_video.set_audio(audio)
                print(f"✅ Đã gắn âm thanh thành công (duration: {audio.duration:.1f}s)")
            except Exception as e:
                print(f"⚠️ Lỗi khi gắn âm thanh: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ Không tìm thấy file âm thanh: {self.nhac_wav}")

        return final_video



def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Sử dụng file test để debug nhanh
    loi = os.path.join(base_dir, "loi.wav")
    nhac = os.path.join(base_dir, "nhac.wav")
    lyrics = os.path.join(base_dir, "lyrics.json")
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
        
        # Lấy duration từ file nhạc và đảm bảo chính xác
        audio_clip = AudioFileClip(nhac)
        duration = audio_clip.duration
        print(f"📊 File nhạc duration: {duration:.2f}s")
        audio_clip.close()
        
        video = kara.make_video(words, duration)
        
        output_file = "karaoke_final.mp4"
        print(f"🎬 Đang xuất video: {output_file}")
        
        # Xuất video với thông số tối ưu
        video.write_videofile(
            output_file, 
            fps=FPS, 
            codec="libx264", 
            audio_codec="aac",
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,  # Giảm log để dễ debug
            logger=None
        )
        
        # Đóng video để giải phóng memory
        video.close()
        
        print(f"✅ Hoàn thành! Video đã được lưu: {output_file}")
        
    except Exception as e:
        print(f"❌ Lỗi trong quá trình xử lý: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
