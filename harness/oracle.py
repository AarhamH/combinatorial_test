def oracle_should_fail(row, formatter_val, lexer_val, output_val,
                       style_val, formatter_config_val, filter_val, flags_val):
    """
    Return (should_fail: bool, reason: str)
    False means we expect returncode == 0.
    """
    if flags_val in ('list_lexers', 'list_formatters', 'list_styles', 'highlight_info'):
        return False, "info flag: expect success"

    if lexer_val == 'invalid':
        return True, "invalid lexer"

    if formatter_val == 'invalid':
        return True, "invalid formatter"

    if style_val == 'invalid_style':
        return True, "invalid style"

    if output_val == 'restricted':
        return True, "restricted output dir"

    if output_val == 'nonexistent_dir':
        return True, "nonexistent output dir"

    if row.get('file_existence') == 'missing':
        if row.get('input_source') == 'file_path':
            return True, "missing input file"

    if filter_val == 'raise_on_error':
        if row.get('file_content') in ('invalid_syntax', 'binary_data'):
            return True, "raiseonerror + bad content"
        if row.get('input_encoding') == 'invalid':
            return True, "raiseonerror + invalid encoding"

    if formatter_config_val in ('invalid_key', 'malformed_syntax'):
        return True, "bad formatter config"

    return False, "normal execution"