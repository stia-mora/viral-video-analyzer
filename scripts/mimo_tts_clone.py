from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

from openai import OpenAI


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MIMO voice-cloned speech from a local WAV reference.")
    parser.add_argument("--reference", required=True, help="Reference WAV file.")
    parser.add_argument("--text", required=True, help="Text to synthesize.")
    parser.add_argument("--out", required=True, help="Output WAV file.")
    args = parser.parse_args()

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise SystemExit("MIMO_API_KEY is not set")

    reference = Path(args.reference).resolve()
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    voice_base64 = base64.b64encode(reference.read_bytes()).decode("ascii")

    client = OpenAI(api_key=api_key, base_url="https://api.xiaomimimo.com/v1")
    completion = client.chat.completions.create(
        model="mimo-v2.5-tts-voiceclone",
        messages=[
            {"role": "user", "content": ""},
            {"role": "assistant", "content": args.text},
        ],
        audio={
            "format": "wav",
            "voice": f"data:audio/wav;base64,{voice_base64}",
        },
    )
    audio_data = completion.choices[0].message.audio.data
    output.write_bytes(base64.b64decode(audio_data))
    print(f"wrote={output}")


if __name__ == "__main__":
    main()
