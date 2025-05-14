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
industry in the United States. Your output should be in markdown with the following sections: 
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

# markdown_prompt = """You are being provided with 4 pieces of information. The first is an executive summary of a meeting
# in markdown format. The second is a list of key topics, decisions, and action items discussed in the meeting, also in markdown format.
# The third is the meeting title, identified by "Meeting Title:" in the text, and the fourth is the meeting date, identified by meeting date:" in the text.
# Your task is to combine all of this information into a single markdown document formatted as follows:
# H1: Meeting Name and Date
# H2: Executive Summary
# H2: Key Discussion Topics and Decisions
# H3: Any subordinate topics
# H2: Next Steps
# Do not include any extraneous words or information. If the meeting title and date are not present in your response, my
# boss will be very angry. Please make sure to include them.
# """



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
    """
    _, ext = os.path.splitext(transcript_file)

    if ext.lower() == '.txt':
        with open(transcript_file) as f:
            transcript = f.read()
        return transcript
    elif ext.lower() == '.docx':
        return extract_text_from_docx(transcript_file)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .txt and .docx are supported.")


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


def get_bullet_summary(transcript_file:str):
    transcript = load_diarized_transcript(transcript_file)
    payload['prompt'] = bullet_prompt + transcript
    bullet_summary = ollama_request_think_tags(payload)
    return bullet_summary


def get_exec_summary(bullet_summary:str):
    payload['prompt'] = exec_summary_prompt + bullet_summary
    exec_summary = ollama_request_think_tags(payload)
    return exec_summary


def get_markdown_document(exec_summary:str, bullet_summary:str, output_file:str, title:str='Meeting', date:str=None):
    payload['prompt'] = markdown_prompt + exec_summary + '\n\n' + bullet_summary + 'Meeting Title: ' + title + 'meeting date: ' + date if date else ''
    markdown_document = ollama_request_think_tags(payload)
    with open(output_file, 'w') as f:
        f.write(exec_summary)
        f.write('\n\n')
        f.write(bullet_summary)
    return markdown_document


if __name__ == "__main__":
    args = parse_args()

    # Get transcript file from args
    transcript_file = args.transcript_file

    # Create output filename with same name but .md extension in the specified output directory
    base_name = os.path.basename(os.path.splitext(transcript_file)[0])
    output_file = os.path.join(args.output_dir, f"{base_name}.md")

    print(f"Processing transcript: {transcript_file}")
    print(f"Output will be saved to: {output_file}")

    bullet_summary = get_bullet_summary(transcript_file)
    exec_summary = get_exec_summary(bullet_summary)
    markdown_document = get_markdown_document(
        exec_summary,
        bullet_summary,
        output_file,
        title=args.title or "Meeting",
        date=args.date
    )
    print(f"Markdown document saved to {output_file}")