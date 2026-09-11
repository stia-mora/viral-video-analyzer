import json
import math
import os
import re
import subprocess
import wave
import httpx
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from . import config


def wav_duration_seconds(path):
    try:
        with wave.open(str(path), "rb") as wav:
            return wav.getnframes() / float(wav.getframerate())
    except (OSError, wave.Error, ZeroDivisionError):
        return None


def run(args, timeout=180):
    completed = subprocess.run(
        [str(a) for a in args],
        capture_output=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        raise RuntimeError("媒体处理失败：" + completed.stderr[-800:])
    return completed.stdout


def atomic_media(args, target, timeout=180):
    temp = target.with_name(target.stem + ".pending" + target.suffix)
    try:
        run([*args, temp], timeout)
        if not temp.is_file() or temp.stat().st_size == 0:
            raise RuntimeError("媒体处理未产生有效文件")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def prepare_media(folder):
    candidates = [
        p
        for p in folder.glob("video.*")
        if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")
    ]
    if not candidates:
        raise RuntimeError("没有找到已下载的视频文件")
    video = max(candidates, key=lambda p: p.stat().st_size)
    info = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                video,
            ]
        )
    )
    duration = float(info["format"]["duration"])
    if (
        not math.isfinite(duration)
        or duration <= 0
        or duration > config.MAX_VIDEO_SECONDS
    ):
        raise ValueError("视频时长无效或超过 15 分钟限制")
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    playable = folder / "playback.mp4"
    if not playable.exists():
        if stream.get("codec_name") == "h264" and video.suffix == ".mp4":
            playable = video
        else:
            atomic_media(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    video,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                ],
                playable,
                600,
            )
    if not (folder / "cover.jpg").exists():
        atomic_media(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                video,
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
            ],
            folder / "cover.jpg",
        )
    # Normalize any webp/png response to an actual JPEG.
    with Image.open(folder / "cover.jpg") as image:
        image.convert("RGB").save(folder / "cover.jpg", quality=90)
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    if has_audio and not (folder / "audio.wav").exists():
        atomic_media(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                video,
                "-vn",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
            ],
            folder / "audio.wav",
        )
    frames = folder / "frames"
    frames.mkdir(exist_ok=True)
    interval = max(3, math.ceil(duration / 48))
    times = [float(t) for t in range(0, math.ceil(duration), interval)][:48]
    for index, second in enumerate(times):
        atomic_media(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                str(second),
                "-i",
                video,
                "-frames:v",
                "1",
                "-vf",
                "scale=512:-2",
            ],
            frames / f"frame-{index+1:03d}.jpg",
        )
    records, previous = [], None
    for index, second in enumerate(times):
        frame = frames / f"frame-{index+1:03d}.jpg"
        with Image.open(frame) as image:
            gray = image.convert("L").resize((64, 64))
            brightness = round(ImageStat.Stat(gray).mean[0] / 255 * 100, 1)
            delta = (
                round(
                    ImageStat.Stat(ImageChops.difference(gray, previous)).mean[0]
                    / 255
                    * 100,
                    1,
                )
                if previous
                else None
            )
            previous = gray.copy()
        records.append(
            {
                "time": round(second, 2),
                "file": "frames/" + frame.name,
                "brightness": brightness,
                "change": delta,
                "description": "",
                "method": "image_statistics",
            }
        )
    return {
        "duration": duration,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "video_file": video.name,
        "playback_file": playable.name,
        "cover_file": "cover.jpg",
        "has_audio": has_audio,
        "frames": records,
        "frame_interval": interval,
    }


