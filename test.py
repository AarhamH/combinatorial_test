import pandas as pd
import subprocess
import os
import shutil
import stat

CSV_FILE = 'PYGMENTS_System-output_updated.csv'
df = pd.read_csv(CSV_FILE, comment='#')

TEST_DIR = "pygments_test_env"
RESTRICTED_DIR = os.path.join(TEST_DIR, "restricted_dir")
OUTPUT_FILE = os.path.join(TEST_DIR, "output.html")

def setup_env():
    """Initializes a clean test environment."""
    if os.path.exists(TEST_DIR):
        for root, dirs, files in os.walk(TEST_DIR):
            for d in dirs: os.chmod(os.path.join(root, d), 0o777)
            for f in files: os.chmod(os.path.join(root, f), 0o666)
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)
    os.makedirs(RESTRICTED_DIR)

def get_content(row):
    """Generates file content based on size, shape, and syntax requirements."""
    content_type = row['file_content']
    size_shape = row['file_size_shape']
    
    if content_type in ['empty', 'na']:
        return b""
    
    base_text = "print('Pygments Test')\n"
    if content_type == 'invalid_syntax':
        base_text = "print('Unclosed string\n"
        
    if size_shape == 'long_line':
        text = "a = '" + "x" * 10000 + "'\n" + base_text
    elif size_shape == 'massive_file':
        text = (base_text * 5000) 
    else:
        text = base_text
        
    encoding = row['input_encoding']
    if encoding == 'utf8_standard_text':
        return text.encode('utf-8')
    elif encoding == 'utf16_byte_order_mark':
        return text.encode('utf-16')
    elif encoding == 'invalid_bytes':
        return b"\xff\xfe\xfd\x00\x01" + text.encode('utf-8')
    return text.encode('utf-8')

def run_test(row_index, row):
    cmd = ["pygmentize"]
    
    if row['lexer'] == 'valid_match': cmd.extend(["-l", "python"])
    elif row['lexer'] == 'valid_mismatch': cmd.extend(["-l", "ruby"])
    elif row['lexer'] == 'invalid': cmd.extend(["-l", "fake_lexer"])
    
    if row['formatter'] == 'valid': cmd.extend(["-f", "html"])
    elif row['formatter'] == 'invalid': cmd.extend(["-f", "fake_formatter"])
        
    if row['filters'] == 'valid_filter': cmd.extend(["-F", "whitespace"])
    elif row['filters'] == 'raise_on_error': cmd.extend(["-F", "raiseonerror"])
        
    if row['style_option'] == 'valid_builtin': cmd.extend(["-O", "style=monokai"])
    elif row['style_option'] == 'invalid': cmd.extend(["-O", "style=fake_style"])

    if row['output'] == 'file_path':
        cmd.extend(["-o", os.path.join(TEST_DIR, "valid_out.html")])
    elif row['output'] == 'restricted':
        os.chmod(RESTRICTED_DIR, 0o444) # Lock directory
        cmd.extend(["-o", os.path.join(RESTRICTED_DIR, "no_access.html")])
    
    input_content = get_content(row)
    input_method = row['input']
    file_path = None
    
    if input_method == 'file_path':
        if row['file_existence'] == 'exists':
            fname = "test.py" if row['file_name_format'] != 'no_extension' else "testfile"
            if row['file_name_format'] == 'special_chars': fname = "test !@#$.py"
            file_path = os.path.join(TEST_DIR, fname)
            with open(file_path, "wb") as f: f.write(input_content)
            cmd.append(file_path)
        elif row['file_existence'] == 'missing':
            cmd.append(os.path.join(TEST_DIR, "missing.py"))

    expect_error = any([
        row['file_existence'] == 'missing' and input_method == 'file_path',
        row['lexer'] == 'invalid',
        row['formatter'] == 'invalid',
        row['style_option'] == 'invalid',
        row['output'] == 'restricted',
        (row['filters'] == 'raise_on_error' and row['file_content'] == 'invalid_syntax'),
        (row['input_encoding'] == 'invalid_bytes' and row['lexer'] != 'omitted')
    ])

    try:
        if input_method == 'stdin':
            result = subprocess.run(cmd, input=input_content, capture_output=True, timeout=5)
        else:
            result = subprocess.run(cmd, capture_output=True, timeout=5)
        
        os.chmod(RESTRICTED_DIR, 0o777)
        actual_error = (result.returncode != 0)
        
        if actual_error != expect_error:
            return {"index": row_index, "status": "BUG FOUND", "cmd": " ".join(cmd), 
                    "detail": f"ExpectError: {expect_error}, Actual: {actual_error}. Code: {result.returncode}"}
        return {"index": row_index, "status": "PASS", "cmd": " ".join(cmd), "detail": "Match"}
    except Exception as e:
        os.chmod(RESTRICTED_DIR, 0o777)
        return {"index": row_index, "status": "EXEC_ERROR", "cmd": " ".join(cmd), "detail": str(e)}

results = []
setup_env()
for i, row in df.iterrows():
    results.append(run_test(i, row))

res_df = pd.DataFrame(results)
print(f"Total Tests: {len(res_df)} | Passed: {len(res_df[res_df.status == 'PASS'])} | Bugs Found: {len(res_df[res_df.status == 'BUG FOUND'])}")
print("\n--- Detailed Bug Report ---")
print(res_df[res_df.status == 'BUG FOUND'][['index', 'cmd', 'detail']].to_string(index=False))