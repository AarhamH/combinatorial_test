def build_content(file_content, input_encoding, file_size):
    """Return bytes that represent the requested content/encoding/size combo."""

    def encode(text):
        if input_encoding == 'utf16_bom':
            return text.encode('utf-16')
        if input_encoding == 'bom_utf8':
            return b'\xef\xbb\xbf' + text.encode('utf-8')
        if input_encoding == 'ascii_only':
            return text.encode('ascii', errors='replace')
        if input_encoding == 'no_declaration':
            return text.encode('utf-16-le')
        if input_encoding == 'invalid':
            return b'\xff\xfe\xfd' + text.encode('utf-8')
        return text.encode('utf-8')

    if file_content in ('na', 'empty'):
        return b""

    if file_content == 'binary_data':
        return bytes(range(256)) * 4

    if file_content == 'unicode_mixed':
        text = "# unicode: café naïve\ndef func(): pass\n"
    elif file_content == 'invalid_syntax':
        text = "def valid():\n    return True\n!!! not valid python !!!\n"
    else:
        text = "def valid_func():\n    return True\n"

    base = encode(text)

    if file_size == 'long_line':
        long = encode("x = " + "a" * 2000 + "\n")
        base = base + long
    elif file_size == 'massive':
        base = base * 5000
    elif file_size == 'buffer_boundary':
        chunk = encode("# pad\n")
        while len(base) < 8192:
            base += chunk
        base = base[:8192]
    elif file_size == 'zero_byte':
        base = b""

    return base


def build_filename(row_index, file_name_format, lexer_val):
    """Return a filename (no dir) appropriate for the format parameter."""
    ext_map = {
        'valid_match':    '.py',
        'valid_mismatch': '.py',
        'ambiguous':      '.h',
    }
    ext = ext_map.get(lexer_val, '.py')

    if file_name_format == 'no_ext':
        return f"input_{row_index}"
    if file_name_format == 'special_chars':
        return f"input file {row_index}!@#${ext}"
    if file_name_format == 'na':
        return f"input_{row_index}{ext}"
    return f"input_{row_index}{ext}"