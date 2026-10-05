# -*- coding: utf-8 -*-
"""
质检 tools/make_video.py 的成品：验证每一段画面位置上，实际播的音乐
就是对应该年份那首 mp3 的对应段落（AAC 有损，用波形平均误差判定，不做逐位比对）。

用法: python tools/verify_video.py <成品.mp4>
"""
import array
import importlib.util
import os
import subprocess
import sys

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))


def load_module():
    spec = importlib.util.spec_from_file_location("mv", os.path.join(HERE, "make_video.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def pcm(ffmpeg, args):
    r = subprocess.run(
        [ffmpeg, "-v", "error"] + args + ["-f", "s16le", "-ac", "2", "-ar", "48000", "-"],
        capture_output=True, check=True)
    a = array.array("h")
    a.frombytes(r.stdout)
    return a


def main():
    video = sys.argv[1]
    m = load_module()
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    total, lens = m.durations()

    print("=" * 84)
    # 每段音频内容在成片里的起点 = 前几段长度之和 - 跨段交叠
    pos = 0.0
    rows = []
    for j, ((stem, start, a, b), ln) in enumerate(zip(m.MUSIC, lens)):
        seg_start = pos                    # 该段音频内容在成片中的全局起点
        mid = seg_start + ln / 2           # 取中点 1 秒做比对（远离交叠区）
        rows.append((stem, start, mid, seg_start, ln, a, b))
        pos += ln - m.AFADE

    print("%-8s %-12s %-12s %-10s" % ("音乐文件", "源mp3取样点", "成片取样点", "相对误差"))
    print("-" * 84)
    worst = 0.0
    for stem, start, mid, seg_start, ln, a, b in rows:
        src_at = start + (mid - seg_start)
        v = pcm(ff, ["-ss", "%.3f" % mid, "-t", "1.0", "-i", video])
        s = pcm(ff, ["-ss", "%.3f" % src_at, "-t", "1.0", "-i",
                     os.path.join(m.MP3_DIR, stem + ".mp3")])
        n = min(len(v), len(s))
        if n == 0:
            print("  %s: 取不到音频!" % stem)
            continue
        diff = 0
        energy = 0
        for i in range(0, n, 7):           # 抽样，够用且快
            d = v[i] - s[i]
            diff += abs(d)
            energy += abs(s[i])
        mae = diff / (n / 7) / 32768
        rel = diff / energy if energy else 9.99
        worst = max(worst, rel)
        print("%-10s %-12s %-12s %6.2f%%  | 画面 %d-%d 张" % (
            stem + ".mp3", "%.1fs" % src_at, "%.1fs" % mid, rel * 100, a, b))

    print("-" * 84)
    print("判定：相对误差越小＝成片该处音频与该 mp3 该段越吻合（AAC 有损，<30%% 即同一段音乐）")
    print("最大相对误差 %.1f%% → %s" % (worst * 100, "对位正确 ✅" if worst < 0.30 else "存在错位 ❌"))

    # 成片规格
    r = subprocess.run([ff, "-hide_banner", "-i", video], capture_output=True, text=True)
    for line in (r.stderr or "").splitlines():
        if "Duration" in line or "Stream #" in line:
            print(line.strip())
    print("画面总长(脚本计算) %.2f s" % total)


if __name__ == "__main__":
    main()
