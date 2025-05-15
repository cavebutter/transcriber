import requests
import json
import re
import os
import docx
import argparse
import jinja2
import datetime
import shutil
from md_to_pdf import convert_md_to_pdf

address = 'http://localhost:11434/api/generate'
model = 'qwen3-summarizer'
payload = {
    'model': model,
    'prompt': None,
    'stream': False,
}

bullet_prompt = """What follows is a diarized transcript of a meeting between a number of people in the electric utility
industry in the United States. Topics discussed will be related to that or related to project management and software
development activities to support the electric utility. 

Your output should be in proper markdown format with the following:
1. Use ** for bold text (e.g., **important point**)
2. Use ### for topic headings (level 3 headers)
3. Use - for bulleted lists
4. Use blank lines between paragraphs

You must include the following sections: 
1. For each key topic discussed: a name for the topic as a level 3 header (###), a bulleted list of key points using dashes (-), and action items highlighted in bold.
Do not include anything else except for the above. No extraneous words or HTML formatting. \n \n"""


exec_summary_prompt = """What follows is a list of key topics discussed in a meeting between a number of people in the electric utility.
Your output should be in plain text using markdown formatting (use ** for bold, not HTML tags).
Your output will be limited to a single paragraph executive summary of the meeting and the action items from each section.
No extraneous words or HTML formatting at all.\n \n"""


# Keep the existing prompts for generating the content in markdown format
# We'll convert the markdown to HTML later

def parse_args():
    parser = argparse.ArgumentParser(description="Summarize a meeting transcript.")
    parser.add_argument('transcript_file', type=str, help='Path to the transcript file (.txt or .docx)')
    parser.add_argument('--title', '-t', type=str, help='Title of the meeting')
    parser.add_argument('--date', '-d', type=str, help='Date of the meeting')
    parser.add_argument('--output-dir', '-o', type=str, default='.', help='Directory to save the output files')
    parser.add_argument('--format', '-f', type=str, choices=['md', 'html', 'pdf'], default='html',
                        help='Output format (md=markdown, html=HTML, pdf=PDF)')
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


def ollama_request_think_tags(payload_: dict):
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


def get_exec_summary(bullet_summary: str):
    payload['prompt'] = exec_summary_prompt + bullet_summary
    exec_summary = ollama_request_think_tags(payload)
    return exec_summary


def get_markdown_document(exec_summary: str, bullet_summary: str, output_file: str, participants=None):
    """Generate a markdown document and save to file"""
    with open(output_file, 'w') as f:
        # Executive Summary Section
        f.write("# Executive Summary\n\n")
        f.write(exec_summary)
        f.write('\n\n')

        # Participants Section if available
        if participants and len(participants) > 0:
            f.write("## Meeting Participants\n\n")
            # Create 4-column table for participants
            cols = 4
            rows = (len(participants) + cols - 1) // cols  # Ceiling division

            # Create markdown table with empty headers
            headers = "| " + " | ".join(["Participant"] * min(cols, len(participants))) + " |\n"
            separator = "| " + " | ".join(["---"] * min(cols, len(participants))) + " |\n"

            f.write(headers)
            f.write(separator)

            # Fill table with participants
            for i in range(rows):
                row = "| "
                for j in range(cols):
                    idx = i + j * rows
                    if idx < len(participants):
                        row += participants[idx] + " | "
                    else:
                        row += " | "
                f.write(row.strip() + "\n")
            f.write('\n\n')

        # Key Discussion Topics Section
        f.write("## Key Discussion Topics and Decisions\n\n")

        # Ensure proper markdown formatting
        # Replace HTML tags with markdown equivalents
        cleaned_summary = bullet_summary
        cleaned_summary = cleaned_summary.replace("<strong>", "**").replace("</strong>", "**")
        cleaned_summary = cleaned_summary.replace("<ul>", "").replace("</ul>", "")
        cleaned_summary = cleaned_summary.replace("<li>", "- ").replace("</li>", "")
        cleaned_summary = cleaned_summary.replace("<h3>", "### ").replace("</h3>", "")
        cleaned_summary = cleaned_summary.replace("<p>", "").replace("</p>", "\n\n")

        f.write(cleaned_summary)

    return exec_summary, bullet_summary, participants


