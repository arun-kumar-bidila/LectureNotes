import subprocess
import whisper
import cv2
import os
import pytesseract
import re
import sys
import cloudinary
import cloudinary.uploader

from Levenshtein import ratio as levenshtein_ratio
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# --------------------------
# Configuration
# --------------------------

FFMPEG_PATH = r"C:\ffmpeg-2025-02-13-git-19a2d26177-full_build\ffmpeg-2025-02-13-git-19a2d26177-full_build\bin\ffmpeg.exe"
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

cloudinary.config(
    cloud_name="duoenlwuj",
    api_key="536698638836779",
    api_secret="_ZfLsWPirfhd08G2JKkgZrG_zTs"
)

# --------------------------
# Audio & Transcript
# --------------------------

def extract_audio_from_video(video_path, audio_path):
    command = [
        FFMPEG_PATH, '-i', video_path, '-vn',
        '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', audio_path
    ]
    subprocess.run(command, check=True)
    print(f"[AUDIO] Extracted to {audio_path}", file=sys.stderr)

def transcribe_audio_to_segments(audio_path, transcript_txt):
    print("[TRANSCRIBE] Loading Whisper model...", file=sys.stderr)
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)

    with open(transcript_txt, 'w', encoding="utf-8") as file:
        file.write(result["text"])

    print(f"[TRANSCRIBE] Saved full transcript to {transcript_txt}", file=sys.stderr)
    return result.get("segments", [])

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
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Cannot open video.", file=sys.stderr)
        return []

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_interval = interval * fps
    count, saved = 0, 0
    prev_text = ""
    saved_texts = []
    data = []

    print(f"[SCREENSHOT] FPS: {fps}, Interval: {interval}s", file=sys.stderr)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if count % frame_interval == 0:
            timestamp_sec = count / fps
            print(f"\n[FRAME] {count} ({timestamp_sec:.2f}s)", file=sys.stderr)

            if is_blurry(frame):
                print(" Blurry, skipping", file=sys.stderr)
                count += 1
                continue

            curr_text = extract_text_from_image(frame)
            if not curr_text:
                print(" No text, skipping", file=sys.stderr)
                count += 1
                continue

            cleaned = clean_text(curr_text)
            if any(levenshtein_ratio(saved, cleaned) > 0.85 for saved in saved_texts):
                print(" Repeated, skipping", file=sys.stderr)
                count += 1
                continue

            if significant_change(prev_text, curr_text):
                filename = os.path.join(output_dir, f'screenshot_{timestamp_sec:.2f}s.jpg')
                cv2.imwrite(filename, frame)
                data.append({
                    "time": timestamp_sec,
                    "image": filename,
                    "text": curr_text
                })
                prev_text = curr_text
                saved_texts.append(cleaned)
                print(f" Saved: {filename}", file=sys.stderr)
            else:
                print(" Slight change, skipping", file=sys.stderr)

        count += 1

    cap.release()
    print(f"\n[SCREENSHOT] Saved {len(data)} screenshots", file=sys.stderr)
    return data

# --------------------------
# Merge Timeline & Generate PDF
# --------------------------

def merge_timeline(transcript_segments, screenshots):
    timeline = []
    for seg in transcript_segments:
        timeline.append({
            "type": "transcript",
            "time": seg["start"],
            "content": seg["text"]
        })
    for shot in screenshots:
        timeline.append({
            "type": "screenshot",
            "time": shot["time"],
            "content": shot["image"],
            "text": shot["text"]
        })
    return sorted(timeline, key=lambda x: x["time"])

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
            wrapped = re.findall(r'.{1,100}(?:\s+|$)', entry["content"])
            line = ''
            for word in wrapped:
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
            except Exception:
                c.drawString(margin, y, f"[Error loading image: {entry['content']}]", file=sys.stderr)
                y -= 20

    c.save()
    print(f"[PDF] Generated: {output_file}", file=sys.stderr)

# --------------------------
# Pipeline Entry Point
# --------------------------

def run_pipeline(video_path, pdf_name):
    audio_path = "temp_audio.wav"
    transcript_txt = "transcript.txt"

    extract_audio_from_video(video_path, audio_path)
    segments = transcribe_audio_to_segments(audio_path, transcript_txt)
    screenshots = extract_screenshots(video_path, output_dir="screenshots", interval=2)
    timeline = merge_timeline(segments, screenshots)
    generate_pdf_summary(timeline, pdf_name)

    # Upload to Cloudinary
    result = cloudinary.uploader.upload(pdf_name, resource_type="raw")
    return result["secure_url"]

# --------------------------
# Main
# --------------------------

if __name__ == "__main__":
    import json

    if len(sys.argv) != 3:
        print(json.dumps({
            "success": False,
            "error": "Invalid arguments. Usage: python server.py <video_path> <pdf_output_path>"
        }))
        sys.exit(1)

    video_path = sys.argv[1]
    pdf_name = sys.argv[2]

    try:
        url = run_pipeline(video_path, pdf_name)

        # ✅ Only this output goes to stdout for Node.js
        print(json.dumps({
            "success": True,
            "url": url
        }))

    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": "Video summarization failed.",
            "details": str(e)
        }))
        sys.exit(1)
