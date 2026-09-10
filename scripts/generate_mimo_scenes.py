from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from openai import OpenAI


GAP_SECONDS = 0.12
MODEL = "mimo-v2.5-tts-voiceclone"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path: Path) -> float:
    output = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        text=True,
    )
    return float(output.strip())


def synthesize(item: tuple[int, int, dict[str, Any]], references: Path, out_dir: Path, api_key: str) -> tuple[int, int, Path]:
    scene_index, line_index, line = item
    reference = references / f"{line['speaker']}.wav"
    output = out_dir / f"scene_{scene_index:02d}_line_{line_index:02d}.wav"
    voice_base64 = base64.b64encode(reference.read_bytes()).decode("ascii")
    client = OpenAI(api_key=api_key, base_url="https://api.xiaomimimo.com/v1")
    completion = None
    for attempt in range(6):
        try:
            completion = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "user", "content": ""},
                    {"role": "assistant", "content": line["text"]},
                ],
                audio={"format": "wav", "voice": f"data:audio/wav;base64,{voice_base64}"},
            )
            break
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 ** (attempt + 1))
    assert completion is not None
    output.write_bytes(base64.b64decode(completion.choices[0].message.audio.data))
    return scene_index, line_index, output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and assemble MIMO cloned dialogue scenes.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--references", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise SystemExit("MIMO_API_KEY is not set")

    manifest_path = Path(args.manifest).resolve()
    references = Path(args.references).resolve()
    out_dir = Path(args.out_dir).resolve()
    line_dir = out_dir / "lines"
    scene_dir = out_dir / "scenes"
    line_dir.mkdir(parents=True, exist_ok=True)
    scene_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    jobs: list[tuple[int, int, dict[str, Any]]] = []
    for scene_index, scene in enumerate(manifest["scenes"], 1):
        for line_index, line in enumerate(scene["lines"], 1):
            jobs.append((scene_index, line_index, line))

    generated: dict[tuple[int, int], Path] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(synthesize, job, references, line_dir, api_key) for job in jobs]
        for future in as_completed(futures):
            scene_index, line_index, path = future.result()
            generated[(scene_index, line_index)] = path
            print(f"generated scene={scene_index} line={line_index}")

    scene_builds: list[dict[str, Any]] = []
    for scene_index, scene in enumerate(manifest["scenes"], 1):
        files: list[Path] = []
        line_meta: list[dict[str, Any]] = []
        raw_cursor = 0.0
        for line_index, line in enumerate(scene["lines"], 1):
            path = generated[(scene_index, line_index)]
            line_duration = duration(path)
            line_meta.append({**line, "file": str(path), "duration": line_duration, "raw_start": raw_cursor})
            files.append(path)
            raw_cursor += line_duration
            if line_index < len(scene["lines"]):
                gap_path = line_dir / f"scene_{scene_index:02d}_gap_{line_index:02d}.wav"
                run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(GAP_SECONDS), "-c:a", "pcm_s16le", str(gap_path)])
                files.append(gap_path)
                raw_cursor += GAP_SECONDS

        concat_list = scene_dir / f"scene_{scene_index:02d}.txt"
        concat_list.write_text("\n".join(f"file '{path.as_posix()}'" for path in files) + "\n", encoding="utf-8")
        raw_path = scene_dir / f"scene_{scene_index:02d}_raw.wav"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(raw_path)])
        raw_duration = duration(raw_path)
        scene_builds.append({
            "scene": scene,
            "files": files,
            "line_meta": line_meta,
            "raw_path": raw_path,
            "raw_duration": raw_duration,
        })

    target_total = float(manifest["duration"])
    natural_total = sum(float(build["raw_duration"]) for build in scene_builds)
    padding_total = target_total - natural_total
    if padding_total < -0.01:
        raise SystemExit(
            f"natural voiceover is {natural_total:.3f}s, longer than target {target_total:.3f}s; shorten dialogue instead of time-stretching"
        )

    hint_total = sum(float(build["scene"]["duration"]) for build in scene_builds)
    planned_durations: list[float] = []
    remaining = target_total
    for index, build in enumerate(scene_builds):
        if index == len(scene_builds) - 1:
            target_duration = remaining
        else:
            target_duration = float(build["raw_duration"]) + padding_total * float(build["scene"]["duration"]) / hint_total
        planned_durations.append(target_duration)
        remaining -= target_duration

    enriched = {"duration": target_total, "scenes": []}
    scene_paths: list[Path] = []
    global_cues: list[dict[str, Any]] = []
    absolute_start = 0.0
    updated_scenes: list[dict[str, Any]] = []

    for build, target_duration in zip(scene_builds, planned_durations):
        scene = build["scene"]
        scene_path = scene_dir / f"scene_{len(scene_paths) + 1:02d}.wav"
        filters = ["apad", f"atrim=duration={target_duration:.3f}"]
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(build["raw_path"]), "-af", ",".join(filters), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(scene_path)])
        scene_paths.append(scene_path)

        scene_record = {"image": scene["image"], "start": absolute_start, "end": absolute_start + target_duration, "duration": target_duration, "lines": []}
        for meta in build["line_meta"]:
            start = absolute_start + meta["raw_start"]
            end = start + meta["duration"]
            cue = {"start": start, "end": end, "speaker": meta["speaker"], "role": meta["role"], "text": meta["text"]}
            scene_record["lines"].append(cue)
            global_cues.append(cue)
        enriched["scenes"].append(scene_record)
        updated_scenes.append({**scene, "duration": target_duration})
        absolute_start += target_duration

    manifest["scenes"] = updated_scenes
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    final_list = scene_dir / "all_scenes.txt"
    final_list.write_text("\n".join(f"file '{path.as_posix()}'" for path in scene_paths) + "\n", encoding="utf-8")
    final_audio = out_dir / "english_voiceover.wav"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(final_list), "-t", str(target_total), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(final_audio)])

    enriched["cues"] = global_cues
    (out_dir / "english_audio_meta.json").write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote={final_audio}")
    print(f"wrote={out_dir / 'english_audio_meta.json'}")


if __name__ == "__main__":
    main()
