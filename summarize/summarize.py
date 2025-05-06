import requests
import json
import re

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
with sensible headings and subheadings. No extraneous words.\n \n"""

def load_diarized_transcript(transcript_file):
    with open(transcript_file) as f:
        transcript = f.read()
    return transcript


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


def get_markdown_document(exec_summary:str, bullet_summary:str, output_file:str):
    payload['prompt'] = markdown_prompt + exec_summary + '\n\n' + bullet_summary
    markdown_document = ollama_request_think_tags(payload)
    with open(output_file, 'w') as f:
        f.write(exec_summary)
        f.write('\n\n')
        f.write(bullet_summary)
    return markdown_document

if __name__ == "__main__":
    bullet_summary = get_bullet_summary('/mnt/hdd/transcripts/SCE-4-1-25_diarized.txt')
    exec_summary = get_exec_summary(bullet_summary)
    markdown_document = get_markdown_document(exec_summary, bullet_summary, '/mnt/hdd/transcripts/SCE-4-1-25_diarized.md')