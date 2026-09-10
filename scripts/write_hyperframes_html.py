from __future__ import annotations

import html
import json
import sys
from pathlib import Path


ROLE_CLASSES = {
    "us": "role-us",
    "china": "role-china",
    "saudi": "role-saudi",
    "russia": "role-russia",
}


def number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def caption_class(text: str) -> str:
    return "caption-long" if len(text) > 42 else "caption-short"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: write_hyperframes_html.py META_JSON OUTPUT_HTML")

    meta_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    scene_markup = []
    caption_markup = []
    caption_index = 1
    track_index = 1
    for scene in meta["scenes"]:
        scene_markup.append(
            f'      <img class="scene-image clip" id="scene-{track_index:02d}" '
            f'src="assets/images/{html.escape(scene["image"])}" alt="English story card {track_index}" '
            f'data-start="{number(scene["start"])}" data-duration="{number(scene["duration"])}" data-track-index="1" />'
        )
        for line in scene["lines"]:
            role_class = ROLE_CLASSES.get(line["speaker"], "role-us")
            role_text = html.escape(line["role"].upper())
            text = html.escape(line["text"])
            line_duration = line["end"] - line["start"]
            caption_markup.append(
                f'      <div class="caption {caption_class(line["text"])} clip" id="caption-{caption_index:02d}" '
                f'data-start="{number(line["start"])}" data-duration="{number(line_duration)}" '
                f'data-track-index="10" data-layout-allow-caption-zone>'
                f'<span class="role {role_class}">{role_text}</span><span class="text">{text}</span></div>'
            )
            caption_index += 1
        track_index += 1

    markup = f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>World Support Chat - English Remake</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: #171a22; }}
      body {{ font-family: Arial, Helvetica, sans-serif; }}
      #root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #171a22; }}
      .scene-image {{ position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; transform-origin: center center; will-change: transform; }}
      .caption {{
        position: absolute; left: 42px; right: 42px; bottom: 76px; min-height: 124px;
        padding: 22px 28px 24px; border: 3px solid rgba(255,255,255,.92); border-radius: 22px;
        background: rgba(10,12,18,.9); color: #fff; box-shadow: 0 12px 28px rgba(0,0,0,.28);
        opacity: 0; z-index: 20;
      }}
      .caption .role {{ display: inline-block; margin-bottom: 10px; padding: 6px 14px; border-radius: 999px; color: #fff; font-size: 22px; font-weight: 800; line-height: 1; }}
      .caption .text {{ display: block; font-size: 34px; font-weight: 700; line-height: 1.14; letter-spacing: 0; overflow-wrap: anywhere; }}
      .role-us {{ background: #2f6de0; }}
      .role-china {{ background: #ed3b3b; }}
      .role-saudi {{ background: #7d5a00; }}
      .role-russia {{ background: #566984; }}
      .caption-short .text {{ font-size: 38px; }}
      .caption-long .text {{ font-size: 29px; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{number(meta["duration"])}" data-width="1080" data-height="1920">
{chr(10).join(scene_markup)}

{chr(10).join(caption_markup)}

      <audio id="english-voiceover" src="assets/audio/english_voiceover.wav" data-start="0" data-duration="{number(meta["duration"])}" data-track-index="20" data-volume="1"></audio>
    </div>

    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      document.querySelectorAll(".scene-image").forEach((image) => {{
        const start = Number(image.dataset.start);
        const duration = Number(image.dataset.duration);
        tl.fromTo(image, {{ scale: 1.025 }}, {{ scale: 1, duration: Math.min(duration, 0.85), ease: "power2.out" }}, start);
      }});
      document.querySelectorAll(".caption").forEach((caption) => {{
        const start = Number(caption.dataset.start);
        const duration = Number(caption.dataset.duration);
        tl.fromTo(caption, {{ opacity: 0, y: 18 }}, {{ opacity: 1, y: 0, duration: Math.min(0.22, duration / 3), ease: "power2.out" }}, start);
        if (duration > 0.45) {{
          tl.to(caption, {{ opacity: 0, y: 8, duration: 0.14, ease: "power1.in" }}, start + duration - 0.14);
        }}
      }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markup, encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
