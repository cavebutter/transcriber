import os
import subprocess as sp
import whisper
import torch
from tqdm import tqdm
import argparse
import shutil
import json
import time
from typing import Dict, List, Tuple, Optional
from pyannote.audio import Pipeline
import numpy as np


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Process audio file with transcription and speaker diarization")

    # Required arguments
    parser.add_argument("audio_file", type=str, help="Path to the audio file to process")

    # Output options
    parser.add_argument("--output_dir", "-o", type=str, default="output",
                        help="Directory to save output files")

    # Processing options
    parser.add_argument("--whisper_model", type=str, default="base",
                        choices=["tiny", "base", "small", "medium", "large", "large-v2"],
                        help="Whisper model size (larger models are more accurate but slower)")
    parser.add_argument("--language", type=str, default="en",
                        help="Language code for transcription (e.g., 'en' for English)")

    # Diarization options
    parser.add_argument("--diarize", action="store_true",
                        help="Perform speaker diarization")
    parser.add_argument("--hf_token", type=str, default=None,
                        help="HuggingFace access token (if not set in environment)")
    parser.add_argument("--min_speakers", type=int, default=None,
                        help="Minimum number of speakers (optional)")
    parser.add_argument("--max_speakers", type=int, default=None,
                        help="Maximum number of speakers (optional)")

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


def perform_diarization(audio_file: str, hf_token: Optional[str] = None,
                        min_speakers: Optional[int] = None,
                        max_speakers: Optional[int] = None) -> Dict:
    """
    Perform speaker diarization on the audio file using pyannote.audio.

    Args:
        audio_file: Path to the audio file (should be WAV format)
        hf_token: HuggingFace access token (optional if already set in environment)
        min_speakers: Minimum number of speakers (optional constraint)
        max_speakers: Maximum number of speakers (optional constraint)

    Returns:
        Dictionary containing speaker segments with timestamps
    """
    print("Performing speaker diarization...")

    # Get HF token from environment if not provided
    if hf_token is None:
        hf_token = os.getenv('HF_TOKEN')
        if not hf_token:
            raise ValueError(
                "HuggingFace token not provided. Set the HF_TOKEN environment variable or pass it as an argument.")

    # Initialize the pipeline
    try:
        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )

        # Check for CUDA availability and move to GPU if available
        if torch.cuda.is_available():
            diarization_pipeline = diarization_pipeline.to(torch.device("cuda"))
            print("Using GPU for diarization")
        else:
            print("Using CPU for diarization")

        # Set up parameters for diarization
        params = {}
        if min_speakers is not None and max_speakers is not None:
            if min_speakers > max_speakers:
                raise ValueError("min_speakers cannot be greater than max_speakers")
            params["num_speakers"] = (min_speakers, max_speakers)
        elif min_speakers is not None:
            params["min_speakers"] = min_speakers
        elif max_speakers is not None:
            params["max_speakers"] = max_speakers

        # Run the diarization
        print(f"Processing {audio_file} for speaker diarization...")
        start_time = time.time()
        diarization_result = diarization_pipeline(audio_file, **params)
        processing_time = time.time() - start_time
        print(f"Diarization completed in {processing_time:.2f} seconds")

        # Convert the diarization result to a more usable format
        diarization_data = {}
        for turn, _, speaker in diarization_result.itertracks(yield_label=True):
            if speaker not in diarization_data:
                diarization_data[speaker] = []

            diarization_data[speaker].append({
                "start": turn.start,
                "end": turn.end,
                "duration": turn.end - turn.start
            })

        print(f"Identified {len(diarization_data)} speaker(s)")
        return diarization_data

    except Exception as e:
        print(f"Error during diarization: {str(e)}")
        raise


def write_diarization_to_file(diarization_data: Dict, output_file: str):
    """
    Write speaker diarization results to a JSON file.

    Args:
        diarization_data: Dictionary containing speaker segments
        output_file: Path to output file
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Convert any non-serializable types to strings or numbers
    serializable_data = {}
    for speaker, segments in diarization_data.items():
        serializable_data[speaker] = [
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "duration": float(segment["duration"])
            }
            for segment in segments
        ]

    # Write to file
    with open(output_file, 'w') as f:
        json.dump(serializable_data, f, indent=2)

    print(f"Diarization results saved to {output_file}")


if __name__ == "__main__":
    args = parse_arguments()
    audio_file = args.audio_file
    output_dir = args.output_dir
    whisper_model = args.whisper_model
    language = args.language
    perform_diarize = args.diarize
    hf_token = args.hf_token
    min_speakers = args.min_speakers
    max_speakers = args.max_speakers

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Set up paths
    base_filename = os.path.splitext(os.path.basename(audio_file))[0]
    wav_output_path = os.path.join(output_dir, f"{base_filename}.wav")
    transcript_output_path = os.path.join(output_dir, f"{base_filename}_transcription.txt")
    diarization_output_path = os.path.join(output_dir, f"{base_filename}_diarization.json")

    # Validate the audio file path
    if not os.path.isfile(audio_file):
        raise FileNotFoundError(f"Audio file {audio_file} does not exist.")

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

    # Perform diarization if requested
    if perform_diarize:
        try:
            diarization_data = perform_diarization(
                wav_file,
                hf_token=hf_token,
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )
            write_diarization_to_file(diarization_data, diarization_output_path)
            print(f"Diarization completed and saved to {diarization_output_path}")
        except Exception as e:
            print(f"Error during diarization: {e}")
            print("Continuing with transcription results only.")

    print("Processing complete!")