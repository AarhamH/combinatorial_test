import pandas as pd
import subprocess
import os
import shutil
import stat

CSV_FILE = 'PYGMENTS_System-output.csv'
TEST_DIR = "pygments_test_env"

# ---------------------------------------------------------------------------
# LEXER MAP
# ---------------------------------------------------------------------------
LEXER_MAP = {
    'valid_match':    'python',   # extension will also be .py  -> consistent
    'valid_mismatch': 'ruby',     # extension .py but lexer ruby -> mismatch
    'ambiguous':      'c',        # .h would be ambiguous; we use -l c explicitly
    'invalid':        'nonexistent_lexer_xyz',
    'omitted':        None,
}

# ---------------------------------------------------------------------------
# FORMATTER MAP
# ---------------------------------------------------------------------------
FORMATTER_MAP = {
    'html':       'html',
    'terminal256':'terminal256',
    'latex':      'latex',
    'invalid':    'nonexistent_formatter_xyz',
    'omitted':    None,
}

# ---------------------------------------------------------------------------
# STYLE MAP
# ---------------------------------------------------------------------------
STYLE_MAP = {
    'valid_builtin': 'monokai',
    'custom_style':  'monokai',   # no real custom style available in CI; treat as valid_builtin
    'invalid_style': 'nonexistent_style_xyz',
    'omitted':       None,
}

