import subprocess
import whisper
import cv2
import os
import pytesseract
import re
from Levenshtein import ratio as levenshtein_ratio
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# --------------------------
# Configuration
# --------------------------

# Paths (adjust if necessary)
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
VIDEO_PATH = "test_video2.mp4"
AUDIO_PATH = "extracted_audio.wav"
TRANSCRIPT_FILE = "transcription.txt"
SUMMARY_PDF = "video_summary.pdf"

# Tesseract configuration
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --------------------------
# Audio & Transcript
# --------------------------

def extract_audio_from_video(video_path, audio_path):
    command = [
        FFMPEG_PATH,
        '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '44100',
        '-ac', '2',
        audio_path
    ]
    subprocess.run(command, check=True)
    print(f"Audio extracted and saved to {audio_path}")

def transcribe_audio_to_segments(audio_path):
    print("[INFO] Loading Whisper model...")
    model = whisper.load_model("base")

    print("[INFO] Transcribing audio...")
    result = model.transcribe(audio_path)
    
    full_text = result["text"]
    with open(TRANSCRIPT_FILE, 'w', encoding="utf-8") as file:
        file.write(full_text)
    print(f"[INFO] Full transcript saved to {TRANSCRIPT_FILE}")
    
    segments = result.get("segments", [])
    print(f"[INFO] Retrieved {len(segments)} transcript segments")
    return segments

# --------------------------
# Screenshot Extraction & OCR
# --------------------------

def is_blurry(image, threshold=100):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < threshold

def extract_text_from_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(gray).strip()

def clean_text(text):
    return re.sub(r'\W+', ' ', text).lower().strip()

def significant_change(prev_text, curr_text, line_change_ratio=0.5):
    prev_lines = [line.strip() for line in prev_text.splitlines() if line.strip()]
    curr_lines = [line.strip() for line in curr_text.splitlines() if line.strip()]
    
    if not prev_lines:
        return True

    new_lines = [line for line in curr_lines if line not in prev_lines]
    added_ratio = len(new_lines) / max(len(prev_lines), 1)
    
    return added_ratio > line_change_ratio

def extract_screenshots(video_path, output_dir='screenshots', interval=2):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("❌ Failed to open video.")
        return []

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_interval = interval * fps
    count, saved = 0, 0
    prev_text = ""
    saved_texts = []

    screenshot_data = []

    print(f"🎞 Processing video at {fps} FPS, extracting every {interval} sec (every {frame_interval} frames).")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if count % frame_interval == 0:
            timestamp_sec = count / fps
            print(f"\n🔍 Frame {count} at {timestamp_sec:.2f}s")

            if is_blurry(frame):
                print("📷 Skipped: Blurry frame")
                count += 1
                continue

            curr_text = extract_text_from_image(frame)
            if not curr_text:
                print("📄 Skipped: No text found")
                count += 1
                continue

            cleaned_curr = clean_text(curr_text)
            is_repeat = any(levenshtein_ratio(saved, cleaned_curr) > 0.85 for saved in saved_texts)
            if is_repeat:
                print("🔁 Skipped: Repeated content")
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
                print(f"✅ Saved screenshot: {filename}")
            else:
                print("⚠️ Skipped: Only slight change")
        count += 1

    cap.release()
    print(f"\n🎉 Done. Total screenshots saved: {saved}")
    return screenshot_data

# --------------------------
# Merge and PDF Generation
# --------------------------

def merge_timeline(transcript_segments, screenshot_data):
    timeline = []
    for seg in transcript_segments:
        timeline.append({
            "type": "transcript",
            "time": seg["start"],
            "content": seg["text"]
        })
    for shot in screenshot_data:
        timeline.append({
            "type": "screenshot",
            "time": shot["time"],
            "content": shot["image"],
            "text": shot["text"]
        })
    timeline.sort(key=lambda x: x["time"])
    return timeline

def generate_pdf_summary(timeline, output_file):
    c = canvas.Canvas(output_file, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - margin
    text_font_size = 11
    image_max_width = width - 2 * margin
    image_max_height = height / 3

    c.setFont("Helvetica", text_font_size)
    c.drawString(margin, y, "Video Summary")
    y -= 20

    for entry in timeline:
        if y < 100:
            c.showPage()
            c.setFont("Helvetica", text_font_size)
            y = height - margin

        if entry["type"] == "transcript":
            wrapped_text = re.findall('.{1,100}(?:\s+|$)', entry["content"])
            line = ''
            for word in wrapped_text:
                if c.stringWidth(line + word.strip(), "Helvetica", text_font_size) < (width - 2 * margin):
                    line += word.strip() + ' '
                else:
                    c.drawString(margin, y, line.strip())
                    y -= 14
                    line = word.strip() + ' '
                    if y < 100:
                        c.showPage()
                        c.setFont("Helvetica", text_font_size)
                        y = height - margin
            if line:
                c.drawString(margin, y, line.strip())
                y -= 14

        elif entry["type"] == "screenshot":
            try:
                img = ImageReader(entry["content"])
                iw, ih = img.getSize()
                scale = min(image_max_width / iw, image_max_height / ih)
                img_width = iw * scale
                img_height = ih * scale

                if y - img_height < 50:
                    c.showPage()
                    c.setFont("Helvetica", text_font_size)
                    y = height - margin

                c.drawImage(img, margin, y - img_height, width=img_width, height=img_height)
                y -= img_height + 20
            except Exception as e:
                c.drawString(margin, y, f"[Error loading image: {entry['content']}]")
                y -= 20

    c.save()
    print(f"[INFO] PDF summary generated: {output_file}")

# --------------------------
# Main Workflow
# --------------------------

if __name__ == "__main__":
    extract_audio_from_video(VIDEO_PATH, AUDIO_PATH)
    transcript_segments = transcribe_audio_to_segments(AUDIO_PATH)
    screenshot_data = extract_screenshots(VIDEO_PATH, output_dir="screenshots", interval=2)
    timeline = merge_timeline(transcript_segments, screenshot_data)
    generate_pdf_summary(timeline, SUMMARY_PDF)
