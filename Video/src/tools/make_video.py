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
FINAL_DIR = os.path.join(VIDEO_ROOT, "dist", "final")
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


# ------------------------------------------------------------------ 输入帧定位
# TIMELINE 的档名主干是旧编号：831 = 民国 83 年（1994）第 1 张（区级图），
# 832 = 同年第 2 张（村里图）。民国年 = 西元 - 1911，所以 831/1112 这类名字
# 可以直接反推回年份，也就能对到 dist/dist_png/taipei-mayor/ 的产物。
STEM_RE = re.compile(r"^(\d{2,3})([12])$")


def stem_year(stem):
    m = STEM_RE.match(stem)
    return 1911 + int(m.group(1)) if m else None


def draft_paths(stem):
    """--draft 用：把旧编号对到 dist/dist_png 的看板产物（按优先级）。

    区级图（后缀 1）优先找 `<年>-map2.png`（2026-10-28 起可用
    `render_boards.mjs --variants map,map2` 产出），没有就退回村里版
    `<年>.png` 并告警 —— 宁可先出一版草稿，也不要整条链路停着。
    """
    year = stem_year(stem)
    if not year:
        return []
    base = os.path.join(VIDEO_ROOT, "dist", "dist_png", "taipei-mayor")
    if stem.endswith("1"):
        return [os.path.join(base, f"{year}-map2.png"),
                os.path.join(base, f"{year}.png")]
    return [os.path.join(base, f"{year}.png")]


def resolve_frames(draft=False):
    """回传 [(stem, 实际路径, 是否草稿替代, 备注)]，缺的路径是 None。"""
    out = []
    for stem, _dur in TIMELINE:
        want = os.path.join(FINAL_DIR, stem + ".png")
        if os.path.isfile(want):
            out.append((stem, want, False, ""))
            continue
        alts = draft_paths(stem) if draft else []
        hit = next((p for p in alts if os.path.isfile(p)), None)
        note = ""
        if hit and alts and hit != alts[0]:
            note = "区级版缺失，暂用村里版"
        out.append((stem, hit, bool(hit), note))
    return out


def preflight(draft=False, music=True, verbose=True):
    """合成前先点清家底：缺图/缺音乐一次说完，别等 ffmpeg 才报错。

    返回 (frames, missing_images, missing_music)。
    """
    frames = resolve_frames(draft=draft)
    missing = [s for s, p, _d, _n in frames if not p]
    missing_music = []
    if music:
        for stem, _start, _a, _b in MUSIC:
            if not os.path.isfile(os.path.join(MP3_DIR, stem + ".mp3")):
                missing_music.append(stem)

    if verbose:
        print("输入帧（%d 张）：" % len(frames))
        for stem, path, is_draft, note in frames:
            if path:
                mark = "草稿" if is_draft else "  ✓ "
                rel = os.path.relpath(path, VIDEO_ROOT)
                print("  %s %-5s %s%s" % (mark, stem, rel, ("  ← " + note) if note else ""))
            else:
                print("  ✗  %-5s 缺 %s" % (stem, os.path.join(FINAL_DIR, stem + ".png")))
        if music:
            print("配乐（%d 首）：%s" % (
                len(MUSIC),
                "齐备" if not missing_music
                else "缺 " + "、".join(s + ".mp3" for s in missing_music)))
    return frames, missing, missing_music


def report_gap(missing, missing_music):
    """缺件时给可执行的下一步，而不是一句「缺图」。"""
    print("\n[无法合成] 缺 %d 张图、%d 首配乐。" % (len(missing), len(missing_music)))
    if missing:
        print("  图：把后期合成好的看板放到 dist/final/<编号>.png（编号见 TIMELINE）")
        print("     或加 --draft 先用 dist/dist_png/taipei-mayor/<年份>[-map2].png 出草稿")
        print("     区级图（编号末位 1）可用：node src/tools/render_boards.mjs \\")
        print("         --boards <8 场 taipei-mayor> --variants map,map2")
    if missing_music:
        print("  配乐：把 mp3 放到 dist/final/MP3/<年份>.mp3（1994/1998/2006/2014/2018/2022）")
        print("        先出无声版可加 --no-music")


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
    ap.add_argument("--out", default=os.path.join(VIDEO_ROOT, "dist", "videos"))
    ap.add_argument("--name", default="臺北市長選舉1994-2022_2560x1440_配樂版.mp4")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--level", action="store_true",
                    help="逐段响度拉平（六首曲子音量差很多时用）")
    ap.add_argument("--target-mean", type=float, default=-14.0,
                    help="--level 的目标平均音量 dB（默认 -14）")
    ap.add_argument("--check", action="store_true",
                    help="只检查输入是否齐备（不合成）；缺件退出码 2")
    ap.add_argument("--draft", action="store_true",
                    help="缺 dist/final/<编号>.png 时，用 dist/dist_png/taipei-mayor/"
                         "的看板产物顶替出一版草稿（没有后期合成的照片）")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    raw = os.path.join(args.out, "_raw_tmp.mp4")
    n = len(TIMELINE)
    total, lens = durations()

    # 先把家底点清：缺什么一次说完，不要等 ffmpeg 跑到一半才报错
    frames, missing, missing_music = preflight(draft=args.draft,
                                               music=not args.no_music)
    if missing or missing_music:
        report_gap(missing, missing_music)
        sys.exit(2)
    if args.check:
        print("\n[检查通过] 输入齐备，可以合成（画面 %.2f 秒）。" % total)
        return
    if args.draft and args.name == "臺北市長選舉1994-2022_2560x1440_配樂版.mp4":
        args.name = "臺北市長選舉1994-2022_2560x1440_草稿.mp4"   # 别覆盖正式成品

    cmd = [FFMPEG, "-y", "-loglevel", "error", "-stats"]
    for (stem, dur), (_s, img, _is_draft, _note) in zip(TIMELINE, frames):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", img]

    gains = None
    if not args.no_music:
        print("音乐段：")
        for (stem, start, a, b), ln in zip(MUSIC, lens):
            f = os.path.join(MP3_DIR, stem + ".mp3")
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