def cloud_transcript(folder):
    from . import store

    endpoint = store.setting("asr_base_url", "https://api.siliconflow.cn/v1").rstrip(
        "/"
    )
    model = store.setting("asr_model", "XingChenAGI/XingChenASR-V3.2-Ultra")
    key = store.setting("asr_api_key")
    if not key:
        raise RuntimeError("未配置云端 ASR API Key")
    audio = folder / "audio.wav"
    try:
        with audio.open("rb") as stream:
            response = httpx.post(
                endpoint + "/audio/transcriptions",
                headers={"Authorization": "Bearer " + key},
                files={"file": (audio.name, stream, "audio/wav")},
                data={"model": model},
                timeout=httpx.Timeout(300.0, connect=30.0),
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError("云端 ASR 请求超时（300 秒）") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("云端 ASR 网络连接失败") from exc
    if response.status_code in (401, 403):
        raise RuntimeError("云端 ASR 鉴权失败，请检查 API Key")
    if response.status_code >= 400:
        raise RuntimeError(f"云端 ASR 返回 HTTP {response.status_code}，请检查模型名称")
    try:
        body = response.json()
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError("云端 ASR 返回格式不兼容，缺少 text 字段") from exc
    text = text.strip()
    duration = wav_duration_seconds(audio) or 0.0
    (folder / "text_plain.txt").write_text(text + "\n", encoding="utf-8")
    (folder / "text.txt").write_text(
        f"[0.0s -> {duration:.1f}s] {text}\n", encoding="utf-8"
    )
    (folder / "asr_result.json").write_text(
        json.dumps(
            {
                "model": model,
                "language": body.get("language", "auto"),
                "timestamps": False,
                "provider": "cloud",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "text": text,
        "segments": [],
        "timing": "whole_video",
        "language": body.get("language", "auto"),
        "provider": "cloud",
        "note": f"云端 ASR 转写（{model}）；未提供句级时间戳，请核对专有名词",
    }


def transcript(folder, has_audio=True, force=False):
    if not has_audio:
        return {"text": "", "segments": [], "timing": "none", "note": "原视频无音轨"}
    from . import store

    if store.setting("asr_provider", "auto") == "cloud":
        return cloud_transcript(folder)
    plain = folder / "text_plain.txt"
    local_error = None
    if force or not plain.exists() or not (folder / "asr_result.json").exists():
        executable = Path(config.ASR_PYTHON)
        if not executable.exists():
            raise RuntimeError(
                "本地 Qwen ASR 环境未安装，请按部署文档设置 PIANXI_ASR_PYTHON"
            )
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONNOUSERSITE"] = "1"
        # Cached local models should never stall on Hub metadata requests.
        local_models = []
        for model_name, flag in [
            ("Qwen3-ASR-1.7B", "--model"),
            ("Qwen3-ForcedAligner-0.6B", "--aligner"),
        ]:
            snapshots = (
                config.ROOT
                / ".hf-cache/hub"
                / ("models--Qwen--" + model_name)
                / "snapshots"
            )
            ready = [
                p
                for p in snapshots.glob("*")
                if (p / "config.json").exists() and any(p.glob("*.safetensors"))
            ]
            if ready:
                local_models.extend([flag, str(ready[0])])
        if len(local_models) == 4:
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
        staging = folder / "asr-pending"
        staging.mkdir(exist_ok=True)
        proc = subprocess.run(
            [
                str(executable),
                str(config.ROOT / "scripts/qwen3_asr_transcribe.py"),
                "--audio",
                str(folder / "audio.wav"),
                "--out-dir",
                str(staging),
                "--timestamps",
                "auto",
                "--language",
                "auto",
                *local_models,
            ],
            env=env,
            capture_output=True,
            timeout=1200,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        (folder / "asr.log").write_bytes(proc.stdout + b"\n" + proc.stderr)
        if proc.returncode:
            local_error = RuntimeError("本地语音转写失败，请检查 GPU 和 Qwen 模型")
        else:
            for name in ["text_plain.txt", "text.txt", "asr_result.json"]:
                (staging / name).replace(folder / name)
    if local_error or not plain.exists():
        if store.setting("asr_provider", "auto") == "auto" and store.setting(
            "asr_api_key"
        ):
            fallback = cloud_transcript(folder)
            fallback["note"] = (
                "本地 ASR 失败，已自动切换云端备用 ASR。" + fallback["note"]
            )
            return fallback
        raise local_error or RuntimeError("本地语音转写未生成结果")
    text = plain.read_text(encoding="utf-8").strip()
    lines = (
        (folder / "text.txt").read_text(encoding="utf-8")
        if (folder / "text.txt").exists()
        else ""
    )
    segments = [
        {"start": float(a), "end": float(b), "text": t.strip()}
        for a, b, t in re.findall(r"\[([\d.]+)s\s*->\s*([\d.]+)s\]\s*([^\n]+)", lines)
    ]
    meta = (
        json.loads((folder / "asr_result.json").read_text(encoding="utf-8"))
        if (folder / "asr_result.json").exists()
        else {}
    )
    timed = bool(meta.get("timestamps"))
    # Existing SRTs can supply a better alignment than legacy one-line transcript.
    if not timed and (folder / "subtitles.srt").exists():
        source = (folder / "subtitles.srt").read_text(encoding="utf-8-sig")

        def seconds(t):
            h, m, s = t.replace(",", ".").split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)

        rows = re.findall(
            r"(\d{2}:\d{2}:\d{2}[,.]\d+) --> (\d{2}:\d{2}:\d{2}[,.]\d+)\s*\n(.*?)(?=\n\s*\n|$)",
            source,
            re.S,
        )
        if rows:
            segments = [
                {"start": seconds(a), "end": seconds(b), "text": t.replace("\n", " ")}
                for a, b, t in rows
            ]
            timed = True
    return {
        "text": text,
        "segments": segments,
        "timing": "aligned" if timed else "whole_video",
        "language": meta.get("language") or "auto",
        "provider": meta.get("provider", "local"),
        "note": (
            f"本地 Qwen3-ASR 转写（识别语言：{meta.get('language') or 'auto'}）；请核对专有名词"
            if timed
            else "转写未对齐到句子，不能据此断言某句出现的秒数"
        ),
    }
