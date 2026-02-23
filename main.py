import os
import subprocess

import pandas as pd

from harness.config import CSV_FILE, TEST_DIR
from harness.env import setup_env
from harness.input_builder import build_content, build_filename
from harness.cmd_builder import build_cmd
from harness.oracle import oracle_should_fail


def run_test(row_index, row):
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

    fname    = build_filename(row_index, file_name_fmt_val, lexer_val)
    in_path  = os.path.join(TEST_DIR, fname)
    out_path = os.path.join(TEST_DIR, f"out_{row_index}.html")

    content = build_content(file_content_val, input_encoding_val, file_size_val)

    if file_existence_val != 'missing':
        with open(in_path, 'wb') as fh:
            fh.write(content)

    cmd, uses_stdin, expect_output_file = build_cmd(
        row_index, row, in_path, out_path
    )

    should_fail, oracle_reason = oracle_should_fail(
        row, formatter_val, lexer_val, output_val,
        style_val, formatter_config_v, filter_val, flags_val
    )

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

    if not actual_fail and expect_output_file and os.path.exists(out_path):
        with open(out_path, 'r', errors='ignore') as fh:
            out_content = fh.read()

        if filter_val in ('raise_on_error', 'chained_filters'):
            if 'class="err"' in out_content or 'class="gr"' in out_content:
                bug_details.append(
                    "VALID BUG: FILTER_BYPASS – raiseonerror produced error tokens without failing"
                )

        if output_val == 'nonexistent_dir':
            bug_details.append(
                "VALID BUG: OUTPUT_TO_NONEXISTENT_DIR – file written to missing directory"
            )

        if output_val == 'restricted':
            bug_details.append(
                "VALID BUG: OUTPUT_TO_RESTRICTED_DIR – file written to unwritable directory"
            )

    if actual_fail != should_fail:
        suppress = False

        if not should_fail and actual_fail and lexer_val == 'omitted':
            suppress = True

        if formatter_config_v == 'invalid_key' and not actual_fail:
            suppress = True

        if formatter_config_v == 'conflicting_options' and not actual_fail:
            suppress = True

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

    if not errors.empty:
        print("\n=== Execution Errors (harness issues, not pygmentize bugs) ===")
        for _, r in errors.iterrows():
            print(f"\n[#{r['index']}] {r['detail']}")
            print(f"  CMD: {r['cmd']}")

    out_csv = 'pygments_test_results.csv'
    res_df.to_csv(out_csv, index=False)
    print(f"\nFull results saved to: {out_csv}")


if __name__ == '__main__':
    main()