from typing import Iterable, List, Optional


def group_timestamp_items(
    items: Iterable[object], max_chars: int = 42, language: Optional[str] = None
) -> List[str]:
    lines: List[str] = []
    buf: List[str] = []
    start: Optional[float] = None
    end: Optional[float] = None
    hard_breaks = set("。！？!?；;\n")
    joiner = " " if (language or "").lower() in {"english", "en"} else ""
    for item in items:
        text = str(getattr(item, "text", "") or "")
        if not text:
            continue
        item_start = float(getattr(item, "start_time", 0.0) or 0.0)
        item_end = float(getattr(item, "end_time", item_start) or item_start)
        if start is None:
            start = item_start
        end = item_end
        buf.append(text)
        joined = joiner.join(buf).strip()
        if joined and (joined[-1] in hard_breaks or len(joined) >= max_chars):
            lines.append(f"[{start:.1f}s -> {end:.1f}s] {joined}")
            buf, start, end = [], None, None
    if buf and start is not None and end is not None:
        joined = joiner.join(buf).strip()
        if joined:
            lines.append(f"[{start:.1f}s -> {end:.1f}s] {joined}")
    return lines
