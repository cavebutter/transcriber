import os
import subprocess as sp
import whisper
import torch
from tqdm import tqdm
import argparse
import shutil


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Process audio file with transcription and diarization")
    parser.add_argument("audio_file", type=str, help="Path to the audio file to process")
    parser.add_argument("--output_dir", type=str, default="output", help="Directory to save output files")
    parser.add_argument("--whisper_model", type=str, default="large",
                        choices=["tiny", "base", "small", "medium", "large", "large-v2"],
                        help="Whisper model size")
    parser.add_argument("--language", type=str, default="en", help="Language code for transcription")
    return parser.parse_args()


def convert_to_wav(audio_file: str, output_file: str):
    """
    Convert audio file to wav format using ffmpeg.
    """
    # Check if ffmpeg is installed
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")

    print(f"Converting {audio_file} to WAV format...")

    # Simplified ffmpeg command that avoids pipe reading that might hang
    command = [
        'ffmpeg',
        '-i', audio_file,
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',  # Overwrite output file if it exists
        output_file
    ]

    try:
        # Use subprocess.run instead of Popen for simpler handling
        process = sp.run(command, check=True, capture_output=True, text=True)
        print(f"Successfully converted to {output_file}")
        return output_file
    except sp.CalledProcessError as e:
        print(f"Error during conversion: {e.stderr}")
        raise RuntimeError(f"Failed to convert audio file: {e}")


def check_audio_format(audio_file: str):
    """
    Check if the audio file is in wav format.
    """
    return audio_file.lower().endswith('.wav')


def transcribe_audio(model_name, audio_file: str, language: str):
    """
    Transcribe audio file using Whisper model.
    """
    print(f"Transcribing audio using whisper {model_name}...")
    # Check for GPU availability and set device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    # Load the model
    model = whisper.load_model(model_name, device=device)

    # Transcribe the audio file with timestamps
    result = model.transcribe(
        audio_file,
        language=language,
        verbose=True,
        word_timestamps=True,
    )
    return result


def write_transcript_to_file(transcript, output_file: str):
    """
    Write the transcript to a text file.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

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

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Set up paths
    base_filename = os.path.splitext(os.path.basename(audio_file))[0]
    wav_output_path = os.path.join(output_dir, f"{base_filename}.wav")
    transcript_output_path = os.path.join(output_dir, f"{base_filename}_transcription.txt")

    # Convert audio file to wav format if not already in wav format
    if not check_audio_format(audio_file):
        print(f"Audio file is not in wav format. Converting {audio_file}...")
        wav_file = convert_to_wav(audio_file, wav_output_path)
        print(f"Converted audio file saved to {wav_file}")
    else:
        print("Audio file is already in wav format. Using as is.")
        wav_file = audio_file

    # Transcribe the audio
    transcription = transcribe_audio(whisper_model, wav_file, language)

    # Write the transcript to a file
    write_transcript_to_file(transcription, transcript_output_path)
    print("Processing complete!")