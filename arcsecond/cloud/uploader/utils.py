import math


def is_file_hidden(path):
    return any([part for part in path.parts if len(part) > 0 and part[0] == "."])


def __get_formatted_time(seconds):
    if seconds > 86400:
        return f"{seconds / 86400:.1f}d"
    elif seconds > 3600:
        return f"{seconds / 3600:.1f}h"
    elif seconds > 60:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds:.1f}s"


def __get_formatted_size_times(size):
    total = f"{__get_formatted_time(size / pow(10, 4))} on 10 kB/s, "
    total += f"{__get_formatted_time(size / pow(10, 5))} on 100 kB/s, "
    total += f"{__get_formatted_time(size / pow(10, 6))} on 1 MB/s, "
    total += f"{__get_formatted_time(size / pow(10, 7))} on 10 MB/s"
    return total


def __get_formatted_bytes_size(size):
    if size == 0:
        return "0 Bytes"
    k = 1024
    units = ["Bytes", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    i = math.floor(math.log10(1.0 * size) / math.log10(k))
    return f"{(size / math.pow(k, i)):.2f} {units[i]}"
