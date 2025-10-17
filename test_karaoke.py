#!/usr/bin/env python3
"""
File test để kiểm tra logic karaoke mới
"""
import json

def test_lyrics_structure():
    with open('lyrics_array.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=== Cấu trúc Lyrics ===")
    for section_key in ["lyrics1", "lyrics2"]:
        if section_key in data:
            print(f"\n{section_key}:")
            for i, line in enumerate(data[section_key]):
                print(f"  {i+1:2d}. {line}")
                if i == len(data[section_key]) - 1:
                    print(f"      -> Cuối {section_key}, sẽ thêm 3 chấm chờ")

def simulate_build_lines():
    """Mô phỏng logic build_lines mới"""
    with open('lyrics_array.json', 'r', encoding='utf-8') as f:
        lyrics_data = json.load(f)
    
    # Mock whisper words - giả lập 100 từ
    mock_words = []
    for i in range(100):
        mock_words.append({
            "word": f"từ{i}",
            "start_time": i * 0.5,  # mỗi từ cách nhau 0.5s
            "duration": 0.4
        })
    
    words_iter = iter(mock_words)
    current_time = 0.0
    lines = []
    
    print("\n=== Mô phỏng Build Lines ===")
    
    # Xử lý từng section lyrics
    for section_key in ["lyrics1", "lyrics2"]:
        if section_key in lyrics_data:
            lyrics_lines = lyrics_data[section_key]
            print(f"\n--- Xử lý {section_key} ---")
            
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
                
                line_info = {
                    "text": text, 
                    "start": start, 
                    "end": end,
                    "section": section_key,
                    "is_last_in_section": i == len(lyrics_lines) - 1
                }
                lines.append(line_info)
                current_time = end
                
                print(f"  Line {len(lines):2d}: {start:5.1f}s - {end:5.1f}s | {text[:50]}...")
                
                # Thêm khoảng nghỉ 3 chấm giữa các section
                if i == len(lyrics_lines) - 1 and section_key == "lyrics1":
                    break_info = {
                        "text": "●  ●  ●",
                        "start": current_time,
                        "end": current_time + 2,
                        "section": "break",
                        "is_break": True
                    }
                    lines.append(break_info)
                    current_time += 2
                    print(f"  BREAK  : {break_info['start']:5.1f}s - {break_info['end']:5.1f}s | ●  ●  ●")
    
    print(f"\nTổng cộng: {len(lines)} lines (bao gồm break)")
    return lines

if __name__ == "__main__":
    test_lyrics_structure()
    simulate_build_lines()