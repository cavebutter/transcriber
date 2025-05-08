import os
import subprocess as sp
import whisper
import torch
from numpy.f2py.crackfortran import verbose
from pyannote.audio.pipelines import SpeakerDiarization
from transformers import pipeline
from tqdm import tqdm
import argparse

HF_TOKEN = os.getenv('HF_TOKEN')

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Process audio file with transcription and diarization")
    parser.add_argument("audio_file", type=str, help="Path to the audio file to process")
    parser.add_argument("--output_dir", type=str, default="output", help="Directory to save output files")
    parser.add_argument("--whisper_model", type=str, default="large",
                        choices=["tiny", "base", "small", "medium", "large", "large-v2"],
                        help="Whisper model size")
    parser.add_argument("--language", type=str, default="en", help="Language code for transcription")
    # parser.add_argument("--summary_length", type=int, default=250, help="Maximum length of summary in tokens")
    return parser.parse_args()


def convert_to_wav(audio_file: str, output_file: str):
    """
    Convert audio file to wav format using ffmpeg with progress bar.
    """
    # First get the duration of the audio file
    duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', audio_file]
    duration = float(sp.check_output(duration_cmd, text=True).strip())

    # Set up the conversion command with progress information
    command = [
        'ffmpeg', '-i', audio_file, '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        '-progress', 'pipe:1', '-nostats', output_file
    ]

    # Create a progress bar
    pbar = tqdm(total=100, desc="Converting audio", unit="%")

    # Run the command and update the progress bar
    process = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)

    last_progress = 0
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break

        # Parse progress information
        if line.startswith("out_time_ms="):
            try:
                time_ms = int(line.split("=")[1])
                progress = min(100, int(time_ms / 1000 / duration * 100))
                # Update progress bar only on change to avoid excessive updates
                if progress > last_progress:
                    pbar.update(progress - last_progress)
                    last_progress = progress
            except (ValueError, IndexError):
                pass

    # Close the progress bar
    pbar.close()

    # Check if the conversion was successful
    if process.returncode != 0:
        stderr = process.stderr.read()
        raise RuntimeError(f"Error converting audio: {stderr}")

    return output_file


def check_audio_format(audio_file:str):
    """
    Check if the audio file is in wav format.
    """
    if audio_file.endswith('.wav'):
        return True
    else:
        return False

def transcribe_audio(model, audio_file:str, language:str):
    """
    Transcribe audio file using Whisper model.
    """
    print(f"Transcribing audio using whisper {model}...")
    # Check for GPU availability and set device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    # Load the model
    model = whisper.load_model(model, device=device)
    # Transcribe the audio file with timestamps
    result = model.transcribe(
        audio_file,
        language=language,
        verbose=True,
        word_timestamps=True,
    )
    return result


def write_transcript_to_file(transcript, output_file:str):
    """
    Write the transcript to a text file.
    """
    with open(output_file, 'w') as f:
        for segment in transcript['segments']:
            start = segment['start']
            end = segment['end']
            text = segment['text']
            f.write(f"{start:.2f} --> {end:.2f}\n{text}\n\n")
    print(f"Transcript saved to {output_file}")


if __name__ == "__main__":
    args = parse_arguments()
    audio_file = args.audio_file
    output_dir = args.output_dir
    whisper_model = args.whisper_model
    language = args.language

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Convert audio file to wav format if not already in wav format
    if not check_audio_format(audio_file):
        print("Audio file is not in wav format. Converting...")
        wav_file = convert_to_wav(audio_file, os.path.join(output_dir, "audio.wav"))
        print(f"Converted audio file saved to {wav_file}")
    else:
        print("Audio file is in wav format. Beginning transcription...")
        wav_file = audio_file

    transcription = transcribe_audio(whisper_model, wav_file, language)
    write_transcript_to_file(transcription, os.path.join(output_dir, "output/test_transcription.txt"))