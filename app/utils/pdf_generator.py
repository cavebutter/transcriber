import os
import subprocess
import tempfile
import datetime
from flask import current_app


def ensure_template_directory():
    """Ensure the templates directory exists."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(current_dir, "..", "templates", "latex")

    if not os.path.exists(template_dir):
        os.makedirs(template_dir)

    return template_dir


def create_latex_template(template_dir, force_update=True):
    """Create or update the LaTeX template file."""
    template_path = os.path.join(template_dir, "meeting_template.tex")

    # Check if template exists and force_update is False
    if os.path.exists(template_path) and not force_update:
        current_app.logger.info(f"Using existing template at: {template_path}")
        return template_path

    template_content = r"""
\documentclass[11pt,letterpaper]{article}
\usepackage{geometry}
\usepackage{fancyhdr}
\usepackage{xcolor}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{tabulary}
\usepackage{booktabs}
\usepackage{longtable}  % Added for long tables
\usepackage{array}      % Added for better table handling
\usepackage{titlesec}
\usepackage{enumitem} % For custom list formatting

% Define tightlist command used by pandoc
\providecommand{\tightlist}{%
  \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}

% Ensure bullet points use actual bullets, not numbers
\setlist[itemize]{label=\textbullet}

% Define navy blue color
\definecolor{navy}{RGB}{0,0,128}

% Page geometry
\geometry{letterpaper,margin=1in,headheight=20pt}

% Set up fancy headers and footers
\pagestyle{fancy}
\fancyhf{} % Clear all header and footer fields

% Header with title and date
\fancyhead[L]{\textbf{$title$} $if(date)$-- $date$$endif$}

% Footer with navy background
\fancyfoot[L]{%
  \colorbox{navy}{%
    \parbox{\dimexpr\textwidth+2\fboxsep\relax}{%
      \color{white}\hspace{5pt}RealRecap by RealPM\hfill\hspace{5pt}Page \thepage\hspace{5pt}%
    }%
  }%
}

% Apply to first page too
\fancypagestyle{plain}{
  \fancyhf{}
  \fancyhead[C]{\textbf{$title$} $if(date)$-- $date$$endif$}
  \fancyfoot[L]{%
    \colorbox{navy}{%
      \parbox{\dimexpr\textwidth+2\fboxsep\relax}{%
        \color{white}\hspace{5pt}RealRecap by RealPM\hfill\hspace{5pt}Page \thepage\hspace{5pt}%
      }%
    }%
  }%
}

% Format section headings
\titleformat*{\section}{\Large\bfseries\color{navy}}
\titleformat*{\subsection}{\large\bfseries\color{navy}}

% Setup hyperlinks
\hypersetup{
  colorlinks=true,
  linkcolor=blue,
  filecolor=blue,
  urlcolor=blue,
  pdftitle={$title$},
  pdfauthor={$author$}
}

% Document begin
\begin{document}

$if(title)$
\begin{center}
\LARGE{\textbf{$title$}}

$if(date)$
\vspace{0.5cm}
\large{$date$}
$endif$
\end{center}
$endif$

$body$

\end{document}
"""

    with open(template_path, 'w') as f:
        f.write(template_content)

    current_app.logger.info(f"LaTeX template created/updated at: {template_path}")
    return template_path


def convert_md_to_pdf(markdown_file, output_file=None, title=None, date=None, author=None):
    """Convert markdown directly to PDF using pandoc with LaTeX."""
    if output_file is None:
        output_file = os.path.splitext(markdown_file)[0] + ".pdf"

    # Ensure output directory exists
    output_dir = os.path.dirname(os.path.abspath(output_file))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Create template with force_update=True to ensure changes are applied
    template_dir = ensure_template_directory()
    template_file = create_latex_template(template_dir, force_update=True)

    # Format date if not provided
    if not date:
        date = datetime.datetime.now().strftime("%B %d, %Y")

    # Run pandoc with the template
    pandoc_cmd = [
        'pandoc',
        os.path.abspath(markdown_file),
        '--pdf-engine=xelatex',
        f'--template={template_file}',
        '--variable=title:' + (title or "Meeting Summary"),
        '--variable=date:' + date,
    ]

    if author:
        pandoc_cmd.append(f'--variable=author:{author}')

    pandoc_cmd.extend([
        '-o', os.path.abspath(output_file)
    ])

    try:
        subprocess.run(pandoc_cmd, check=True, capture_output=True, text=True)
        current_app.logger.info(f"Successfully created PDF: {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        current_app.logger.error(f"Error generating PDF with pandoc: {e}")
        return None
    except FileNotFoundError:
        current_app.logger.error("pandoc or xelatex not found. Please install pandoc and texlive-xetex")
        return None