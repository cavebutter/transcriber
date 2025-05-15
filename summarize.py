import requests
import json
import re
import os
import docx
import argparse

address = 'http://localhost:11434/api/generate'
model = 'qwen3-summarizer'
payload = {
    'model': model,
    'prompt': None,
    'stream': False,
}

bullet_prompt = """What follows is a diarized transcript of a meeting between a number of people in the electric utility
industry in the United States. Topics discussed will be related to that or related to project management and software
development activities to support the electric utility. Your output should be in markdown with the following sections: 
1. For each key topic discussed: a name for the topic, bulleted list of key points, and action items related to each topic.
Do not include anything else except for the above. No extraneous words. \n \n"""

exec_summary_prompt = """What follows is a list of key topics discussed in a meeting between a number of people in the electric utility.
Your output should be in markdown and be limited to a single paragraph executive summary of the meeting and the action items
 from each section. No extraneous words.\n \n"""

markdown_prompt = """What follows are two markdown documents separated by two new blank lines. The first is an executive summary of a meeting, and the
second is a list of key topics discussed in the meeting. Your task is to combine the two documents into a single markdown document
with the executive summary at the top, followed by the list of key topics discussed. The output should be in markdown format,
with sensible headings and subheadings. Use the following heading schema as a guide: H1: Meeting Name and Date;
H2: Executive Summary and Key Discussion Topics and Decisions, and Next Steps.
H3: Any subordinate topics.
The meeting title and date are identified by "Meeting Title:" and "meeting date:" in the text.
No extraneous words and absolutely no additional formatting such as horizontal lines or em-dashes.\n \n"""

copy_edit_prompt = """
You are a copy editor whose life depends on meticulously following these formatting rules and applying edits to the 
supplied markdown document such that it is in strict conformance with the rules. Failure to do so will result in imprisonment
and a heavy fine for you personally.
H1: Meeting Name and Date. These are provided below in the text. Format the meeting name and date as a single line.
H2: Executive Summary. This is provided in the text below. The executive summary must be included verbatim and not changed
in any way aside from the formatting.
H2: Participants. Table of particpants. The list of participants must be formatted as a table with up to 4 columns and 
no header. Participants' names will be inserted into each column, adding additonal rows if necessary. The table must be 
formatted as a markdown table with no title or caption. The first row must not be bolded. The table should be placed 
directly after the executive summary.
H2: Key Discussion Topics and Decisions. This is provided in the text below following two blank lines after the executive
summary. The key discussion topics and decisions must be included verbatim and not changed in any way aside from the formatting.
H3: Any subordinate topics. These are provided in the text below as part of the key discussion topics and decisions. They 
must be included verbatim and not changed in any way aside from the formatting.
H2: Next Steps. These are provided in the text below as part of the key discussion topics and decisions. They must be included
verbatim and not changed in any way aside from the formatting.
This markdown will be applied to a CSS document and applied to a PDF. The CSS will handle all formatting and styling.
Do not add any additional formatting or styling to the markdown. Do not add any additional text or information to the markdown.
Remove any extraneous text or formatting in the markdown document that is not related to headings. This includes any em-dashes, horizontal lines, or other formatting.
"""

def parse_args():
    parser = argparse.ArgumentParser(description="Summarize a meeting transcript.")
    parser.add_argument('transcript_file', type=str, help='Path to the transcript file (.txt or .docx)')
    parser.add_argument('--title', '-t', type=str, help='Title of the meeting')
    parser.add_argument('--date', '-d', type=str, help='Date of the meeting')
    parser.add_argument('--output-dir', '-o', type=str, default='.', help='Directory to save the output markdown file')
    return parser.parse_args()


def load_diarized_transcript(transcript_file):
    """
    Load a transcript file based on its extension (.txt or .docx)

    Returns:
        tuple: (transcript_text, participants) where participants is a list or None
    """
    _, ext = os.path.splitext(transcript_file)
    participants = None

    if ext.lower() == '.txt':
        with open(transcript_file) as f:
            transcript = f.read()
    elif ext.lower() == '.docx':
        transcript = extract_text_from_docx(transcript_file)
        participants = extract_participants_from_teams_docx(transcript_file)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .txt and .docx are supported.")

    return transcript, participants


def extract_text_from_docx(docx_file):
    """
    Extract text content from MS Teams transcript (.docx) file,
    ignoring images and preserving speaker information and timestamps.
    """
    print(f"Loading MS Teams transcript from {docx_file}...")
    doc = docx.Document(docx_file)
    transcript_text = []

    # Process paragraphs to extract speaker info and text
    current_speaker = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # In Teams transcripts, speaker is typically in bold text
        # followed by timestamp and then the actual content
        if ':' in text and len(text.split(':')[0]) < 50:  # Simple heuristic for speaker line
            parts = text.split(':', 1)
            speaker_info = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""

            # Extract speaker name (might contain timestamp too)
            current_speaker = speaker_info
            if content:
                transcript_text.append(f"{current_speaker}: {content}")
        else:
            # This is content from the previous speaker
            if current_speaker:
                transcript_text.append(f"{current_speaker}: {text}")
            else:
                transcript_text.append(text)

    return '\n'.join(transcript_text)


