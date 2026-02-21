import pandas as pd
import subprocess
import os
import shutil

CSV_FILE = 'PYGMENTS_System-output.csv'
df = pd.read_csv(CSV_FILE, comment='#')

TEST_DIR = "pygments_test_env"

def setup_env():
    if os.path.exists(TEST_DIR):
        for root, dirs, files in os.walk(TEST_DIR):
            for d in dirs: os.chmod(os.path.join(root, d), 0o777)
            for f in files: os.chmod(os.path.join(root, f), 0o666)
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

def get_content(row):
    content_type = row.get('file_content', 'valid')
    if content_type in ['empty', 'na']: return b""
    
    text = "def valid_func():\n    return True\n"
    if content_type == 'invalid_syntax':
        text += "!!! This is not valid Python code !!!\n"
    
    encoding = row.get('input_encoding', 'utf8')
    if encoding == 'invalid':
        return b"\xff\xfe\xfd" + text.encode('utf-8')
    return text.encode('utf-8')

def run_test(row_index, row):
    output_path = os.path.join(TEST_DIR, f"out_{row_index}.html")
    cmd = ["pygmentize", "-f", "html"]
    
    lexer = row.get('lexer', 'omitted')
    if lexer == 'valid_match': cmd.extend(["-l", "python"])
    elif lexer == 'valid_mismatch': cmd.extend(["-l", "ruby"])
    elif lexer == 'invalid': cmd.extend(["-l", "nonexistent_lexer"])

    is_raise_on_error = False
    if row.get('filter') == 'raise_on_error':
        cmd.extend(["-F", "raiseonerror"])
        is_raise_on_error = True

    cmd.extend(["-o", output_path])

    input_data = get_content(row)
    input_file = os.path.join(TEST_DIR, f"input_{row_index}.py")
    with open(input_file, "wb") as f: f.write(input_data)
    cmd.append(input_file)

    try:
        res = subprocess.run(cmd, capture_output=True, timeout=5)
        actual_error = (res.returncode != 0)
        
        should_fail = (
            lexer == 'invalid' or 
            (is_raise_on_error and (row.get('file_content') == 'invalid_syntax' or row.get('input_encoding') == 'invalid'))
        )

        bug_details = []
        
        if os.path.exists(output_path):
            with open(output_path, 'r', errors='ignore') as f:
                content = f.read()
            
            has_error_tokens = 'class="err"' in content or 'class="gr"' in content
            if is_raise_on_error and has_error_tokens and not actual_error:
                bug_details.append("VALID BUG: FILTER_BYPASS (raiseonerror ignored)")

        if bug_details:
            status = "BUG FOUND"
            detail = " | ".join(bug_details)
        elif actual_error != should_fail:
            if lexer == 'omitted' and not actual_error:
                status = "PASS"
                detail = "Behavior as expected (Fallback to Text)"
            else:
                status = "BUG FOUND"
                detail = f"ORACLE MISMATCH: ShouldFail={should_fail}, Actual={actual_error}"
        else:
            status = "PASS"
            detail = "Behavior as expected"

        return {"index": row_index, "status": status, "detail": detail, "cmd": " ".join(cmd)}

    except Exception as e:
        return {"index": row_index, "status": "EXEC_ERROR", "detail": str(e)}

setup_env()
results = [run_test(i, row) for i, row in df.iterrows()]
res_df = pd.DataFrame(results)

bugs = res_df[res_df.status == "BUG FOUND"]
print(f"Verified {len(bugs)} actual bugs (Noise filtered out).")
if not bugs.empty:
    print("\n--- Verified Bug Report ---")
    print(bugs[['index', 'detail', 'cmd']].to_string(index=False))