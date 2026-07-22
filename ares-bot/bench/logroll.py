#!/usr/bin/env python3
"""滚动日志器:从 stdin 读,只把最近 keep 字节写入目标文件。

用法: some_command 2>&1 | python3 logroll.py out.log [keep_bytes]
防止 bench/promotion 长跑日志把磁盘写爆(曾 18h 写出 25GB)。
"""
import sys

path = sys.argv[1]
keep = int(sys.argv[2]) if len(sys.argv) > 2 else 20 * 1024 * 1024

buf = bytearray()
src = sys.stdin.buffer
while True:
    chunk = src.read(65536)
    if not chunk:
        break
    buf += chunk
    if len(buf) > keep:
        del buf[: len(buf) - keep]
        with open(path, "wb") as f:
            f.write(buf)
with open(path, "wb") as f:
    f.write(buf)
