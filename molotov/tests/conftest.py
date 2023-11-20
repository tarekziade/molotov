import os
import stat
import subprocess
import warnings

import pytest


def get_opened_fds():
    process_id = os.getpid()
    opened_fds = []
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(process_id)],
            capture_output=True,
            text=True,
            check=True,
        )
        lsof_output = result.stdout.splitlines()

        for line in lsof_output[1:]:
            parts = line.split()
            if len(parts) > 3 and parts[3].isdigit():
                opened_fds.append(int(parts[3]))

    except subprocess.CalledProcessError as e:
        print(f"Error executing lsof: {e}")
        return set()

    return set(opened_fds)


@pytest.fixture(autouse=True)
def check_file_descriptors(request):
    fds = get_opened_fds()
    try:
        yield
    finally:
        diff = fds - get_opened_fds()
        final_diff = []
        if len(diff) > 0:
            for fd in diff:
                try:
                    file_info = os.fstat(fd)
                except Exception:
                    continue
                file_type = "unknown"
                if stat.S_ISREG(file_info.st_mode):
                    file_type = "regular file"
                elif stat.S_ISDIR(file_info.st_mode):
                    file_type = "directory"
                elif stat.S_ISCHR(file_info.st_mode):
                    file_type = "character device"
                elif stat.S_ISBLK(file_info.st_mode):
                    file_type = "block device"
                elif stat.S_ISFIFO(file_info.st_mode):
                    file_type = "FIFO/pipe"
                elif stat.S_ISSOCK(file_info.st_mode):
                    file_type = "socket"

                final_diff.append((fd, file_type))

        if len(final_diff) > 0:
            msg = "\n****** LEAK ******\n"
            for fd, file_type in final_diff:
                msg += f"Leaked file descriptor: {fd} ({file_type})\n"
            msg += "****** LEAK ******\n"

            warnings.warn(msg, ResourceWarning)
