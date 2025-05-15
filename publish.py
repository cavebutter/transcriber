import os
import subprocess
import argparse
import tempfile
from pathlib import Path
import shutil

# Define a path for the permanent CSS file
DEFAULT_CSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.css")

# CSS template for styling the PDF output
CSS_TEMPLATE = """
body {
    font-family: Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    max-width: 8.5in;
    margin: 0 auto;
    padding: 1em;
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

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
}

table, th, td {
    border: 1px solid #ddd;
}

th, td {
    padding: 8px;
    text-align: left;
}

tr:nth-child(even) {
    background-color: #f2f2f2;
}

ul, ol {
    margin-left: 1.5em;
    padding-left: 0;
}

li {
    margin-bottom: 0.5em;
}

strong {
    font-weight: bold;
}

blockquote {
    border-left: 4px solid #eee;
    padding-left: 1em;
    margin-left: 0;
    color: #777;
}
"""


def ensure_css_file_exists():
    """Ensure the CSS template file exists, create if it doesn't."""
    if not os.path.exists(DEFAULT_CSS_PATH):
        with open(DEFAULT_CSS_PATH, 'w') as f:
            f.write(CSS_TEMPLATE)
    return DEFAULT_CSS_PATH


def convert_markdown_to_pdf(markdown_file, output_file=None, title=None, author=None, css_file=None):
    """
    Convert a markdown file to PDF using pandoc with custom styling.

    Args:
        markdown_file (str): Path to the markdown file
        output_file (str, optional): Path for the output PDF file. If None, uses the same name as input with .pdf extension
        title (str, optional): Document title
        author (str, optional): Document author
        css_file (str, optional): Path to CSS file for styling

    Returns:
        str: Path to the generated PDF file
    """
    if not os.path.exists(markdown_file):
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")

    # Create default output filename if not provided
    if output_file is None:
        output_file = os.path.splitext(markdown_file)[0] + '.pdf'
    elif os.path.isdir(output_file):
        # If output is a directory, create a filename based on the input file
        base_name = os.path.basename(os.path.splitext(markdown_file)[0])
        output_file = os.path.join(output_file, f"{base_name}.pdf")

    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Use provided CSS file or ensure the default exists
    if css_file is None:
        css_file = ensure_css_file_exists()

    # Use two-step approach directly as it's more reliable
    try:
        # Create a temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a local copy of the CSS file in the temp directory for accessibility
            local_css = os.path.join(temp_dir, "style.css")
            shutil.copy2(css_file, local_css)

            # Step 1: Convert markdown to HTML with proper title
            html_file = os.path.join(temp_dir, "output.html")
            html_cmd = ['pandoc', os.path.abspath(markdown_file), '-o', html_file, '--standalone']

            # Add metadata
            if title:
                html_cmd.extend(['--metadata', f'title={title}'])
            if author:
                html_cmd.extend(['--metadata', f'author={author}'])

            subprocess.run(html_cmd, check=True)

            # Step 2: Convert HTML to PDF using wkhtmltopdf directly
            pdf_cmd = [
                'wkhtmltopdf',
                '--quiet',
                '--enable-local-file-access',
            ]

            # Add title if provided (wkhtmltopdf format)
            if title:
                pdf_cmd.extend(['--title', title])

            # Add CSS and input/output files
            pdf_cmd.extend([
                f'--user-style-sheet', local_css,
                html_file,
                os.path.abspath(output_file)
            ])

            subprocess.run(pdf_cmd, check=True)
            print(f"Successfully created PDF: {output_file}")
            return output_file

    except subprocess.CalledProcessError as e:
        print(f"Error converting to PDF: {e}")
        return None
    except FileNotFoundError:
        print("Error: pandoc or wkhtmltopdf not found. Please install with:")
        print("  sudo apt-get install pandoc wkhtmltopdf")
        return None


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Convert a markdown document to PDF with styling.")
    parser.add_argument('markdown_file', type=str, help='Path to the markdown file')
    parser.add_argument('--output', '-o', type=str, help='Output PDF file path or directory')
    parser.add_argument('--title', '-t', type=str, help='Document title')
    parser.add_argument('--author', '-a', type=str, help='Document author')
    parser.add_argument('--css', '-c', type=str, help='Path to CSS file for styling')
    return parser.parse_args()


def check_dependencies():
    """Check if pandoc and wkhtmltopdf are installed."""
    try:
        subprocess.run(['pandoc', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(['wkhtmltopdf', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


if __name__ == "__main__":
    args = parse_args()

    if not check_dependencies():
        print("Required dependencies not found. Please install pandoc and wkhtmltopdf:")
        print("  sudo apt-get install pandoc wkhtmltopdf")
        exit(1)

    # If output is a directory, ensure it exists
    if args.output and os.path.dirname(args.output) and not os.path.exists(os.path.dirname(args.output)):
        os.makedirs(os.path.dirname(args.output))

    convert_markdown_to_pdf(
        args.markdown_file,
        args.output,
        args.title,
        args.author,
        args.css
    )