def markdown_to_html(title, date, exec_summary, bullet_summary, participants, output_dir="."):
    """Convert markdown content to HTML using Jinja2"""
    # First, ensure bullet_summary is a string
    if isinstance(bullet_summary, list):
        bullet_summary = "\n".join(bullet_summary)

    # Define template and CSS locations
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(current_dir, "templates")
    template_name = "meeting_template.html"
    css_name = "template.css"

    # Create templates directory if it doesn't exist
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)

    template_path = os.path.join(template_dir, template_name)
    css_path = os.path.join(template_dir, css_name)

    # If template doesn't exist, create it
    if not os.path.exists(template_path):
        create_html_template(template_path)

    # If CSS doesn't exist, create it
    if not os.path.exists(css_path):
        create_css_template(css_path)

    # Copy CSS to output directory - this is the key change
    output_css_path = os.path.join(output_dir, css_name)
    shutil.copy2(css_path, output_css_path)
    print(f"Copied CSS file to: {output_css_path}")

    # Setup Jinja2 environment
    template_loader = jinja2.FileSystemLoader(searchpath=template_dir)
    template_env = jinja2.Environment(loader=template_loader)

    # Load template
    template = template_env.get_template(template_name)

    # Convert bullet summary to HTML
    bullet_html = markdown_to_html_content(bullet_summary)

    # Format participants into a table with up to 4 columns
    participants_html = ""
    if participants:
        participants_html = "<table class='participants-table'>"
        cols = 4
        rows = (len(participants) + cols - 1) // cols  # Ceiling division

        for i in range(rows):
            participants_html += "<tr>"
            for j in range(cols):
                idx = i + j * rows
                if idx < len(participants):
                    participants_html += f"<td>{participants[idx]}</td>"
                else:
                    participants_html += "<td></td>"
            participants_html += "</tr>"
        participants_html += "</table>"

    # Get current date if not provided
    if not date:
        date = datetime.datetime.now().strftime("%B %d, %Y")

    # Render template - the HTML should use a relative path to CSS
    html_content = template.render(
        title=title or "Meeting Summary",
        date=date,
        executive_summary=exec_summary,
        participants_html=participants_html,
        content=bullet_html,
        current_year=datetime.datetime.now().year
    )

    return html_content



def create_css_template(css_path):
    """Create a default CSS template for meeting summaries"""
    css_content = """@page {
    size: letter;
    margin: 2.5cm 1.5cm 2.5cm 1.5cm;
}

body {
    font-family: Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    margin: 0;
    padding: 0;
}

/* Header styling */
.header {
    position: running(header);
    text-align: center;
    padding: 10px 0;
    border-bottom: 1px solid #ddd;
}

.title {
    font-weight: bold;
    font-size: 14pt;
}

.date {
    font-style: italic;
    font-size: 10pt;
    color: #555;
}

/* Footer styling */
.footer {
    position: running(footer);
    background-color: #000080; /* Navy blue background */
    color: white;
    padding: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
}

.company {
    margin-left: 10px;
}

.logo {
    text-align: center;
    flex-grow: 1;
}

.logo img {
    height: 1cm;
}

.page-number:after {
    content: counter(page);
}

/* Content styling */
.content-container {
    margin: 20px 0;
}

h1 {
    font-size: 18pt;
    font-weight: bold;
    color: #2c3e50;
    margin-bottom: 0.5em;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.3em;
}

h2 {
    font-size: 14pt;
    font-weight: bold;
    color: #34495e;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}

h3 {
    font-size: 12pt;
    font-weight: bold;
    color: #7f8c8d;
    margin-top: 1.2em;
    margin-bottom: 0.5em;
}

p {
    margin: 0.5em 0;
}

ul {
    margin-left: 1.5em;
    padding-left: 0;
}

li {
    margin-bottom: 0.5em;
}

.participants-table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
}

.participants-table td {
    padding: 5px;
    border: 1px solid #ddd;
}

@page {
    @top-center {
        content: element(header);
    }

    @bottom-center {
        content: element(footer);
    }
}"""

    with open(css_path, 'w') as f:
        f.write(css_content)

    print(f"Created CSS template at {css_path}")

def create_html_template(template_path):
    """Create a default HTML template for meeting summaries"""
    template_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link rel="stylesheet" href="template.css">
