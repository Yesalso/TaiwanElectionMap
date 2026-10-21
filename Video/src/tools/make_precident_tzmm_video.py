# -*- coding: utf-8 -*-
"""
把 dist/final/precident-tzmm/1 的 8 张总统选举地图 PNG + Video/MP3 的配乐合成 MP4。

时间轴（关键）：
  1. 依次展示 1996–2024 各年地图，每张图停留时长 = 对应配乐的「播放区间」长度；
  2. 画面用 xfade 交叉淡化（0.5s），音乐用 acrossfade（0.5s），
     每段配乐的切换点落在「上一张图 → 下一张图」转场的【中点】，
     于是音乐与画面锁死、不累积漂移，且各段配乐实际播放区间 =
     用户指定的 start→end（段长恰等于 end-start）。

用法:
  python make_precident_tzmm_video.py               # 出配乐版
  python make_precident_tzmm_video.py --level       # 逐段响度拉平
  python make_precident_tzmm_video.py --no-music    # 出无声版
  python make_precident_tzmm_video.py --crf 18 --name xxx.mp4
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

VIDEO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../Video（本檔在 src/tools/）
OUT_DIR = os.path.join(VIDEO_ROOT, "dist", "final", "precident-tzmm")
IMG_DIR = os.path.join(OUT_DIR, "1")
MP3_DIR = os.path.join(VIDEO_ROOT, "MP3")

# 顺序即播放顺序：(标签, 图片文件名, 配乐文件名 或 None, 起始秒, 结束秒)
# 每年一张图、一段配乐，画面停留 = 结束 - 起始。
SEGMENTS = [
    ("1996", "1996-president-tzmm_2560x1440.png",
     "恳丁→基隆(1).mp3", 51.0, 81.0),
    ("2000", "2000-president-tzmm_2560x1440.png",
     "有你有我-宋楚瑜2000競選總統主題曲(王建傑演唱)_mp3.mp3", 185.0, 223.0),
    ("2004", "2004-president-tzmm_2560x1440.png",
     "Ray YT｜群星｜台灣有你真好｜歌詞.mp4", 43.0, 78.0),
    ("2008", "2008-president-tzmm_2560x1440.png",
     "臺灣向前行.mp3", 95.0, 125.0),
    ("2012", "2012-president-tzmm_2560x1440.png",
     "WE ARE ONE.mp3", 184.0, 212.0),
    ("2016", "2016-president-tzmm_2560x1440.png",
     "《台灣美樂地》為你微笑_南西樂團_mp3.mp3", 160.0, 205.0),
    ("2020", "2020-president-tzmm_2560x1440.png",
     "2020小英總統競選歌曲《自信勇敢 咱的名》MV上線！ ── 滅火器Fire Ex._mp3.mp3",
     130.0, 162.0),
    ("2024", "2024-president-tzmm_2560x1440.png",
     "「#晴空加長版」 看到後面國歌那段 被感動到了.._mp3.mp3", 77.0, 125.0),
]

W, H = 2560, 1440
FPS = 24
FADE = 0.5        # 画面交叉淡化时长
AFADE = 0.5       # 音乐交叉淡化时长（与画面同步）
TAIL_OUT = 2.0    # 全片音乐结尾淡出


def durations():
    """各画面停留秒数。"""
    return [round(end - start, 4) for _l, _i, _m, start, end in SEGMENTS]


def mid_after(k):
    """第 k 张图（1-based）结束处那个转场的中点（全局秒）。"""
    acc = sum(durations()[:k])
    return acc - k * FADE + FADE / 2


def music_lens():
    """各段配乐应取用的长度：段长恰等于 结束-起始。"""
    durs = durations()
    total = sum(durs) - FADE * (len(durs) - 1)
    lens = []
    for i in range(len(SEGMENTS)):
        a = b = i + 1
        seg_start = 0.0 if a == 1 else mid_after(a - 1)
        seg_end = total if b == len(SEGMENTS) else mid_after(b)
        head = 0.0 if a == 1 else FADE / 2
        tail = 0.0 if b == len(SEGMENTS) else FADE / 2
        lens.append(round(seg_end - seg_start + head + tail, 4))
    return round(total, 4), lens


def segment_loudness(path, start, ln):
    """返回该段音乐的平均音量(dB)。"""
    r = subprocess.run(
        [FFMPEG, "-hide_banner", "-ss", str(start), "-t", str(ln), "-i", path,
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"mean_volume:\s+(-?[\d.]+)", r.stderr)
    return float(m.group(1)) if m else None


def build_filter(video_n, seg_lens, gains=None):
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

    if not seg_lens:
        return ";".join(parts), None

    for j in range(len(seg_lens)):
        g = 0.0 if not gains else gains[j]
        parts.append(
            f"[{video_n + j}:a]aformat=sample_rates=48000:sample_fmts=fltp:"
            f"channel_layouts=stereo,asetpts=PTS-STARTPTS,"
            f"volume={g:.2f}dB,alimiter=limit=0.891:attack=5:release=50[a{j}]"
        )
    prev = "a0"
    for j in range(1, len(seg_lens)):
        out = f"ax{j}" if j < len(seg_lens) - 1 else "amix"
        parts.append(f"[{prev}][a{j}]acrossfade=d={AFADE}:c1=tri:c2=tri[{out}]")
        prev = out

    atotal = sum(seg_lens) - AFADE * (len(seg_lens) - 1)
    parts.append(
        f"[amix]afade=t=out:st={max(atotal - TAIL_OUT, 0):.3f}:d={TAIL_OUT}[afin]"
    )
    return ";".join(parts), "afin"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--name", default="總統選舉1996-2024_tzmm_2560x1440_配樂版.mp4")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="slow",
                    help="x264 编码预设，越慢同 crf 画质越好（veryfast/fast/medium/slow/slower）")
    ap.add_argument("--tune", default="stillimage",
                    help="x264 tune，静止看板图用 stillimage；不需要则传 none")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--level", action="store_true",
                    help="逐段响度拉平（各首曲子音量差很多时用）")
    ap.add_argument("--target-mean", type=float, default=-14.0)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    raw = os.path.join(args.out, "_raw_tmp.mp4")
    n = len(SEGMENTS)
    total, lens = music_lens()

    for label, img_name, _m, _s, _e in SEGMENTS:
        img = os.path.join(IMG_DIR, img_name)
        if not os.path.isfile(img):
            sys.exit(f"缺图: {img}")

    cmd = [FFMPEG, "-y", "-loglevel", "error", "-stats"]
    for (label, img_name, _m, _s, _e), dur in zip(SEGMENTS, durations()):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", str(dur),
                "-i", os.path.join(IMG_DIR, img_name)]

    gains = None
    if not args.no_music:
        print("配乐段：")
        for idx, ((label, _img, music, start, end), ln) in enumerate(zip(SEGMENTS, lens), 1):
            path = os.path.join(MP3_DIR, music)
            if not os.path.isfile(path):
                sys.exit(f"缺音乐: {path}")
            cmd += ["-ss", str(start), "-t", str(ln), "-i", path]
            print("  %-6s  %d:%04.1f → %d:%04.1f  取 %6.1fs  (%s)"
                  % (label, start // 60, start % 60, (start + ln) // 60,
                     (start + ln) % 60, ln, music))
        if args.level:
            gains = []
            print("响度拉平（目标 %.1f dB）：" % args.target_mean)
            for (label, _img, music, start, end), ln in zip(SEGMENTS, lens):
                path = os.path.join(MP3_DIR, music)
                cur = segment_loudness(path, start, ln)
                g = round(args.target_mean - cur, 2)
                gains.append(g)
                print("  %-6s 实测 %6.1f dB → %+5.2f dB" % (label, cur, g))

    fc, alabel = build_filter(n, [] if args.no_music else lens, gains)
    cmd += ["-filter_complex", fc, "-map", "[vout]",
            "-c:v", "libx264", "-preset", args.preset]
    if args.tune and args.tune != "none":
        cmd += ["-tune", args.tune]
    cmd += ["-crf", str(args.crf),
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
