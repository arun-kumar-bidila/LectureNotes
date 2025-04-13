import subprocess
import whisper

def extract_audio_from_video(video_path, audio_path):
    """
    Extracts audio from a video file using ffmpeg.
    Args:
        video_path (str): Path to the input video file.
        audio_path (str): Path to save the extracted audio file.
    """
    ffmpeg_path = r"C:\ffmpeg\bin\ffmpeg.exe"
    
    command = [
        ffmpeg_path, 
        '-i', video_path,       # Input video file
        '-vn',                  # Disable video recording
        '-acodec', 'pcm_s16le', # Audio codec (WAV format)
        '-ar', '44100',         # Audio sample rate
        '-ac', '2',             # Number of audio channels
        audio_path             # Output audio file
    ]
    subprocess.run(command, check=True)
    print(f"Audio extracted and saved to {audio_path}")

def transcribe_audio_to_text(audio_path):
    """
    Transcribes audio to text using Whisper.
    Args:
        audio_path (str): Path to the audio file to transcribe.
    Returns:
        str: Transcribed text.
    """
    print("[INFO] Loading Whisper model...")
    model = whisper.load_model("base")  # You can change this to "small", "medium", or "large"

    print("[INFO] Transcribing audio...")
    result = model.transcribe(audio_path)
    
    text = result["text"]
    print("[INFO] Transcription successful!")
    return text

def save_transcription_to_file(text, file_path):
    """
    Saves transcribed text to a file.
    Args:
        text (str): Text to save.
        file_path (str): Path to the output text file.
    """
    if text:
        with open(file_path, 'w', encoding="utf-8") as file:
            file.write(text)
        print(f"Transcription saved to {file_path}")
    else:
        print("No text to save")

# Example usage
if __name__ == "__main__":
    video_path = 'test_video.mp4'       # Replace with your video file path
    audio_path = 'extracted_audio.wav'  # Desired path for the extracted audio
    text_file_path = 'transcription.txt' # Desired path for the transcription text file

    extract_audio_from_video(video_path, audio_path)
    transcription = transcribe_audio_to_text(audio_path)
    save_transcription_to_file(transcription, text_file_path)