</head>
<body>
    <div class="header">
        <div class="title">{{ title }}</div>
        <div class="date">{{ date }}</div>
    </div>

    <div class="footer">
        <div class="company">Service provided by RealPM</div>
        <div class="logo"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAAEGElEQVRoge3abYxcVRnG8d8zL7vdWaXdnd2dvi0iEQS0QBVoFREbCCAVCYpYQZOikWCiJmpCjPELhg+a+EFM/KKJftGYGI0ahcjLCm0BtUCgvIiCQGm3dLvtdnfedmd25vHDdoWy3dm5M3NnN5H7T+7ce855zvPcc++55z73iFKKjeTD2e4KFQ6MD3Jw/BCEmJjk4tYWYoFZ88nnmRhnsI+jRzmeoSwe55LVnZyX+lD8M+zgs2cN5NDkME/ufYQ/7H6a7Qf3nHbaWmkpL+O6td/klrW38IXVV1AVI0eOcv/j/ONlxkJkxrip+xt8Y9WXafTragp5Jvsy3//nT3lu31bGpkdrvr7eq1hV18pPL/sllzVcwo4XufNu9g+STWXCmZQGf3zZ/dy09oa6QobDNPf8/W5+t+uRvOWwrrmdP1zzIK21zWzZxnd+xJ5D0yQkwQn03XAXt627uW6QjmO7+db2m+mcOFCwLDY1reeBq37H8to1vPAyP/wxrxzIJIMk+cy6G7hn0+11g+wYeIFv/vUmeiYPFiXPza0b+fVVD1D2l4f4xVPTZHIyTpHA5KV1H+eX4brSQ57tepp1v7uEP+97sqiIOJUdI7u4ZtvNDO58gttv59+jYXKfYYIL29fxVGurq2NBkOHwGP84/CpPvP5XntvbQXdyb9HzaK5p5rlv/pclP7yJu3bHyGLkApRA39oNfK+j3dWxIEhx0D/Rxb7xA0wHk3THDzASP1JUN+uapZzvfJH73ueZ3bM55BIUjnW38MWu/UyncpjiQ3q7eaIgc7pS5XdWf5pvH+nk733TmGKBiJGp1/nrwRdY3+A+VHeIJkkcYDQYY3+ylwNJP/3JfgYnB5mKJkkm41RXVlNbXUtNVQ0L1FJRUUFddR3VGxJcsrKWCnehukL61vC1zdv4WSCFZRgssgYKQlOWcmzqKEN9PYyO9zM2Oczo5CBHp0YYnR5jeKqfIBMgEiMX2lTGHBqqG2ioWU5TXQPNC5bQtKCFlqZWLmi8kEWLW4gti1FbW8vRRZUSY627ZmqB7G3ihm8/zo+yGWzXXkwrSwzBOD9/FAwD0zQxTQvLsrBtG9u27c+4BLrjNfJAF1t2LF7KuxAnoylRVxBSiIaVDFmKZIT5lQ8lQoMeXNoZOW9IRrSQmBIyJOvkKEWRXMeUIRGlNMhgCpGSQW7MIEFLTkhMCRlE44rIdZQoY1tNJkN6x+r3FZPi2IoKcucNyYoUJZGjFEX6zpGQMo0K2VOsqCupji2JMeiRYm1DQMuSdE+yYqGiuP1ca8NJyKBCGmRQG3RsdwkDKIrTGftxVDGCVkRRfIWcV2RQIaMOKKooXtLIuJYmYkiSwzYX1e7KOu61oiq2IplWsR8zJO+mjFiOa7jXeVvWNlGW5y5cUV6vhdmUNPq4KxHVspiYPImSU0ZTjLZgy9leLVcYCUbpDgaIdPo7h3OCGZrGaAnGz/Y8ckq8AxoK1zJ/mj76AAAAAElFTkSuQmCC" alt="Logo"></div>
        <div class="page-number">Page </div>
    </div>

    <div class="content-container">
        <h1>{{ title }} - {{ date }}</h1>

        <h2>Executive Summary</h2>
        <p>{{ executive_summary }}</p>

        {% if participants_html %}
        <h2>Participants</h2>
        {{ participants_html|safe }}
        {% endif %}

        <h2>Key Discussion Topics and Decisions</h2>
        {{ content|safe }}
    </div>
