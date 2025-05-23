import os
import tempfile
import subprocess as sp
import whisper
import torch
import json
import time
from typing import Dict, Optional
import shutil
from pyannote.audio import Pipeline
from flask import current_app


class TranscriptionProcessor:
    def __init__(self, whisper_model='large', enable_diarization=True,
                 min_speakers=None, max_speakers=None, temp_dir=None):
        self.whisper_model = whisper_model
        self.enable_diarization = enable_diarization
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.temp_dir = temp_dir or tempfile.gettempdir()

    def convert_to_wav(self, audio_file: str, output_dir: str) -> str:
        """Convert audio file to WAV format using ffmpeg."""
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found. Please install ffmpeg.")

        # Create output filename
        base_name = os.path.splitext(os.path.basename(audio_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}.wav")

        current_app.logger.info(f"Converting {audio_file} to WAV format")

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
            process = sp.run(command, check=True, capture_output=True, text=True)
            current_app.logger.info(f"Successfully converted to {output_file}")
            return output_file
        except sp.CalledProcessError as e:
            current_app.logger.error(f"Error during conversion: {e.stderr}")
            raise RuntimeError(f"Failed to convert audio file: {e}")

    def transcribe_audio(self, audio_file: str) -> Dict:
        """Transcribe audio file using Whisper."""
        current_app.logger.info(f"Transcribing audio using Whisper {self.whisper_model} model")

        # Check for GPU availability
        device = "cuda" if torch.cuda.is_available() else "cpu"
        current_app.logger.info(f"Using device: {device}")

        try:
            start_time = time.time()

            # Load the model
            model = whisper.load_model(self.whisper_model, device=device)
            model_load_time = time.time() - start_time
            current_app.logger.info(f"Model loaded in {model_load_time:.2f} seconds")

            # Transcribe with word timestamps
            transcribe_start = time.time()
            result = model.transcribe(
                audio_file,
                language='en',  # Default to English for now
                verbose=True,
                word_timestamps=True,
                temperature=0.0,
                beam_size=5
            )

            transcribe_time = time.time() - transcribe_start
            current_app.logger.info(f"Transcription completed in {transcribe_time:.2f} seconds")
            current_app.logger.info(f"Detected language: {result.get('language', 'unknown')}")
            current_app.logger.info(f"Total segments: {len(result.get('segments', []))}")

            return result

        except Exception as e:
            current_app.logger.error(f"Error during transcription: {str(e)}")
            raise

    def perform_diarization(self, audio_file: str) -> Dict:
        """Perform speaker diarization using pyannote.audio."""
        current_app.logger.info("Performing speaker diarization")

        # Get HF token from config
        hf_token = current_app.config.get('HF_TOKEN')
        if not hf_token:
            raise ValueError("HuggingFace token not provided in configuration")

        try:
            # Free up GPU memory if possible
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                current_app.logger.info("Cleared CUDA cache before loading diarization model")

            # Load diarization pipeline
            start_load_time = time.time()
            diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            load_time = time.time() - start_load_time
            current_app.logger.info(f"Diarization model loaded in {load_time:.2f} seconds")

            # Move to GPU if available
            if torch.cuda.is_available():
                diarization_pipeline = diarization_pipeline.to(torch.device("cuda"))
                current_app.logger.info("Using GPU for diarization")
            else:
                current_app.logger.info("Using CPU for diarization")

            # Set up parameters
            params = {}
            if self.min_speakers is not None and self.max_speakers is not None:
                if self.min_speakers > self.max_speakers:
                    raise ValueError("min_speakers cannot be greater than max_speakers")
                params["num_speakers"] = (self.min_speakers, self.max_speakers)
            elif self.min_speakers is not None:
                params["min_speakers"] = self.min_speakers
            elif self.max_speakers is not None:
                params["max_speakers"] = self.max_speakers

            # Run diarization
            start_time = time.time()
            diarization_result = diarization_pipeline(audio_file, **params)
            processing_time = time.time() - start_time
            current_app.logger.info(f"Diarization completed in {processing_time:.2f} seconds")

            # Convert to usable format
            diarization_data = {}
            for turn, _, speaker in diarization_result.itertracks(yield_label=True):
                if speaker not in diarization_data:
                    diarization_data[speaker] = []

                diarization_data[speaker].append({
                    "start": turn.start,
                    "end": turn.end,
                    "duration": turn.end - turn.start
                })

            current_app.logger.info(f"Identified {len(diarization_data)} speaker(s)")
            return diarization_data

        except Exception as e:
            current_app.logger.error(f"Error during diarization: {str(e)}")
            raise

    def create_diarized_transcript(self, transcription: Dict, diarization_data: Dict,
                                   output_dir: str, time_tolerance: float = 0.5) -> str:
        """Combine transcription and diarization results."""
        current_app.logger.info("Combining transcription with speaker diarization")

        # Create flat list of speaker segments
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

        # Combine with transcription
        diarized_transcript = []
        for segment in transcription.get("segments", []):
            segment_start = segment.get("start", 0)
            segment_end = segment.get("end", 0)
            segment_text = segment.get("text", "").strip()

            # Find matching speakers
            matching_speakers = []
            for speaker_segment in speaker_segments:
                if (speaker_segment["start"] <= segment_end + time_tolerance and
                        speaker_segment["end"] + time_tolerance >= segment_start):
                    matching_speakers.append(speaker_segment["speaker"])

            # Use most frequent speaker
            speaker = max(set(matching_speakers),
                          key=matching_speakers.count) if matching_speakers else "Unknown Speaker"

            diarized_transcript.append({
                "speaker": speaker,
                "start": segment_start,
                "end": segment_end,
                "text": segment_text
            })

        # Save to file
        output_file = os.path.join(output_dir, "diarized_transcript.txt")
        with open(output_file, 'w') as f:
            for segment in diarized_transcript:
                timestamp = f"{segment['start']:.2f} --> {segment['end']:.2f}"
                f.write(f"{segment['speaker']} ({timestamp}):\n{segment['text']}\n\n")

        current_app.logger.info(f"Diarized transcript saved to {output_file}")
        return output_file

    def create_simple_transcript(self, transcription: Dict, output_dir: str) -> str:
        """Create simple transcript without diarization."""
        output_file = os.path.join(output_dir, "transcript.txt")

        with open(output_file, 'w') as f:
            for segment in transcription.get('segments', []):
                start = segment['start']
                end = segment['end']
                text = segment['text']
                f.write(f"{start:.2f} --> {end:.2f}\n{text}\n\n")

        current_app.logger.info(f"Transcript saved to {output_file}")
        return output_file