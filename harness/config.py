import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

CSV_FILE = os.path.join(PROJECT_ROOT, "PYGMENTS_System-output.csv")
TEST_DIR = os.path.join(PROJECT_ROOT, "pygments_test_env")

LEXER_MAP = {
    'valid_match':    'python',
    'valid_mismatch': 'ruby',
    'ambiguous':      'c',
    'invalid':        'nonexistent_lexer_xyz',
    'omitted':        None,
}

FORMATTER_MAP = {
    'html':        'html',
    'terminal256': 'terminal256',
    'latex':       'latex',
    'invalid':     'nonexistent_formatter_xyz',
    'omitted':     None,
}

STYLE_MAP = {
    'valid_builtin': 'monokai',
    'custom_style':  'monokai',
    'invalid_style': 'nonexistent_style_xyz',
    'omitted':       None,
}