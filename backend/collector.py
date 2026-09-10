"""Public metadata, bounded downloads and best-effort comment collection."""

import http.cookiejar
import ipaddress
import json
import re
import socket
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import httpx
import yt_dlp
from . import config

PLATFORMS = {
    "douyin.com": "抖音",
    "bilibili.com": "哔哩哔哩",
    "b23.tv": "哔哩哔哩",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def normalize_url(text):
    # Stop at Markdown link delimiters as well as whitespace/punctuation.
    match = re.search(r'https?://[^\s<>"\[\]()，。]+', text)
    if not match:
        raise ValueError("请粘贴包含 https:// 的视频链接或分享文案")
    # Shared posts are often pasted as Markdown links. Brackets are
    # presentation syntax, not part of the URL.
    url = match.group(0).rstrip(".,;!）)]}>")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.username or parsed.password or parsed.port not in (None, 443, 80):
        raise ValueError("链接格式不受支持")
    if not any(host == d or host.endswith("." + d) for d in PLATFORMS):
        raise ValueError("目前支持抖音、哔哩哔哩和 YouTube 视频链接")
    if "douyin.com" in host:
        match = re.search(r"/video/(\d+)", parsed.path)
        video_id = (
            match.group(1) if match else parse_qs(parsed.query).get("modal_id", [""])[0]
        )
        if video_id.isdigit():
            return "https://www.douyin.com/video/" + video_id
    return url


def resolve_short_url(url):
    """Resolve a Douyin share URL; browser collection remains the fallback."""
    host = urlparse(url).hostname or ""
    if "v.douyin.com" not in host:
        return url
    try:
        with httpx.Client(follow_redirects=True, headers={"User-Agent": UA}, timeout=15) as client:
            return normalize_url(str(client.get(url).url))
    except Exception:
        return url


def platform(url):
    host = urlparse(url).hostname or ""
    return next(
        (
            label
            for domain, label in PLATFORMS.items()
            if host == domain or host.endswith("." + domain)
        ),
        "视频",
    )


def public_url(url):
    p = urlparse(url)
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("资源地址无效")
    host = p.hostname.lower()
    # Media is accepted only from platform-owned CDN domains, never arbitrary
    # attacker-controlled domains returned through redirects or metadata.
    cdns = (
        "douyin.com",
        "douyinvod.com",
        "douyinpic.com",
        "byteimg.com",
        "bytecdn.cn",
        "bytecdn.com",
        "pstatp.com",
        "snssdk.com",
        "ibytedtos.com",
        "bilivideo.com",
        "hdslb.com",
        "bilibili.com",
        "ytimg.com",
        "googlevideo.com",
        "youtube.com",
        "ggpht.com",
    )
    if not any(host == d or host.endswith("." + d) for d in cdns):
        raise ValueError("资源不在受支持平台的媒体域名中")
    for item in socket.getaddrinfo(
        p.hostname, p.port or (443 if p.scheme == "https" else 80)
    ):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("不允许访问内网资源地址")
    return url


def download_file(url, target, limit=config.MAX_BYTES):
    # Redirects are validated individually; no credentials are forwarded.
    with httpx.Client(
        timeout=60, headers={"User-Agent": UA, "Referer": "https://www.douyin.com/"}
    ) as client:
        for _ in range(6):
            public_url(url)
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin

                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                written = 0
                temp = target.with_suffix(target.suffix + ".part")
                try:
                    with temp.open("wb") as file:
                        for chunk in response.iter_bytes(65536):
                            written += len(chunk)
                            if written > limit:
                                raise ValueError("资源超过大小限制")
                            file.write(chunk)
                    temp.replace(target)
                finally:
                    temp.unlink(missing_ok=True)
                return
        raise ValueError("资源重定向次数过多")


def number(value):
    if isinstance(value, (int, float)) and value >= 0:
        return int(value)
    return None


def clean_info(info, url):
    views = number(info.get("view_count"))
    # Douyin frequently uses zero as an unavailable public play-count sentinel.
    if platform(url) == "抖音" and views == 0:
        views = None
    comments = []
    for item in (info.get("comments") or [])[:200]:
        comments.append(
            {
                "id": str(item.get("id", len(comments))),
                "author": str(item.get("author") or "用户"),
                "text": str(item.get("text") or "")[:4000],
                "likes": number(item.get("like_count")),
                "timestamp": item.get("timestamp"),
            }
        )
    return {
        "video_id": str(info.get("id", "")),
        "title": info.get("title") or "未命名视频",
        "description": info.get("description") or "",
        "author": info.get("uploader") or info.get("channel") or "平台未提供作者",
        "platform": platform(url),
        "source_url": url,
        "duration": info.get("duration"),
        "published_at": info.get("timestamp"),
        "collected_at": time.time(),
        "metrics": {
            "views": views,
            "likes": number(info.get("like_count")),
            "comments": number(info.get("comment_count")),
            "shares": number(info.get("repost_count")),
            "saves": number(info.get("save_count")),
        },
        "tags": (
            info.get("tags") or re.findall(r"#([^\s#]+)", info.get("title") or "")
        )[:20],
        "comments": comments,
        "comments_note": (
            "采集到的公开评论样本，不代表全部评论"
            if comments
            else "暂未取得评论内容；评论数量不等于已采集样本数"
        ),
    }


def cookie_path(url):
    name = (
        "douyin_cookies.txt"
        if platform(url) == "抖音"
        else (
            "youtube_mini_cookies.txt"
            if platform(url) == "YouTube"
            else "bilibili_cookies.txt"
        )
    )
    path = config.ROOT / name
    return path if path.exists() else None


class QuietLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def collect(url, folder):
    metadata = None
    warnings = []
    resolved_url = resolve_short_url(url)
    if platform(resolved_url) == "抖音":
        try:
            metadata = collect_douyin(resolved_url, folder)
            metadata["source_url"] = url
            metadata["resolved_url"] = resolved_url
        except Exception:
            warnings.append(
                "抖音页面采集未完成，已尝试下载器；如遇验证请在系统设置更新登录 Cookie"
            )
    if metadata is None:

        def bounds(info, *, incomplete=False):
            if (info.get("duration") or 0) > config.MAX_VIDEO_SECONDS:
                return "当前支持不超过 15 分钟的视频"
            return None

        def progress(event):
            if (event.get("downloaded_bytes") or 0) > config.MAX_BYTES:
                raise ValueError("视频超过 500MB 限制")

        options = {
            "outtmpl": str(folder / "video.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "logger": QuietLogger(),
            "format": "best[ext=mp4]/best",
            "socket_timeout": 30,
            "retries": 2,
            "max_filesize": config.MAX_BYTES,
            "match_filter": bounds,
            "progress_hooks": [progress],
            "getcomments": True,
            "extractor_args": {
                "youtube": {"max_comments": ["200"]},
                "bilibili": {"max_comments": ["200"]},
            },
            "overwrites": False,
        }
        cookie = cookie_path(url)
        if cookie:
            options["cookiefile"] = str(cookie)
        with yt_dlp.YoutubeDL(options) as dl:
            info = dl.extract_info(url, download=True)
        if not info:
            raise ValueError("未取得视频，请检查链接或更新平台登录 Cookie")
        metadata = clean_info(info, url)
        metadata["resolved_url"] = resolved_url
        cover = info.get("thumbnail")
        if cover:
            try:
                download_file(cover, folder / "cover.jpg", 15 * 1024 * 1024)
            except Exception:
                warnings.append("原封面下载失败，已改用视频首帧")
    metadata["warnings"] = warnings
    return metadata


def collect_douyin(url, folder):
    from playwright.sync_api import sync_playwright

    detail, comments = {}, {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1440, "height": 1000}
        )
        cookie = cookie_path(url)
        if cookie:
            jar = http.cookiejar.MozillaCookieJar(str(cookie))
            jar.load(ignore_discard=True, ignore_expires=True)
            context.add_cookies(
                [
                    {
                        "name": c.name,
                        "value": c.value or "",
                        "domain": c.domain,
                        "path": c.path or "/",
                        "secure": bool(c.secure),
                    }
                    for c in jar
                    if (
                        c.domain.lstrip(".") == "douyin.com"
                        or c.domain.endswith(".douyin.com")
                    )
                    and c.name
                ]
            )
        page = context.new_page()

        def response_handler(response):
            try:
                if "/aweme/detail/" in response.url:
                    body = response.json().get("aweme_detail")
                    if body:
                        detail.update(body)
                elif "/comment/list/" in response.url:
                    for item in response.json().get("comments") or []:
                        comments[str(item.get("cid"))] = {
                            "id": str(item.get("cid")),
                            "text": str(item.get("text", ""))[:4000],
                            "author": (item.get("user") or {}).get("nickname", "用户"),
                            "likes": number(item.get("digg_count")),
                            "timestamp": item.get("create_time"),
                        }
            except Exception:
                pass

        page.on("response", response_handler)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            for _ in range(12):
                page.wait_for_timeout(1000)
                if detail:
                    break
            if not detail:
                raw = page.locator("script#RENDER_DATA").text_content(timeout=3000)
                from urllib.parse import unquote

                tree = json.loads(unquote(raw or "{}"))
                expected = re.search(r"/video/(\d+)", page.url)

                def find(node):
                    if isinstance(node, dict):
                        if (
                            "aweme_id" in node
                            and "video" in node
                            and (
                                not expected
                                or str(node["aweme_id"]) == expected.group(1)
                            )
                        ):
                            return node
                        for value in node.values():
                            found = find(value)
                            if found:
                                return found
                    if isinstance(node, list):
                        for value in node:
                            found = find(value)
                            if found:
                                return found

                detail.update(find(tree) or {})
            for _ in range(4):
                if len(comments) >= 100:
                    break
                page.mouse.move(1250, 700)
                page.mouse.wheel(0, 700)
                page.wait_for_timeout(800)
        finally:
            browser.close()
    if not detail:
        raise ValueError("抖音未返回公开视频详情")
    video, stats = detail.get("video", {}), detail.get("statistics", {})
    duration = (video.get("duration") or 0) / 1000
    if duration > config.MAX_VIDEO_SECONDS:
        raise ValueError("当前支持不超过 15 分钟的视频")
    urls = video.get("play_addr", {}).get("url_list") or []
    for rate in sorted(
        video.get("bit_rate") or [], key=lambda r: r.get("bit_rate", 0), reverse=True
    ):
        urls = rate.get("play_addr", {}).get("url_list") or urls
        if urls:
            break
    if not urls:
        raise ValueError("没有可下载的视频资源")
    download_file(urls[0], folder / "video.mp4")
    covers = video.get("cover", {}).get("url_list") or []
    if covers:
        try:
            download_file(covers[0], folder / "cover.jpg", 15 * 1024 * 1024)
        except Exception:
            pass
    result = clean_info(
        {
            "id": detail.get("aweme_id"),
            "title": detail.get("desc"),
            "uploader": (detail.get("author") or {}).get("nickname"),
            "duration": duration,
            "timestamp": detail.get("create_time"),
            "view_count": stats.get("play_count"),
            "like_count": stats.get("digg_count"),
            "comment_count": stats.get("comment_count"),
            "repost_count": stats.get("share_count"),
            "save_count": stats.get("collect_count"),
        },
        url,
    )
    result["comments"] = list(comments.values())[:200]
    if comments:
        result["comments_note"] = "页面采集的公开评论样本，不代表全部评论"
    return result
