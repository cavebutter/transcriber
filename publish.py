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
    """Convert a markdown file to PDF using pandoc and wkhtmltopdf with styling."""
    if css_file is None:
        css_file = ensure_css_file_exists()

    if output_file is None:
        # Default output file has the same name but .pdf extension
        output_file = os.path.splitext(markdown_file)[0] + ".pdf"

    try:
        # Create a temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a local copy of the CSS file in the temp directory for accessibility
            local_css = os.path.join(temp_dir, "style.css")
            shutil.copy2(css_file, local_css)

            # Create header and footer HTML files
            header_file = os.path.join(temp_dir, "header.html")
            footer_file = os.path.join(temp_dir, "footer.html")

            # Extract meeting date from title if possible
            meeting_date = ""
            if title and "standup" in title.lower():
                meeting_date = "Meeting Date: " + title.split("Standup")[1].strip()

            # Create header HTML file
            with open(header_file, 'w') as f:
                f.write(f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
        .header {{
            text-align: center;
            padding: 10px 0;
            border-bottom: 1px solid #ddd;
        }}
        .title {{
            font-weight: bold;
            font-size: 14pt;
        }}
        .date {{
            font-style: italic;
            font-size: 10pt;
            color: #555;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">{title or "Meeting Summary"}</div>
        <div class="date">{meeting_date}</div>
    </div>
</body>
</html>''')

            # Create footer HTML file
            with open(footer_file, 'w') as f:
                f.write('''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            margin: 0;
            padding: 0;
        }
        .footer {
            background-color: #000080;
            color: white;
            padding: 10px;
            height: 1.2cm;
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
        .page-number {
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="footer">
        <div class="company">Service provided by RealPM</div>
        <div class="logo"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAAEGElEQVRoge3abYxcVRnG8d8zL7vdWaXdnd2dvi0iEQS0QBVoFREbCCAVCYpYQZOikWCiJmpCjPELhg+a+EFM/KKJftGYGI0ahcjLCm0BtUCgvIiCQGm3dLvtdnfedmd25vHDdoWy3dm5M3NnN5H7T+7ce855zvPcc++55z73iFKKjeTD2e4KFQ6MD3Jw/BCEmJjk4tYWYoFZ88nnmRhnsI+jRzmeoSwe55LVnZyX+lD8M+zgs2cN5NDkME/ufYQ/7H6a7Qf3nHbaWmkpL+O6td/klrW38IXVV1AVI0eOcv/j/ONlxkJkxrip+xt8Y9WXafTragp5Jvsy3//nT3lu31bGpkdrvr7eq1hV18pPL/sllzVcwo4XufNu9g+STWXCmZQGf3zZ/dy09oa6QobDNPf8/W5+t+uRvOWwrrmdP1zzIK21zWzZxnd+xJ5D0yQkwQn03XAXt627uW6QjmO7+db2m+mcOFCwLDY1reeBq37H8to1vPAyP/wxrxzIJIMk+cy6G7hn0+11g+wYeIFv/vUmeiYPFiXPza0b+fVVD1D2l4f4xVPTZHIyTpHA5KV1H+eX4brSQ57tepp1v7uEP+97sqiIOJUdI7u4ZtvNDO58gttv59+jYXKfYYIL29fxVGurq2NBkOHwGP84/CpPvP5XntvbQXdyb9HzaK5p5rlv/pclP7yJu3bHyGLkApRA39oNfK+j3dWxIEhx0D/Rxb7xA0wHk3THDzASP1JUN+uapZzvfJH73ueZ3bM55BIUjnW38MWu/UyncpjiQ3q7eaIgc7pS5XdWf5pvH+nk733TmGKBiJGp1/nrwRdY3+A+VHeIJkkcYDQYY3+ylwNJP/3JfgYnB5mKJkkm41RXVlNbXUtNVQ0L1FJRUUFddR3VGxJcsrKWCnehukL61vC1zdv4WSCFZRgssgYKQlOWcmzqKEN9PYyO9zM2Oczo5CBHp0YYnR5jeKqfIBMgEiMX2lTGHBqqG2ioWU5TXQPNC5bQtKCFlqZWLmi8kEWLW4gti1FbW8vRRZUSY627ZmqB7G3ihm8/zo+yGWzXXkwrSwzBOD9/FAwD0zQxTQvLsrBtG9u27c+4BLrjNfJAF1t2LF7KuxAnoylRVxBSiIaVDFmKZIT5lQ8lQoMeXNoZOW9IRrSQmBIyJOvkKEWRXMeUIRGlNMhgCpGSQW7MIEFLTkhMCRlE44rIdZQoY1tNJkN6x+r3FZPi2IoKcucNyYoUJZGjFEX6zpGQMo0K2VOsqCupji2JMeiRYm1DQMuSdE+yYqGiuP1ca8NJyKBCGmRQG3RsdwkDKIrTGftxVDGCVkRRfIWcV2RQIaMOKKooXtLIuJYmYkiSwzYX1e7KOu61oiq2IplWsR8zJO+mjFiOa7jXeVvWNlGW5y5cUV6vhdmUNPq4KxHVspiYPImSU0ZTjLZgy9leLVcYCUbpDgaIdPo7h3OCGZrGaAnGz/Y8ckq8AxoK1zJ/mj76AAAAAElFTkSuQmCC" alt="Logo"></div>
        <div class="page-number">Page <span class="pageNumber"></span></div>
    </div>
    <script>
        // Insert page number
        var vars = {};
        var x = document.location.search.substring(1).split('&');
        for (var i in x) {
            var z = x[i].split('=', 2);
            vars[z[0]] = unescape(z[1]);
        }
        document.getElementsByClassName('pageNumber')[0].innerHTML = vars['page'];
    </script>
</body>
</html>''')

            # Step 1: Convert markdown to HTML
            html_file = os.path.join(temp_dir, "output.html")
            html_cmd = ['pandoc', os.path.abspath(markdown_file), '-o', html_file, '--standalone']

            # Add metadata
            if title:
                html_cmd.extend(['--metadata', f'title={title}'])
            if author:
                html_cmd.extend(['--metadata', f'author={author}'])

            subprocess.run(html_cmd, check=True)

            # Step 2: Convert HTML to PDF using wkhtmltopdf with proper header and footer
            pdf_cmd = [
                'wkhtmltopdf',
                '--quiet',
                '--enable-local-file-access',
            ]

            # Add title if provided (wkhtmltopdf format)
            if title:
                pdf_cmd.extend(['--title', title])

            # Add header/footer options - using external HTML files
            pdf_cmd.extend([
                '--header-html', header_file,
                '--footer-html', footer_file,
                '--margin-top', '25mm',
                '--margin-bottom', '25mm',
                '--margin-left', '15mm',
                '--margin-right', '15mm',
                '--header-spacing', '5',
                '--footer-spacing', '5',
            ])

            # Add CSS and input/output files
            pdf_cmd.extend([
                f'--user-style-sheet', local_css,
                html_file,
                os.path.abspath(output_file)
            ])

            subprocess.run(pdf_cmd, check=True)
            print(f"Successfully created PDF: {output_file}")
            return output_file

    except Exception as e:
        print(f"Error: {e}")
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