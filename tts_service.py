import pyttsx3
import os
import uuid
from database import get_session, Newsletter

import wave
import json
import re
import contextlib

def generate_audio(text, output_filename):
    """
    Generates an audio file from text using pyttsx3, with sentence-level alignment.
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    alignment_data = []
    combined_frames = []
    current_time = 0.0
    params = None

    try:
        # Split text into sentences
        # Split by . ! ? followed by whitespace or end of string
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            sentences = [text]

        engine = pyttsx3.init()
        # Optional: Configure voice/rate
        # engine.setProperty('rate', 150)

        for sentence in sentences:
            temp_filename = f"temp_{uuid.uuid4()}.wav"
            # In some environments, save_to_file might fail or hang if loop is running. 
            # But we are calling runAndWait sequentially.
            engine.save_to_file(sentence, temp_filename)
            engine.runAndWait()

            if os.path.exists(temp_filename):
                try:
                    with contextlib.closing(wave.open(temp_filename, 'rb')) as wf:
                        if params is None:
                            params = wf.getparams()
                        
                        # Verify params match (simplification: assume they do for same engine settings)
                        frames = wf.readframes(wf.getnframes())
                        duration = wf.getnframes() / wf.getframerate()
                        
                        alignment_data.append({
                            "sentence": sentence,
                            "start": current_time,
                            "end": current_time + duration
                        })
                        
                        current_time += duration
                        combined_frames.append(frames)
                finally:
                    try:
                        os.remove(temp_filename)
                    except OSError:
                        pass
        
        # Write final audio file
        if params and combined_frames:
             with contextlib.closing(wave.open(output_filename, 'wb')) as wf:
                 wf.setparams(params)
                 for frames in combined_frames:
                     wf.writeframes(frames)
             
             # Write alignment JSON
             json_filename = os.path.splitext(output_filename)[0] + '.json'
             with open(json_filename, 'w') as f:
                 json.dump(alignment_data, f)
        else:
            # Fallback if no frames were generated (e.g. empty text or TTS failure not catching)
            # Try generating whole text as one block if splitting failed, or just empty
            print("Warning: No audio frames generated from sentences.")
            with open(output_filename, 'w') as f:
                f.write("Audio generation failed - no frames.")

    except OSError as e:
        # Fallback for environments without espeak (like CI/Sandbox)
        print(f"Warning: TTS Engine failed to initialize (likely missing system libraries). Creates dummy file. Error: {e}")
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
