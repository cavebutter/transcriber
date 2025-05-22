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
from dotenv import load_dotenv



def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Process audio file with transcription and speaker diarization")

    # Required arguments
    parser.add_argument("audio_file", type=str, help="Path to the audio file to process")

    # Output options
    parser.add_argument("--output_dir", "-o", type=str, default="output",
                        help="Directory to save output files")

    # Processing options
    parser.add_argument("--whisper_model", type=str, default="large",
                        choices=["tiny", "base", "small", "medium", "large", "large-v2"],
                        help="Whisper model size (larger models are more accurate but slower)")
    parser.add_argument("--language", type=str, default="en",
                        help="Language code for transcription (e.g., 'en' for English)")

    # Diarization options
    parser.add_argument("--diarize", action="store_true",
                        help="Perform speaker diarization")
    parser.add_argument("--min_speakers", type=int, default=None,
                        help="Minimum number of speakers (optional)")
    parser.add_argument("--max_speakers", type=int, default=None,
                        help="Maximum number of speakers (optional)")

    return parser.parse_args()


def convert_to_wav(audio_file: str, output_file: str):
    """
    Convert audio file to wav format using ffmpeg.

    Args:
        audio_file: Path to the input audio file
        output_file: Path to save the converted WAV file

    Returns:
        str: Path to the converted WAV file

    Raises:
        RuntimeError: If ffmpeg is not installed or conversion fails
    """
    # Check if ffmpeg is installed
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    print(f"Converting {audio_file} to WAV format (16kHz mono)...")

    # Simplified ffmpeg command that avoids pipe reading that might hang
    command = [
        'ffmpeg',
        '-i', audio_file,
        '-acodec', 'pcm_s16le',
        '-ar', '16000',  # 16kHz sampling rate
        '-ac', '1',  # Mono audio
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


def transcribe_audio(model_name, audio_file: str, language: str,
                     temperature=0.0, beam_size=5, save_intermediate=True,
                     temp_dir=None):
    """
    Transcribe audio file using Whisper model.

    Args:
        model_name: Size of Whisper model to use (tiny, base, small, medium, large)
        audio_file: Path to the audio file to transcribe
        language: Language code for transcription
        temperature: Temperature for sampling (lower = more deterministic)
        beam_size: Beam size for decoding
        save_intermediate: Whether to save intermediate results
        temp_dir: Directory for temporary files (if None, uses system temp)

    Returns:
        dict: Transcription result with segments and metadata
    """
    print(f"Transcribing audio using Whisper {model_name} model...")

    # Check for GPU availability and set device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    try:
        start_time = time.time()

        # Load the model
        model = whisper.load_model(model_name, device=device)
        model_load_time = time.time() - start_time
        print(f"Model loaded in {model_load_time:.2f} seconds")

        # Transcribe the audio file with timestamps
        transcribe_start = time.time()
        result = model.transcribe(
            audio_file,
            language=language,
            verbose=True,
            word_timestamps=True,
            temperature=temperature,
            beam_size=beam_size
        )

        total_time = time.time() - start_time
        transcribe_time = time.time() - transcribe_start

        # Save intermediate results if requested
        if save_intermediate and temp_dir:
            base_name = os.path.splitext(os.path.basename(audio_file))[0]
            temp_result_file = os.path.join(temp_dir, f"temp_{base_name}_transcription.json")
            with open(temp_result_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Saved intermediate result to {temp_result_file}")

        print(f"Transcription completed in {transcribe_time:.2f} seconds (total time: {total_time:.2f} seconds)")
        print(f"Detected language: {result.get('language', 'unknown')}")
        print(f"Total segments: {len(result.get('segments', []))}")

        return result
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        raise

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


def perform_diarization(audio_file: str,
                        min_speakers: Optional[int] = None,
                        max_speakers: Optional[int] = None,
                        model_version: str = "pyannote/speaker-diarization-3.1",
                        save_intermediate: bool = True,
                        temp_dir=None) -> Dict:
    """
    Perform speaker diarization on the audio file using pyannote.audio.

    Args:
        audio_file: Path to the audio file (should be WAV format)
        min_speakers: Minimum number of speakers (optional constraint)
        max_speakers: Maximum number of speakers (optional constraint)
        model_version: Version of the pyannote diarization model to use
        save_intermediate: Whether to save intermediate results
        temp_dir: Directory for temporary files (if None, uses system temp)

    Returns:
        Dictionary containing speaker segments with timestamps
    """
    print("Performing speaker diarization...")

    # Get HF token from environment
    hf_token = os.getenv('HF_TOKEN')
    if not hf_token:
        raise ValueError(
            "HuggingFace token not provided. Set the HF_TOKEN environment variable.")

    # Initialize the pipeline
    try:
        # Free up GPU memory if possible
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("Cleared CUDA cache before loading diarization model")

        print(f"Loading diarization model {model_version}...")
        start_load_time = time.time()
        diarization_pipeline = Pipeline.from_pretrained(
            model_version,
            use_auth_token=hf_token
        )
        load_time = time.time() - start_load_time
        print(f"Model loaded in {load_time:.2f} seconds")

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
        print(f"Parameters: {params}")

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

        # Save intermediate result if requested
        if save_intermediate and temp_dir:
            base_name = os.path.splitext(os.path.basename(audio_file))[0]
            temp_result_file = os.path.join(temp_dir, f"temp_{base_name}_diarization.json")
            try:
                with open(temp_result_file, 'w') as f:
                    json.dump(diarization_data, f, indent=2)
                print(f"Saved intermediate diarization result to {temp_result_file}")
            except Exception as e:
                print(f"Warning: Could not save intermediate result: {e}")

        print(f"Identified {len(diarization_data)} speaker(s)")
        return diarization_data

    except ImportError as e:
        print(f"Error: Pyannote.audio not properly installed: {str(e)}")
        print("Try reinstalling with: pip install pyannote.audio==3.3.2")
        raise
    except Exception as e:
        print(f"Error during diarization: {str(e)}")
        if "CUDA" in str(e):
            print("This might be a CUDA compatibility issue. Try using CPU instead.")
        elif "auth" in str(e).lower():
            print("This might be an authentication issue with your HuggingFace token.")
        raise

def combine_transcript_with_diarization(transcription: Dict, diarization_data: Dict,
                                        output_file: str, time_tolerance: float = 0.5) -> Dict:
    """
    Combine transcription and diarization results to create a diarized transcript.

    Args:
        transcription: Transcription results from Whisper
        diarization_data: Speaker diarization results
        output_file: Path to save the combined output
        time_tolerance: Tolerance in seconds for matching segments

    Returns:
        Dict: Combined diarized transcript
    """
    print("Combining transcription with speaker diarization...")

    # Create a flat list of all speaker segments
    speaker_segments = []
    for speaker, segments in diarization_data.items():
        for segment in segments:
            speaker_segments.append({
                "speaker": speaker,
                "start": segment["start"],
                "end": segment["end"]
            })

    # Sort by start time
    speaker_segments.sort(key=lambda x: x["start"])

    # Combine with transcription segments
    diarized_transcript = []
    for segment in transcription.get("segments", []):
        segment_start = segment.get("start", 0)
        segment_end = segment.get("end", 0)
        segment_text = segment.get("text", "").strip()

        # Find matching speaker(s)
        matching_speakers = []
        for speaker_segment in speaker_segments:
            # Check if segments overlap
            if (speaker_segment["start"] <= segment_end + time_tolerance and
                    speaker_segment["end"] + time_tolerance >= segment_start):
                matching_speakers.append(speaker_segment["speaker"])

        # Use the most frequent speaker if multiple matches
        speaker = max(set(matching_speakers), key=matching_speakers.count) if matching_speakers else "Unknown Speaker"

        diarized_transcript.append({
            "speaker": speaker,
            "start": segment_start,
            "end": segment_end,
            "text": segment_text
        })

    # Save the diarized transcript to file
    with open(output_file, 'w') as f:
        for segment in diarized_transcript:
            timestamp = f"{segment['start']:.2f} --> {segment['end']:.2f}"
            f.write(f"{segment['speaker']} ({timestamp}):\n{segment['text']}\n\n")

    print(f"Diarized transcript saved to {output_file}")
    return {"segments": diarized_transcript}

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
    import tempfile
    import atexit

    # Load environment variables from .env file
    load_dotenv()

    args = parse_arguments()
    audio_file = args.audio_file
    output_dir = args.output_dir
    whisper_model = args.whisper_model
    language = args.language
    perform_diarize = args.diarize
    min_speakers = args.min_speakers
    max_speakers = args.max_speakers

    # Create temporary directory for intermediate files
    temp_dir = tempfile.mkdtemp(prefix="transcribe_temp_")
    print(f"Using temporary directory: {temp_dir}")


    # Register cleanup function to run on exit
    def cleanup_temp_files():
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            print(f"Warning: Could not clean up temp directory: {e}")


    atexit.register(cleanup_temp_files)

    # Validate HF_TOKEN early if diarization is requested
    if perform_diarize:
        hf_token = os.getenv('HF_TOKEN')
        if not hf_token:
            print("ERROR: Diarization requested but HF_TOKEN environment variable is not set.")
            print("Please set your HuggingFace token: export HF_TOKEN=your_token_here")
            print("You can get a token from: https://huggingface.co/settings/tokens")
            print("Also make sure to accept the terms at: https://huggingface.co/pyannote/speaker-diarization-3.1")
            cleanup_temp_files()  # Clean up before exiting
            exit(1)
        print("✓ HF_TOKEN found for diarization")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Set up paths
    base_filename = os.path.splitext(os.path.basename(audio_file))[0]
    wav_output_path = os.path.join(output_dir, f"{base_filename}.wav")
    transcript_output_path = os.path.join(output_dir, f"{base_filename}_transcription.txt")
    diarization_output_path = os.path.join(output_dir, f"{base_filename}_diarization.json")
    diarized_transcript_path = os.path.join(output_dir, f"{base_filename}_diarized_transcript.txt")

    # Validate the audio file path
    if not os.path.isfile(audio_file):
        cleanup_temp_files()
        raise FileNotFoundError(f"Audio file {audio_file} does not exist.")

    try:
        print(f"Starting processing of {audio_file}")
        print(f"Output directory: {output_dir}")
        print(f"Whisper model: {whisper_model}")
        print(f"Language: {language}")
        print(f"Diarization: {'Yes' if perform_diarize else 'No'}")

        # Convert audio file to wav format if not already in wav format
        if not check_audio_format(audio_file):
            print(f"Audio file is not in wav format. Converting {audio_file}...")
            wav_file = convert_to_wav(audio_file, wav_output_path)
            print(f"Converted audio file saved to {wav_file}")
        else:
            print("Audio file is already in wav format. Using as is.")
            wav_file = audio_file

        # Transcribe the audio
        print(f"Starting transcription with Whisper {whisper_model} model...")
        transcription = transcribe_audio(
            whisper_model,
            wav_file,
            language,
            save_intermediate=True,
            temp_dir=temp_dir
        )

        # Write the transcript to a file
        write_transcript_to_file(transcription, transcript_output_path)
        print(f"Transcription completed and saved to {transcript_output_path}")

        # Perform diarization if requested
        if perform_diarize:
            try:
                print("Starting speaker diarization...")
                diarization_data = perform_diarization(
                    wav_file,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                    save_intermediate=True,
                    temp_dir=temp_dir
                )
                write_diarization_to_file(diarization_data, diarization_output_path)
                print(f"Diarization completed and saved to {diarization_output_path}")

                # Combine transcription with diarization results
                combined_result = combine_transcript_with_diarization(
                    transcription,
                    diarization_data,
                    diarized_transcript_path
                )
                print(f"Diarized transcript saved to {diarized_transcript_path}")

            except Exception as e:
                print(f"Error during diarization: {e}")
                print("Continuing with transcription results only.")
                print("Hint: Check your HuggingFace token and ensure PyAnnote is correctly installed.")

        print("-" * 40)
        print("Processing summary:")
        print(f"- Audio file: {audio_file}")
        print(f"- Transcription file: {transcript_output_path}")
        if perform_diarize:
            print(f"- Diarization file: {diarization_output_path}")
            if os.path.exists(diarized_transcript_path):
                print(f"- Diarized transcript: {diarized_transcript_path}")
            else:
                print("- Diarized transcript: Failed to create")
        print("-" * 40)
        print("Processing complete!")

        # Cleanup happens automatically via atexit

    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback

        traceback.print_exc()
        print("Processing failed. Check the error message above.")
        cleanup_temp_files()  # Manual cleanup on error
        exit(1)