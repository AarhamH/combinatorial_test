import os
import shutil
import stat

from .config import TEST_DIR


def setup_env():
    if os.path.exists(TEST_DIR):
        def _remove_readonly(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(TEST_DIR, onerror=_remove_readonly)

    os.makedirs(TEST_DIR)
    os.makedirs(os.path.join(TEST_DIR, "writable_out"), exist_ok=True)

    restricted = os.path.join(TEST_DIR, "restricted_out")
    os.makedirs(restricted, exist_ok=True)
    os.chmod(restricted, 0o444)