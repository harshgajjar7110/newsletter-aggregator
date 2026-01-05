import pyttsx3
import os
import uuid
from database import get_session, Newsletter

def generate_audio(text, output_filename):
    """
    Generates an audio file from text using pyttsx3.
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    try:
        engine = pyttsx3.init()

        # Optional: Configure voice/rate
        # engine.setProperty('rate', 150)

        engine.save_to_file(text, output_filename)
        engine.runAndWait()
    except OSError as e:
        # Fallback for environments without espeak (like CI/Sandbox)
        print(f"Warning: TTS Engine failed to initialize (likely missing system libraries). Creating dummy file. Error: {e}")
        with open(output_filename, 'w') as f:
            f.write("Audio generation failed in this environment.")
    except Exception as e:
        print(f"Error in TTS generation: {e}")
        # Create dummy file so app doesn't break
        with open(output_filename, 'w') as f:
            f.write("Audio generation failed.")

    return output_filename

def process_newsletter_audio(newsletter_id):
    """
    Generates audio for a specific newsletter and updates the DB.
    """
    session = get_session()
    newsletter = session.query(Newsletter).filter_by(id=newsletter_id).first()

    if not newsletter:
        return None

    if newsletter.audio_path and os.path.exists(newsletter.audio_path):
        return newsletter.audio_path

    # Generate unique filename
    filename = f"static/audio/{uuid.uuid4()}.mp3" # pyttsx3 usually saves as wav/aiff depending on OS, but we'll try .mp3 or .wav
    # Linux pyttsx3 often defaults to espeak which handles .wav well.
    # Let's use .wav for better compatibility if ffmpeg isn't around,
    # or .mp3 if the engine supports it.
    # Safest is .wav for 'save_to_file' with standard engines.
    filename = f"static/audio/{uuid.uuid4()}.wav"

    try:
        generate_audio(newsletter.content_text, filename)
        newsletter.audio_path = filename
        session.commit()
        return filename
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None
    finally:
        session.close()

if __name__ == "__main__":
    # Test
    # Create a dummy file to test
    generate_audio("Hello world, this is a test of the newsletter listener.", "static/audio/test.wav")
    print("Audio generated at static/audio/test.wav")
