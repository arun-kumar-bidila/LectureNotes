import cv2
import os
import pytesseract
from Levenshtein import ratio as levenshtein_ratio
import re

# Set path to Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

def is_blurry(image, threshold=100):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < threshold

def extract_text(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(gray).strip()

def clean_text(text):
    return re.sub(r'\W+', ' ', text).lower().strip()

def is_duplicate(prev_text, curr_text, ratio_threshold=0.85):
    prev_clean = clean_text(prev_text)
    curr_clean = clean_text(curr_text)
    similarity = levenshtein_ratio(prev_clean, curr_clean)
    return similarity > ratio_threshold

def significant_change(prev_text, curr_text, line_change_ratio=0.5):
    prev_lines = [line.strip() for line in prev_text.splitlines() if line.strip()]
    curr_lines = [line.strip() for line in curr_text.splitlines() if line.strip()]
    
    if not prev_lines:
        return True  # Always save first non-empty

    new_lines = [line for line in curr_lines if line not in prev_lines]
    added_ratio = len(new_lines) / max(len(prev_lines), 1)
    
    return added_ratio > line_change_ratio

def extract_screenshots(video_path, output_dir='screenshots', interval=2):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("❌ Failed to open video.")
        return

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_interval = interval * fps
    count, saved = 0, 0
    prev_text = ""
    saved_texts = []  # Store cleaned texts of all saved screenshots

    screenshot_data = []

    print(f"🎞 Processing at {fps} FPS, every {interval}s (interval = {frame_interval} frames)")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if count % frame_interval == 0:
            timestamp_sec = count / fps
            print(f"\n🔍 Frame {count} (Time: {timestamp_sec:.2f}s)")

            if is_blurry(frame):
                print("📷 Skipped: Blurry frame")
                count += 1
                continue

            curr_text = extract_text(frame)
            if not curr_text:
                print("📄 Skipped: No text found")
                count += 1
                continue

            cleaned_curr = clean_text(curr_text)

            # Compare with all previously saved texts
            is_repeat = False
            for saved_clean in saved_texts:
                similarity = levenshtein_ratio(saved_clean, cleaned_curr)
                if similarity > 0.85:
                    is_repeat = True
                    break

            if is_repeat:
                print("🔁 Skipped: Repeated content (high similarity with earlier save)")
                count += 1
                continue

            if significant_change(prev_text, curr_text):
                filename = os.path.join(output_dir, f'screenshot_{timestamp_sec:.2f}s.jpg')
                cv2.imwrite(filename, frame)
                screenshot_data.append({
                    "time": timestamp_sec,
                    "image": filename,
                    "text": curr_text
                })
                prev_text = curr_text
                saved_texts.append(cleaned_curr)
                saved += 1
                print(f"✅ Saved: {filename}")
            else:
                print("⚠️ Skipped: Only slight change, not saving")

        count += 1

    cap.release()
    print(f"\n🎉 Done. Total screenshots saved: {saved}")
    return screenshot_data


# 👉 Run the function
screenshot_data = extract_screenshots("test_video.mp4")