def extract_participants_from_teams_docx(docx_file):
    """
    Extract a list of unique participants from MS Teams transcript (.docx) file.
    Cleans up names to remove timestamps and numeric indicators.

    Args:
        docx_file (str): Path to the MS Teams transcript docx file

    Returns:
        list: A list of unique participant names
    """
    print(f"Extracting participants from MS Teams transcript: {docx_file}...")
    doc = docx.Document(docx_file)
    participants = set()

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # In Teams transcripts, speaker is typically before the colon
        if ':' in text and len(text.split(':')[0]) < 50:  # Simple heuristic for speaker line
            speaker_info = text.split(':', 1)[0].strip()

            # Clean up speaker info by extracting just the name
            # Remove timestamps like (10:45) and numeric indicators like "35"
            speaker_name = speaker_info

            # Remove content in parentheses (like timestamps)
            if '(' in speaker_name:
                speaker_name = speaker_name.split('(')[0].strip()

            # Remove any trailing numbers after the name with spaces
            speaker_name = re.sub(r'\s+\d+\s*$', '', speaker_name)

            # Only add non-empty names and avoid date-like entries
            if speaker_name and not re.match(
                    r'^(January|February|March|April|May|June|July|August|September|October|November|December)',
                    speaker_name):
                participants.add(speaker_name)

    # Convert set to sorted list
    return sorted(list(participants))

def ollama_request_think_tags(payload_:dict):
    response = requests.post(address, json=payload)
    if response.status_code == 200:
        response_data = response.json()
        full_response = response_data['response']

        match = re.search(r'</think>(.*)', full_response, re.DOTALL)
        if match:
            text_after_think = match.group(1).strip()
            return text_after_think
        else:
            return full_response
    else:
        return None


def get_bullet_summary(transcript_file: str):
    transcript, participants = load_diarized_transcript(transcript_file)

    # Update prompt with participant information if available
    local_bullet_prompt = bullet_prompt
    if participants:
        participants_str = ", ".join(participants)
        local_bullet_prompt += f"Meeting participants: {participants_str}\n\n"

    payload['prompt'] = local_bullet_prompt + transcript
    bullet_summary = ollama_request_think_tags(payload)
    return bullet_summary, participants


def get_exec_summary(bullet_summary:str):
    payload['prompt'] = exec_summary_prompt + bullet_summary
    exec_summary = ollama_request_think_tags(payload)
    return exec_summary


def get_markdown_document(exec_summary: str, bullet_summary: str, output_file: str, participants=None):
    prompt = markdown_prompt

    # Add participants table to the prompt if available
    if participants and len(participants) > 0:
        participants_md = "## Meeting Participants\n\n"
        participants_md += "| Participant |\n|---|\n"
        for participant in participants:
            participants_md += f"| {participant} |\n"

        prompt += "Include the following participants table after the executive summary:\n\n" + participants_md + "\n\n"

    payload['prompt'] = prompt + exec_summary + '\n\n' + bullet_summary
    markdown_document = ollama_request_think_tags(payload)
    with open(output_file, 'w') as f:
        f.write(exec_summary)
        f.write('\n\n')
        if participants and len(participants) > 0:
            f.write("## Meeting Participants\n\n")
            f.write("| Participant |\n|---|\n")
            for participant in participants:
                f.write(f"| {participant} |\n")
            f.write('\n\n')
        f.write(bullet_summary)
    return markdown_document


def copy_edit_markdown_document(markdown_document:str, output_file:str, title:str, date:str):
    payload['prompt'] = copy_edit_prompt + markdown_document + f"\n\nMeeting Title: {title}\nMeeting Date: {date}"
    copy_edit_document = ollama_request_think_tags(payload)
    with open(output_file, 'w') as f:
        f.write(copy_edit_document)
    return copy_edit_document


if __name__ == "__main__":
    args = parse_args()

    # Get transcript file from args
    transcript_file = args.transcript_file

    # Create output filename with same name but .md extension in the specified output directory
    base_name = os.path.basename(os.path.splitext(transcript_file)[0])
    output_file = os.path.join(args.output_dir, f"{base_name}.md")

    print(f"Processing transcript: {transcript_file}")
    print(f"Output will be saved to: {output_file}")

    bullet_summary, participants = get_bullet_summary(transcript_file)
    exec_summary = get_exec_summary(bullet_summary)
    markdown_document = get_markdown_document(
        exec_summary,
        bullet_summary,
        output_file,
        participants
    )
    print(f"Markdown document saved to {output_file}")
    # Copy edit the markdown document
    copy_edit_output_file = os.path.join(args.output_dir, f"{base_name}_copyedited.md")
    copy_edit_markdown_document(
        markdown_document,
        copy_edit_output_file,
        args.title,
        args.date,
    )
    print(f"Copy-edited markdown document saved to {copy_edit_output_file}")