</body>
</html>"""

    with open(template_path, 'w') as f:
        f.write(template_content)

    print(f"Created HTML template at {template_path}")


def markdown_to_html_content(markdown_text):
    """Convert markdown text to HTML with proper formatting"""
    try:
        import markdown
        # Use the Python markdown library with extra extensions
        return markdown.markdown(markdown_text, extensions=['extra'])
    except ImportError:
        print("Warning: markdown module not found. Using simple conversion.")
        # Simple conversion if markdown module not available
        html = markdown_text

        # First, protect already existing HTML tags
        html = re.sub(r'<(/?[a-zA-Z][^>]*)>', r'<!--TAG-START-->\1<!--TAG-END-->', html)

        # Convert headers
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)

        # Convert bullet points
        html = re.sub(r'^\* (.+)$', r'<ul><li>\1</li></ul>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.+)$', r'<ul><li>\1</li></ul>', html, flags=re.MULTILINE)

        # Convert bold text
        html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)

        # Fix consecutive list items
        html = html.replace('</ul>\n<ul>', '')

        # Convert paragraphs
        paragraphs = html.split('\n\n')
        for i in range(len(paragraphs)):
            if not (paragraphs[i].startswith('<h') or
                    paragraphs[i].startswith('<ul') or
                    paragraphs[i].startswith('<p')):
                paragraphs[i] = f'<p>{paragraphs[i]}</p>'
        html = '\n'.join(paragraphs)

        # Restore protected HTML tags
        html = re.sub(r'<!--TAG-START-->([^>]*)<!--TAG-END-->', r'<\1>', html)

        return html


def generate_pdf_from_html(html_content, output_file):
    """Generate PDF from HTML content using wkhtmltopdf"""
    import tempfile
    import subprocess

    # Extract the output directory
    output_dir = os.path.dirname(os.path.abspath(output_file))

    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp:
        temp.write(html_content.encode('utf-8'))
        temp_name = temp.name

    try:
        # Run wkhtmltopdf with correct paths
        subprocess.run([
            'wkhtmltopdf',
            '--quiet',
            '--enable-local-file-access',  # This is important for accessing local files
            '--enable-external-links',  # This allows external links
            '--footer-center', '[page]/[topage]',  # Add page numbers
            '--footer-font-size', '9',
            '--footer-spacing', '5',
            '--margin-bottom', '20mm',  # Add margin for footer
            temp_name,
            output_file
        ], check=True)
        print(f"Successfully created PDF: {output_file}")
    except Exception as e:
        print(f"Error generating PDF: {e}")
    finally:
        # Clean up the temporary file
        os.unlink(temp_name)


if __name__ == "__main__":
    args = parse_args()

    # Get transcript file from args
    transcript_file = args.transcript_file

    # Create base output filename with same name but different extension in the specified output directory
    base_name = os.path.basename(os.path.splitext(transcript_file)[0])

    # Make sure output directory exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    print(f"Processing transcript: {transcript_file}")

    # Process the transcript
    bullet_summary, participants = get_bullet_summary(transcript_file)
    exec_summary = get_exec_summary(bullet_summary)

    # Output handling based on selected format
    if args.format in ['md', 'html', 'pdf']:
        # Always generate markdown version first
        md_output_file = os.path.join(args.output_dir, f"{base_name}.md")
        exec_summary, bullet_summary_str, participants = get_markdown_document(
            exec_summary,
            bullet_summary,
            md_output_file,
            participants
        )
        print(f"Markdown document saved to {md_output_file}")

        # Convert to HTML if requested
        if args.format in ['html', 'pdf']:
            html_content = markdown_to_html(
                args.title,
                args.date,
                exec_summary,
                bullet_summary_str,
                participants,
                args.output_dir  # Pass output directory parameter
            )

            # Save HTML file
            html_output_file = os.path.join(args.output_dir, f"{base_name}.html")
            with open(html_output_file, 'w') as f:
                f.write(html_content)
            print(f"HTML document saved to {html_output_file}")

            # Generate PDF if requested
            if args.format == 'pdf':
                pdf_output_file = os.path.join(args.output_dir, f"{base_name}.pdf")

                # REPLACE THIS LINE:
                # generate_pdf_from_html(html_content, pdf_output_file)

                # WITH THIS:
                convert_md_to_pdf(
                    md_output_file,
                    pdf_output_file,
                    args.title,
                    args.date,
                    "Meeting Summarization System"  # Or any author you want
                )
                print(f"PDF document saved to {pdf_output_file}")
    else:
        print(f"Unsupported output format: {args.format}")
