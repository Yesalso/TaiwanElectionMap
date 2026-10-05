# -*- coding: utf-8 -*-
"""
把 final/ 的 16 张看板 PNG + final/MP3 的配乐合成 MP4。

时间轴约定（关键）：
  画面 16 张用 xfade 交叉淡化（0.5s）；音乐按“选举段”分 6 段，
  每段边界落在「同段最后一张图 → 下一段第一张图」那个转场的【中点】，
  于是音乐切换与画面转场同时发生，且与画面时间轴锁死（不累积漂移）。

用法:
  python make_video.py                 # 出配乐版
  python make_video.py --no-music      # 出无声版
  python make_video.py --crf 18 --name xxx.mp4
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

VIDEO_ROOT = r"D:\Windows\TaiwanElection\Video"
FINAL_DIR = os.path.join(VIDEO_ROOT, "final")
MP3_DIR = os.path.join(FINAL_DIR, "MP3")

# 顺序即播放顺序：(文件名主干, 停留秒数)
# 1994/1998/2002/2006/2010/2014/2018/2022，每场 _1=区级图 _2=村里图
# 2006(20/25)+2010(10/18) 按比例拉长到 86s，使 2006+2010 段画面 = 音乐 84s
TIMELINE = [
    ("831", 25), ("832", 32),          # 1994
    ("871", 15), ("872", 20),          # 1998
    ("911", 10), ("912", 18),          # 2002
    ("951", 23.5), ("952", 29.5),      # 2006  (原 20/25)
    ("991", 11.75), ("992", 21.25),    # 2010  (原 10/18)
    ("1031", 27), ("1032", 34),        # 2014
    ("1071", 23), ("1072", 33),        # 2018
    ("1111", 30), ("1112", 50),        # 2022
]

# 配乐：(mp3 主干, 起始秒, 覆盖第几张图起, 覆盖第几张图止) —— 1-based 闭区间
# 段内图数可变：同一首曲子可以跨两个年份连续播放。
MUSIC = [
    ("1994", 93.0, 1, 2),      # 1:33 起 —— 覆盖 1994
    ("1998", 2.0, 3, 6),       # 0:02 起 —— 覆盖 1998 + 2002 四张
    ("2006", 102.0, 7, 10),    # 1:42 起 —— 覆盖 2006 + 2010 四张
    ("2014", 20.0, 11, 12),    # 0:20 起 —— 覆盖 2014
    ("2018", 15.0, 13, 14),    # 0:15 起 —— 覆盖 2018
    ("2022", 90.0, 15, 16),    # 1:30 起 —— 覆盖 2022
]

W, H = 2560, 1440
FPS = 24
FADE = 0.5        # 画面交叉淡化时长
AFADE = 0.5       # 音乐交叉淡化时长（与画面同步）
LEAD_IN = 0.8     # 全片音乐开头淡入
TAIL_OUT = 2.5    # 全片音乐结尾淡出


def mid_after(k):
    """第 k 张图结束处那个转场的中点（全局秒）。"""
    acc = sum(d for _, d in TIMELINE[:k])
    return acc - k * FADE + FADE / 2


def durations():
    """返回 (画面总时长, 各音乐段应取用的长度)。"""
    total = sum(d for _, d in TIMELINE) - FADE * (len(TIMELINE) - 1)
    lens = []
    for _, _, a, b in MUSIC:
        start = 0.0 if a == 1 else mid_after(a - 1)
        end = total if b == len(TIMELINE) else mid_after(b)
        # 首段无头部交叠、末段无尾部交叠，其余段各向两侧多取 0.25s
        head = 0.0 if a == 1 else FADE / 2
        tail = 0.0 if b == len(TIMELINE) else FADE / 2
        lens.append(round(end - start + head + tail, 4))
    return round(total, 4), lens


def segment_loudness(stem, start, ln):
    """返回该段音乐的平均音量(dB)。"""
    f = os.path.join(MP3_DIR, stem + ".mp3")
    r = subprocess.run(
        [FFMPEG, "-hide_banner", "-ss", str(start), "-t", str(ln), "-i", f,
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"mean_volume:\s+(-?[\d.]+)", r.stderr)
    return float(m.group(1)) if m else None


def build_filter(video_n, music_lens, gains=None):
    parts = []
    for i in range(video_n):
        parts.append(f"[{i}:v]scale={W}:{H},setsar=1,fps={FPS},format=yuv420p[f{i}]")

    prev = "f0"
    for k in range(1, video_n):
        out = f"x{k}" if k < video_n - 1 else "vout"
        off = mid_after(k) - FADE / 2
        parts.append(
            f"[{prev}][f{k}]xfade=transition=fade:duration={FADE}:offset={off:.3f}[{out}]"
        )
        prev = out

    if not music_lens:
        return ";".join(parts), None

    # 音频各段已由 -ss/-t 截好；可选逐段增益（把六首曲子的响度拉平）+ 限幅
    for j in range(len(music_lens)):
        g = 0.0 if not gains else gains[j]
        parts.append(
            f"[{video_n + j}:a]aformat=sample_rates=48000:sample_fmts=fltp:"
            f"channel_layouts=stereo,asetpts=PTS-STARTPTS,"
            f"volume={g:.2f}dB,alimiter=limit=0.891:attack=5:release=50[a{j}]"
        )
    prev = "a0"
    for j in range(1, len(music_lens)):
        out = f"ax{j}" if j < len(music_lens) - 1 else "amix"
        parts.append(f"[{prev}][a{j}]acrossfade=d={AFADE}:c1=tri:c2=tri[{out}]")
        prev = out

    atotal = sum(music_lens) - AFADE * (len(music_lens) - 1)
    parts.append(
        f"[amix]afade=t=in:st=0:d={LEAD_IN},"
        f"afade=t=out:st={max(atotal - TAIL_OUT, 0):.3f}:d={TAIL_OUT}[afin]"
    )
    return ";".join(parts), "afin"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(VIDEO_ROOT, "out_video"))
    ap.add_argument("--name", default="臺北市長選舉1994-2022_2560x1440_配樂版.mp4")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--level", action="store_true",
                    help="逐段响度拉平（六首曲子音量差很多时用）")
    ap.add_argument("--target-mean", type=float, default=-14.0,
                    help="--level 的目标平均音量 dB（默认 -14）")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    raw = os.path.join(args.out, "_raw_tmp.mp4")
    n = len(TIMELINE)
    total, lens = durations()

    cmd = [FFMPEG, "-y", "-loglevel", "error", "-stats"]
    for stem, dur in TIMELINE:
        img = os.path.join(FINAL_DIR, stem + ".png")
        if not os.path.isfile(img):
            sys.exit(f"缺图: {img}")
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", img]

    gains = None
    if not args.no_music:
        print("音乐段：")
        for (stem, start, a, b), ln in zip(MUSIC, lens):
            f = os.path.join(MP3_DIR, stem + ".mp3")
            if not os.path.isfile(f):
                sys.exit(f"缺音乐: {f}")
            cmd += ["-ss", str(start), "-t", str(ln), "-i", f]
            print(
                "  %s.mp3  %d:%04.1f → %d:%04.1f  取 %6.2fs  (画面 %d-%d 张)"
                % (stem, start // 60, start % 60, (start + ln) // 60,
                   (start + ln) % 60, ln, a, b)
            )
        if args.level:
            gains = []
            print("响度拉平（目标 %.1f dB）：" % args.target_mean)
            for (stem, start, a, b), ln in zip(MUSIC, lens):
                cur = segment_loudness(stem, start, ln)
                g = round(args.target_mean - cur, 2)
                gains.append(g)
                print("  %s.mp3 实测 %6.1f dB → %+5.2f dB" % (stem, cur, g))

    fc, alabel = build_filter(n, [] if args.no_music else lens, gains)
    cmd += ["-filter_complex", fc, "-map", "[vout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart"]
    if alabel:
        cmd += ["-map", f"[{alabel}]", "-c:a", "aac", "-b:a", "192k"]
    cmd.append(raw)

    print("画面总时长 %.2f 秒 (%d:%04.1f)" % (total, total // 60, total % 60))
    subprocess.run(cmd, check=True)

    dst = os.path.join(args.out, args.name)
    shutil.move(raw, dst)
    print("完成:", dst, "%.1f MB" % (os.path.getsize(dst) / 1048576))


if __name__ == "__main__":
    main()
