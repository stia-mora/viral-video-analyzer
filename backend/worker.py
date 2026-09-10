import json
import shutil
import threading
import time
from pathlib import Path
from . import analysis, collector, config, media, store

STAGES = [
    ("collect", "采集视频与互动数据"),
    ("media", "下载资源与提取画面"),
    ("transcribe", "提取视频文案"),
    ("analyze", "分析文案与视频爆点"),
    ("done", "报告已完成"),
]


class Worker:
    def __init__(self):
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.thread = None

    def start(self):
        # This desktop deployment owns one GPU and one worker process. An OS lock
        # prevents a second uvicorn instance from resetting an active queue.
        self.lock_file = (config.DATA / "worker.lock").open("a+b")
        self.lock_file.seek(0)
        if self.lock_file.read(1) == b"":
            self.lock_file.write(b"0")
            self.lock_file.flush()
        self.lock_file.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt

                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise RuntimeError("已有片析服务在使用同一数据目录，请勿启动多个 worker")
        with store.connect() as con:
            con.execute(
                "UPDATE jobs SET status='queued',stage='等待恢复' WHERE status='running'"
            )
        self.thread = threading.Thread(
            target=self.loop, daemon=True, name="video-worker"
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.wake.set()

    def loop(self):
        while not self.stop_event.is_set():
            with store.connect() as con:
                con.execute("BEGIN IMMEDIATE")
                row = con.execute(
                    "SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1"
                ).fetchone()
                if row:
                    con.execute(
                        "UPDATE jobs SET status='running' WHERE id=? AND status='queued'",
                        (row["id"],),
                    )
            if not row:
                self.wake.wait(2)
                self.wake.clear()
                continue
            self.process(row["id"])

    def process(self, job_id):
        job = store.job(job_id)
        folder = config.MEDIA / job_id
        folder.mkdir(parents=True, exist_ok=True)
        result = job["result"]
        try:
            if not result.get("video_id"):
                store.update(job_id, stage="collect", status="running")
                if job["url"].startswith("local:"):
                    source = config.ROOT / "outputs" / job["url"][6:]
                    if not source.resolve().is_relative_to(
                        (config.ROOT / "outputs").resolve()
                    ):
                        raise ValueError("本地来源无效")
                    info = json.loads(
                        (source / "video.info.json").read_text(encoding="utf-8")
                    )
                    result = collector.clean_info(info, info.get("webpage_url", ""))
                    result["imported"] = True
                    result["collected_at"] = (
                        info.get("epoch")
                        or (source / "video.info.json").stat().st_mtime
                    )
                    for name in [
                        "video.mp4",
                        "video.webm",
                        "video.mkv",
                        "audio.wav",
                        "text_plain.txt",
                        "text.txt",
                        "asr_result.json",
                        "subtitles.srt",
                    ]:
                        if (source / name).is_file():
                            shutil.copy2(source / name, folder / name)
                    result["warnings"] = [
                        "已导入本地历史资源，互动数据为历史快照，可新建链接分析以重新采集"
                    ]
                else:
                    result = collector.collect(job["url"], folder)
                store.update(job_id, result=result)
            store.update(job_id, stage="media")
            result.update(media.prepare_media(folder))
            result["ratios"] = analysis.ratios(result["metrics"])
            result["comment_insights"] = analysis.comment_insights(
                result.get("comments", [])
            )
            store.update(job_id, result=result, stage="transcribe")
            transcript_data = result.get("transcript", {})
            refresh_transcript = bool(
                result.get("has_audio", True)
                and transcript_data.get("text")
                and not transcript_data.get("language")
            )
            if (not transcript_data.get("text") or refresh_transcript) and result.get(
                "has_audio", True
            ):
                try:
                    result["transcript"] = media.transcript(
                        folder, result.get("has_audio", True), force=refresh_transcript
                    )
                    result["warnings"] = [
                        w
                        for w in result.get("warnings", [])
                        if "语音转写失败" not in w and "ASR 环境未安装" not in w
                    ]
                except Exception as error:
                    result["transcript"] = {
                        "text": "",
                        "segments": [],
                        "timing": "none",
                        "note": str(error),
                    }
                    result.setdefault("warnings", []).append(str(error))
            result["analysis"] = analysis.baseline(result)
            store.update(job_id, result=result, stage="analyze")
            try:
                result["analysis"] = analysis.analyze(result, folder)
                missing_transcript = result.get("has_audio", True) and not result.get(
                    "transcript", {}
                ).get("text")
                status = "partial" if missing_transcript else "done"
                error = (
                    "视频含音轨但转写未完成，请检查 ASR 环境或补充文案后重试"
                    if missing_transcript
                    else None
                )
            except Exception as exc:
                status = "partial"
                error = str(exc)[:500]
                result["analysis"]["limitations"].append(error)
            result["analyzed_at"] = time.time()
            store.update(
                job_id, result=result, status=status, stage="done", error=error
            )
        except Exception as exc:
            message = str(exc)
            if "yt_dlp" in type(exc).__module__:
                message = "视频下载未完成。请检查视频是否公开、链接是否有效，以及平台登录 Cookie 是否过期。"
            store.update(
                job_id,
                result=result,
                status="failed",
                stage="failed",
                error=message[:700],
            )


worker = Worker()