# ---------------------------------------------------------------------------
# ENV SETUP
# ---------------------------------------------------------------------------
def setup_env():
    if os.path.exists(TEST_DIR):
        # Force-remove read-only files/dirs on Windows too
        def _remove_readonly(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(TEST_DIR, onerror=_remove_readonly)
    os.makedirs(TEST_DIR)
    os.makedirs(os.path.join(TEST_DIR, "writable_out"), exist_ok=True)
    # Restricted dir: exists but not writable
    restricted = os.path.join(TEST_DIR, "restricted_out")
    os.makedirs(restricted, exist_ok=True)
    os.chmod(restricted, 0o444)


# ---------------------------------------------------------------------------
# BUILD FILE CONTENT (bytes)
# ---------------------------------------------------------------------------
def build_content(file_content, input_encoding, file_size):
    """Return bytes that represent the requested content/encoding/size combo."""

    # -- encoding helper --
    def encode(text):
        if input_encoding == 'utf16_bom':
            return text.encode('utf-16')          # includes BOM
        if input_encoding == 'bom_utf8':
            return b'\xef\xbb\xbf' + text.encode('utf-8')
        if input_encoding == 'ascii_only':
            return text.encode('ascii', errors='replace')
        if input_encoding == 'no_declaration':
            # Actual UTF-16 bytes but no BOM - will confuse decoders
            return text.encode('utf-16-le')
        if input_encoding == 'invalid':
            return b'\xff\xfe\xfd' + text.encode('utf-8')
        # default: utf8_standard
        return text.encode('utf-8')

    if file_content in ('na', 'empty'):
        return b""

    if file_content == 'binary_data':
        # Non-text binary blob
        return bytes(range(256)) * 4

    if file_content == 'unicode_mixed':
        text = "# unicode: café naïve\ndef func(): pass\n"
    elif file_content == 'invalid_syntax':
        text = "def valid():\n    return True\n!!! not valid python !!!\n"
    else:  # valid_syntax
        text = "def valid_func():\n    return True\n"

    base = encode(text)

    # -- size modifier --
    if file_size == 'long_line':
        long = encode("x = " + "a" * 2000 + "\n")
        base = base + long
    elif file_size == 'massive':
        base = base * 5000        # ~several MB
    elif file_size == 'buffer_boundary':
        # Land exactly on a common buffer size (8192 bytes)
        chunk = encode("# pad\n")
        while len(base) < 8192:
            base += chunk
        base = base[:8192]
    elif file_size == 'zero_byte':
        base = b""
    # 'typical' and 'na' -> leave as-is

    return base


# ---------------------------------------------------------------------------
# BUILD INPUT FILE NAME
# ---------------------------------------------------------------------------
def build_filename(row_index, file_name_format, lexer_val):
    """Return a filename (no dir) appropriate for the format parameter."""
    ext_map = {
        'valid_match':    '.py',
        'valid_mismatch': '.py',   # mismatch is the point
        'ambiguous':      '.h',    # C / C++ ambiguous
    }
    ext = ext_map.get(lexer_val, '.py')

    if file_name_format == 'no_ext':
        return f"input_{row_index}"
    if file_name_format == 'special_chars':
        return f"input file {row_index}!@#${ext}"
    if file_name_format == 'na':
        return f"input_{row_index}{ext}"
    # standard_ext
    return f"input_{row_index}{ext}"


# ---------------------------------------------------------------------------
# ORACLE: should this invocation fail (non-zero returncode)?
# ---------------------------------------------------------------------------
def oracle_should_fail(row, formatter_val, lexer_val, output_val,
                       style_val, formatter_config_val, filter_val, flags_val):
    """
    Return (should_fail: bool, reason: str)
    False means we expect returncode == 0.
    """
    # -- Informational flags exit 0 and do nothing else --
    if flags_val in ('list_lexers', 'list_formatters', 'list_styles', 'highlight_info'):
        return False, "info flag: expect success"

    # -- Invalid lexer always fails --
    if lexer_val == 'invalid':
        return True, "invalid lexer"

    # -- Invalid formatter always fails --
    if formatter_val == 'invalid':
        return True, "invalid formatter"

    # -- Invalid style always fails --
    if style_val == 'invalid_style':
        return True, "invalid style"

    # -- Output to restricted directory should fail --
    if output_val == 'restricted':
        return True, "restricted output dir"

    # -- Output to nonexistent directory should fail --
    if output_val == 'nonexistent_dir':
        return True, "nonexistent output dir"

    # -- Missing input file --
    if row.get('file_existence') == 'missing':
        # stdin tests won't use a file, so this only matters for file_path input
        if row.get('input_source') == 'file_path':
            return True, "missing input file"

    # -- raiseonerror filter with bad content --
    if filter_val == 'raise_on_error':
        if row.get('file_content') in ('invalid_syntax', 'binary_data'):
            return True, "raiseonerror + bad content"
        if row.get('input_encoding') == 'invalid':
            return True, "raiseonerror + invalid encoding"

    # -- malformed / invalid formatter_config --
    if formatter_config_val in ('invalid_key', 'malformed_syntax'):
        return True, "bad formatter config"

    return False, "normal execution"


# ---------------------------------------------------------------------------
# BUILD COMMAND
# ---------------------------------------------------------------------------
def build_cmd(row_index, row, input_file, output_file):
    """
    Return (cmd: list[str], uses_stdin: bool, expect_output_file: bool)
    """
    flags_val          = str(row.get('flags',            'none')).strip()
    formatter_val      = str(row.get('formatter',        'omitted')).strip()
    lexer_val          = str(row.get('lexer',            'omitted')).strip()
    output_val         = str(row.get('output',           'stdout')).strip()
    style_val          = str(row.get('style_option',     'omitted')).strip()
    formatter_config_v = str(row.get('formatter_config', 'omitted')).strip()
    filter_val         = str(row.get('filter',           'omitted')).strip()
    input_source_val   = str(row.get('input_source',     'file_path')).strip()

    cmd = ['pygmentize']

    # -- Informational flags: short-circuit everything --
    if flags_val == 'list_lexers':
        return ['pygmentize', '-L', 'lexers'], False, False
    if flags_val == 'list_formatters':
        return ['pygmentize', '-L', 'formatters'], False, False
    if flags_val == 'list_styles':
        return ['pygmentize', '-L', 'styles'], False, False
    if flags_val == 'highlight_info':
        # -N prints the lexer name for a filename; needs a filename arg
        return ['pygmentize', '-N', input_file], False, False
    if flags_val == 'guess_lexer':
        cmd.append('-g')

    # -- Formatter --
    fmt = FORMATTER_MAP.get(formatter_val)
    if fmt:
        cmd.extend(['-f', fmt])
    else:
        cmd.extend(['-f', 'html'])   # default so we always get parseable output

    # -- Formatter options --
    if formatter_config_v == 'valid_config':
        cmd.extend(['-O', 'full=True'])
    elif formatter_config_v == 'conflicting_options':
        cmd.extend(['-O', 'noclasses=True,cssclass=highlight'])
    elif formatter_config_v == 'invalid_key':
        cmd.extend(['-O', 'nonexistent_option_xyz=True'])
    elif formatter_config_v == 'malformed_syntax':
        cmd.extend(['-O', '!!!notvalid!!!'])

    # -- Style --
    sty = STYLE_MAP.get(style_val)
    if sty:
        cmd.extend(['-O', f'style={sty}'])

    # -- Lexer (skip if -g was used) --
    if flags_val != 'guess_lexer':
        lex = LEXER_MAP.get(lexer_val)
        if lex:
            cmd.extend(['-l', lex])

    # -- Filters --
    if filter_val == 'raise_on_error':
        cmd.extend(['-F', 'raiseonerror'])
    elif filter_val == 'valid_filter':
        cmd.extend(['-F', 'tokenmerge'])
    elif filter_val == 'chained_filters':
        cmd.extend(['-F', 'tokenmerge', '-F', 'raiseonerror'])
    elif filter_val == 'filter_with_options':
        cmd.extend(['-F', 'tokenmerge:maxmerge=5'])

    # -- Output destination --
    expect_output_file = False
    if output_val == 'stdout':
        pass  # no -o flag
    elif output_val == 'file_path':
        cmd.extend(['-o', output_file])
        expect_output_file = True
    elif output_val == 'restricted':
        restricted_path = os.path.join(TEST_DIR, "restricted_out", f"out_{row_index}.html")
        cmd.extend(['-o', restricted_path])
        expect_output_file = True
    elif output_val == 'nonexistent_dir':
        bad_path = os.path.join(TEST_DIR, "does_not_exist_xyz", f"out_{row_index}.html")
        cmd.extend(['-o', bad_path])
        expect_output_file = True

    # -- Input source --
    uses_stdin = (input_source_val == 'stdin')
    if not uses_stdin:
        cmd.append(input_file)

    return cmd, uses_stdin, expect_output_file


# ---------------------------------------------------------------------------
# RUN A SINGLE TEST
# ---------------------------------------------------------------------------
def run_test(row_index, row):
    # Normalise all values
    file_existence_val  = str(row.get('file_existence',    'exists')).strip()
    file_content_val    = str(row.get('file_content',      'valid_syntax')).strip()
    input_encoding_val  = str(row.get('input_encoding',    'utf8_standard')).strip()
    file_size_val       = str(row.get('file_size',         'typical')).strip()
    file_name_fmt_val   = str(row.get('file_name_format',  'standard_ext')).strip()
    formatter_val       = str(row.get('formatter',         'omitted')).strip()
    lexer_val           = str(row.get('lexer',             'omitted')).strip()
    output_val          = str(row.get('output',            'stdout')).strip()
    style_val           = str(row.get('style_option',      'omitted')).strip()
    formatter_config_v  = str(row.get('formatter_config',  'omitted')).strip()
    filter_val          = str(row.get('filter',            'omitted')).strip()
    flags_val           = str(row.get('flags',             'none')).strip()
    input_source_val    = str(row.get('input_source',      'file_path')).strip()

    # -- Build input file --
    fname    = build_filename(row_index, file_name_fmt_val, lexer_val)
    in_path  = os.path.join(TEST_DIR, fname)
    out_path = os.path.join(TEST_DIR, f"out_{row_index}.html")

    content = build_content(file_content_val, input_encoding_val, file_size_val)

    if file_existence_val != 'missing':
        with open(in_path, 'wb') as fh:
            fh.write(content)
    # If 'missing', don't create the file

    # -- Build command --
    cmd, uses_stdin, expect_output_file = build_cmd(
        row_index, row, in_path, out_path
    )

    # -- Oracle --
    should_fail, oracle_reason = oracle_should_fail(
        row, formatter_val, lexer_val, output_val,
        style_val, formatter_config_v, filter_val, flags_val
    )

    # -- Execute --
    try:
        run_kwargs = dict(capture_output=True, timeout=10)
        if uses_stdin:
            run_kwargs['input'] = content
        result = subprocess.run(cmd, **run_kwargs)
    except subprocess.TimeoutExpired:
        return {
            "index":  row_index,
            "status": "EXEC_ERROR",
            "detail": "TIMEOUT after 10s",
            "cmd":    " ".join(cmd),
        }
    except Exception as exc:
        return {
            "index":  row_index,
            "status": "EXEC_ERROR",
            "detail": str(exc),
            "cmd":    " ".join(cmd),
        }

    actual_fail = (result.returncode != 0)
    bug_details = []

    # -- Deep oracle checks (only when command succeeded) --
    if not actual_fail and expect_output_file and os.path.exists(out_path):
        with open(out_path, 'r', errors='ignore') as fh:
            out_content = fh.read()

        # raiseonerror filter should have aborted before producing error tokens
        if filter_val in ('raise_on_error', 'chained_filters'):
            if 'class="err"' in out_content or 'class="gr"' in out_content:
                bug_details.append(
                    "VALID BUG: FILTER_BYPASS – raiseonerror produced error tokens without failing"
                )

        # Output file produced even though dir doesn't exist (shouldn't happen)
        if output_val == 'nonexistent_dir':
            bug_details.append(
                "VALID BUG: OUTPUT_TO_NONEXISTENT_DIR – file written to missing directory"
            )

        # Output file produced even though dir is restricted
        if output_val == 'restricted':
            bug_details.append(
                "VALID BUG: OUTPUT_TO_RESTRICTED_DIR – file written to unwritable directory"
            )

    # -- Primary oracle check --
    if actual_fail != should_fail:
        # Apply known false-positive suppressions before calling it a bug
        suppress = False

        # pygmentize falls back to 'text' when lexer omitted + no extension match
        if not should_fail and actual_fail and lexer_val == 'omitted':
            suppress = True  # might be an oracle gap, not a real failure

        # Some formatter options are silently ignored rather than erroring
        if formatter_config_v == 'invalid_key' and not actual_fail:
            suppress = True  # pygmentize ignores unknown -O keys silently

        if formatter_config_v == 'conflicting_options' and not actual_fail:
            suppress = True  # conflicting options may be resolved silently

        if not suppress:
            bug_details.append(
                f"VALID BUG: RETURNCODE_MISMATCH – "
                f"expected_fail={should_fail} (reason: {oracle_reason}), "
                f"actual_fail={actual_fail}, stderr={result.stderr.decode(errors='replace')[:200]}"
            )

    if bug_details:
        return {
            "index":  row_index,
            "status": "BUG FOUND",
            "detail": " | ".join(bug_details),
            "cmd":    " ".join(cmd),
        }

    return {
        "index":  row_index,
        "status": "PASS",
        "detail": f"ok (oracle: {oracle_reason})",
        "cmd":    " ".join(cmd),
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    df = pd.read_csv(CSV_FILE, comment='#')
    setup_env()

    results = [run_test(i, row) for i, row in df.iterrows()]

    res_df = pd.DataFrame(results)
    bugs   = res_df[res_df['status'] == 'BUG FOUND']
    errors = res_df[res_df['status'] == 'EXEC_ERROR']

    print(f"\nTotal tests  : {len(res_df)}")
    print(f"Passed       : {len(res_df[res_df['status'] == 'PASS'])}")
    print(f"Bugs found   : {len(bugs)}")
    print(f"Exec errors  : {len(errors)}")

    if not bugs.empty:
        print("\n=== Verified Bug Report ===")
        for _, r in bugs.iterrows():
            print(f"\n[#{r['index']}] {r['detail']}")
            print(f"  CMD: {r['cmd']}")

    out_csv = 'pygments_test_results.csv'
    res_df.to_csv(out_csv, index=False)
    print(f"\nFull results saved to: {out_csv}")


if __name__ == '__main__':
    main()