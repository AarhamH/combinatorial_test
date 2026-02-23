import os

from .config import TEST_DIR, LEXER_MAP, FORMATTER_MAP, STYLE_MAP


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

    if flags_val == 'list_lexers':
        return ['pygmentize', '-L', 'lexers'], False, False
    if flags_val == 'list_formatters':
        return ['pygmentize', '-L', 'formatters'], False, False
    if flags_val == 'list_styles':
        return ['pygmentize', '-L', 'styles'], False, False
    if flags_val == 'highlight_info':
        return ['pygmentize', '-N', input_file], False, False
    if flags_val == 'guess_lexer':
        cmd.append('-g')

    fmt = FORMATTER_MAP.get(formatter_val)
    if fmt:
        cmd.extend(['-f', fmt])
    else:
        cmd.extend(['-f', 'html']) 

    if formatter_config_v == 'valid_config':
        cmd.extend(['-O', 'full=True'])
    elif formatter_config_v == 'conflicting_options':
        cmd.extend(['-O', 'noclasses=True,cssclass=highlight'])
    elif formatter_config_v == 'invalid_key':
        cmd.extend(['-O', 'nonexistent_option_xyz=True'])
    elif formatter_config_v == 'malformed_syntax':
        cmd.extend(['-O', '!!!notvalid!!!'])

    sty = STYLE_MAP.get(style_val)
    if sty:
        cmd.extend(['-O', f'style={sty}'])

    if flags_val != 'guess_lexer':
        lex = LEXER_MAP.get(lexer_val)
        if lex:
            cmd.extend(['-l', lex])

    if filter_val == 'raise_on_error':
        cmd.extend(['-F', 'raiseonerror'])
    elif filter_val == 'valid_filter':
        cmd.extend(['-F', 'tokenmerge'])
    elif filter_val == 'chained_filters':
        cmd.extend(['-F', 'tokenmerge', '-F', 'raiseonerror'])
    elif filter_val == 'filter_with_options':
        cmd.extend(['-F', 'tokenmerge:maxmerge=5'])

    expect_output_file = False
    if output_val == 'stdout':
        pass 
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

    uses_stdin = (input_source_val == 'stdin')
    if not uses_stdin:
        cmd.append(input_file)

    return cmd, uses_stdin, expect_output_file