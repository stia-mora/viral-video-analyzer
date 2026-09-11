import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import config, store, security, collector
from .export import markdown
from .worker import worker, STAGES


@asynccontextmanager
async def lifespan(app):
    store.init()
    if os.environ.get("PIANXI_NO_WORKER") != "1":
        worker.start()
    yield
    worker.stop()


app = FastAPI(
    title="片析 · 视频研究工作台",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)


@app.middleware("http")
async def same_origin(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "请求来源不匹配"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "不接受跨站请求"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class NewUser(Login):
    name: str = Field(min_length=1, max_length=64)
    role: str = "member"


class PasswordChange(BaseModel):
    old_password: str = Field(max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class JobInput(BaseModel):
    url: str = Field(min_length=1, max_length=4000)


class SettingsInput(BaseModel):
    team_name: str = Field(default="创作研究室", min_length=1, max_length=64)
    provider: str = "local"
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    api_key: str | None = Field(default=None, max_length=2000)
    asr_provider: str = "auto"
    asr_base_url: str = Field(default="https://api.siliconflow.cn/v1", max_length=500)
    asr_model: str = Field(default="XingChenAGI/XingChenASR-V3.2-Ultra", max_length=200)
    asr_api_key: str | None = Field(default=None, max_length=2000)


def get_job(job_id):
    job = store.job(job_id)
    if not job:
        raise HTTPException(404, "视频不存在")
    return job


@app.post("/api/auth/login")
def login(data: Login, request: Request, response: Response):
    identity = (
        (request.client.host if request.client else "") + ":" + data.username.lower()
    )
    now = time.time()
    with store.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM login_attempts WHERE started<?", (now - 600,))
        hits = con.execute(
            "SELECT hits FROM login_attempts WHERE identity=?", (identity,)
        ).fetchone()
        if hits and hits["hits"] >= 10:
            raise HTTPException(429, "尝试次数过多，请 10 分钟后重试")
        con.execute(
            "INSERT INTO login_attempts VALUES(?,?,1) ON CONFLICT(identity) DO UPDATE SET hits=hits+1",
            (identity, now),
        )
        row = con.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (data.username,)
        ).fetchone()
    if not row or not security.verify_password(data.password, row["password"]):
        raise HTTPException(401, "账号或密码不正确")
    token = secrets.token_urlsafe(32)
    with store.connect() as con:
        con.execute("DELETE FROM login_attempts WHERE identity=?", (identity,))
        con.execute("DELETE FROM sessions WHERE expires<?", (now,))
        con.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), row["id"], now + 7 * 86400),
        )
    response.set_cookie(
        "pianxi_session",
        token,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("PIANXI_HTTPS") == "1",
        max_age=7 * 86400,
    )
    return {k: row[k] for k in ["id", "username", "name", "role"]}


@app.get("/api/auth/me")
def me(current=Depends(security.user)):
    return current | {"team_name": store.setting("team_name", "创作研究室")}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, current=Depends(security.user)):
    with store.connect() as con:
        con.execute(
            "DELETE FROM sessions WHERE token=?",
            (
                hashlib.sha256(
                    request.cookies.get("pianxi_session", "").encode()
                ).hexdigest(),
            ),
        )
    response.delete_cookie("pianxi_session")
    return {"ok": True}


@app.post("/api/auth/password")
def password(data: PasswordChange, current=Depends(security.user)):
    with store.connect() as con:
        row = con.execute(
            "SELECT password FROM users WHERE id=?", (current["id"],)
        ).fetchone()
        if not security.verify_password(data.old_password, row["password"]):
            raise HTTPException(400, "原密码不正确")
        con.execute(
            "UPDATE users SET password=? WHERE id=?",
            (security.hash_password(data.new_password), current["id"]),
        )
        con.execute("DELETE FROM sessions WHERE user_id=?", (current["id"],))
    bootstrap = config.DATA / "first-login.txt"
    if current["username"] == "admin":
        bootstrap.unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/team")
def team(current=Depends(security.admin)):
    with store.connect() as con:
        return [
            dict(r)
            for r in con.execute(
                "SELECT id,username,name,role,active,created FROM users ORDER BY created"
            )
        ]


@app.post("/api/team", status_code=201)
def add_member(data: NewUser, current=Depends(security.admin)):
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", data.username):
        raise HTTPException(400, "账号使用 3–64 位字母、数字或 . _ @ -")
    if len(data.password) < 10:
        raise HTTPException(400, "密码至少 10 位")
    if data.role not in ("admin", "member"):
        raise HTTPException(400, "角色无效")
    try:
        uid = security.create_user(data.username, data.name, data.password, data.role)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "账号已经存在")
    return {"id": uid}


class MemberState(BaseModel):
    active: bool


@app.patch("/api/team/{user_id}")
def member_state(user_id: str, data: MemberState, current=Depends(security.admin)):
    if user_id == current["id"]:
        raise HTTPException(400, "不能停用当前账号")
    with store.connect() as con:
        if not con.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(404, "成员不存在")
        con.execute("UPDATE users SET active=? WHERE id=?", (int(data.active), user_id))
        con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return {"ok": True}


@app.get("/api/settings")
def settings(current=Depends(security.admin)):
    s = store.settings()
    return {
        "team_name": s.get("team_name", "创作研究室"),
        "provider": s.get("provider", "local"),
        "base_url": s.get("base_url", ""),
        "model": s.get("model", ""),
        "has_api_key": bool(s.get("api_key")),
        "asr_provider": s.get("asr_provider", "auto"),
        "asr_base_url": s.get("asr_base_url", "https://api.siliconflow.cn/v1"),
        "asr_model": s.get("asr_model", "XingChenAGI/XingChenASR-V3.2-Ultra"),
        "has_asr_api_key": bool(s.get("asr_api_key")),
        "local_model": "Qwen3-VL-2B-Instruct",
        "cookies": {
            p: bool(collector.cookie_path(url))
            for p, url in [
                ("抖音", "https://www.douyin.com/"),
                ("YouTube", "https://www.youtube.com/"),
                ("哔哩哔哩", "https://www.bilibili.com/"),
            ]
        },
    }


@app.put("/api/settings")
def update_settings(data: SettingsInput, current=Depends(security.admin)):
    if data.provider not in ("local", "api"):
        raise HTTPException(400, "模型类型无效")
    if data.base_url:
        parsed = urlparse(data.base_url)
        if (
            parsed.scheme not in ("https", "http")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(
                400, "模型地址需为 HTTP(S) API 根地址，例如 https://example.com/v1"
            )
        if parsed.scheme == "http" and parsed.hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            raise HTTPException(400, "远程模型地址必须使用 HTTPS")
    if data.asr_provider not in ("auto", "local", "cloud"):
        raise HTTPException(400, "ASR 模式无效")
    if data.asr_base_url:
        asr_url = urlparse(data.asr_base_url)
        if (
            asr_url.scheme not in ("https", "http")
            or not asr_url.hostname
            or asr_url.username
            or asr_url.password
            or asr_url.query
            or asr_url.fragment
        ):
            raise HTTPException(400, "ASR 地址需为 HTTP(S) API 根地址")
        if asr_url.scheme == "http" and asr_url.hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            raise HTTPException(400, "远程 ASR 地址必须使用 HTTPS")
    values = data.model_dump(exclude_none=True)
    store.save_settings(values)
    return {"ok": True}


@app.post("/api/settings/test")
def test_settings(current=Depends(security.admin)):
    import httpx

    started = time.perf_counter()

    if store.setting("provider", "local") == "local":
        path = Path(
            store.setting("local_model", str(config.ROOT / ".hf-cache/vision-model"))
        )
        ok = (path / "config.json").exists() and any(path.glob("*.safetensors"))
        return {
            "ok": ok,
            "message": "本地模型文件已就绪" if ok else "本地模型尚未下载完成",
            "kind": "local",
        }
    base_url = store.setting("base_url").rstrip("/")
    model = store.setting("model").strip()
    key = store.setting("api_key")
    if not base_url or not model:
        return {
            "ok": False,
            "kind": "api",
            "message": "请先保存 API 地址和视觉模型名称",
        }

    test_image = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVQIHWP4z8DwHwAFgAI/Sc4eGQAAAABJRU5ErkJggg=="
    )
    headers = {"Authorization": "Bearer " + key} if key else {}
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张图片，并只回复 OK。"},
                    {"type": "image_url", "image_url": {"url": test_image}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 8,
    }
    try:
        response = httpx.post(
            base_url + "/chat/completions", headers=headers, json=payload, timeout=45
        )
    except httpx.TimeoutException:
        return {"ok": False, "kind": "api", "message": "云端 VLM 请求超时（45 秒）"}
    except httpx.HTTPError:
        return {
            "ok": False,
            "kind": "api",
            "message": "无法连接云端 VLM，请检查地址和网络",
        }
    if response.status_code in (401, 403):
        return {
            "ok": False,
            "kind": "api",
            "message": "云端 VLM 鉴权失败，请检查 API Key",
        }
    if response.status_code == 404:
        return {
            "ok": False,
            "kind": "api",
            "message": "找不到视觉接口或模型，请检查 API 地址和模型名称",
        }
    if response.status_code >= 400:
        return {
            "ok": False,
            "kind": "api",
            "message": f"云端 VLM 返回 HTTP {response.status_code}",
        }
    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = " ".join(
                str(item.get("text", "")) for item in content if isinstance(item, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError
    except (ValueError, KeyError, IndexError, TypeError):
        return {
            "ok": False,
            "kind": "api",
            "message": "云端返回格式不是兼容的 Chat Completions 响应",
        }
    elapsed = round((time.perf_counter() - started) * 1000)
    return {
        "ok": True,
        "kind": "api",
        "message": f"云端 VLM 可用 · {model} · {elapsed} ms",
    }


@app.post("/api/settings/test-asr")
def test_asr_settings(current=Depends(security.admin)):
    """Test the configured cloud ASR with a tiny generated WAV file."""
    import io, wave, httpx

    mode = store.setting("asr_provider", "auto")
    if mode == "local":
        return {
            "ok": Path(config.ASR_PYTHON).exists(),
            "kind": "local",
            "message": (
                "本地 ASR 环境已找到"
                if Path(config.ASR_PYTHON).exists()
                else "本地 ASR 环境不存在"
            ),
        }
    endpoint = store.setting("asr_base_url", "https://api.siliconflow.cn/v1").rstrip(
        "/"
    )
    model = store.setting("asr_model", "XingChenAGI/XingChenASR-V3.2-Ultra")
    key = store.setting("asr_api_key")
    if not key:
        return {"ok": False, "kind": "cloud", "message": "请先保存云端 ASR API Key"}
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 1600)
    try:
        response = httpx.post(
            endpoint + "/audio/transcriptions",
            headers={"Authorization": "Bearer " + key},
            files={"file": ("test.wav", audio.getvalue(), "audio/wav")},
            data={"model": model},
            timeout=httpx.Timeout(90, connect=20),
        )
    except httpx.TimeoutException:
        return {"ok": False, "kind": "cloud", "message": "云端 ASR 请求超时（90 秒）"}
    except httpx.HTTPError:
        return {
            "ok": False,
            "kind": "cloud",
            "message": "无法连接云端 ASR，请检查地址和网络",
        }
    if response.status_code in (401, 403):
        return {
            "ok": False,
            "kind": "cloud",
            "message": "云端 ASR 鉴权失败，请检查 API Key",
        }
    if response.status_code >= 400:
        return {
            "ok": False,
            "kind": "cloud",
            "message": f"云端 ASR 返回 HTTP {response.status_code}，请检查模型名称",
        }
    try:
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("text"), str):
            raise ValueError
    except (ValueError, TypeError):
        return {
            "ok": False,
            "kind": "cloud",
            "message": "云端 ASR 返回格式不兼容，缺少 text 字段",
        }
    return {"ok": True, "kind": "cloud", "message": f"云端 ASR 可用 · {model}"}


class CookiesInput(BaseModel):
    platform: str
    content: str = Field(min_length=1, max_length=100000)


@app.put("/api/settings/cookies")
def cookies(data: CookiesInput, current=Depends(security.admin)):
    paths = {
        "抖音": "douyin_cookies.txt",
        "YouTube": "youtube_mini_cookies.txt",
        "哔哩哔哩": "bilibili_cookies.txt",
    }
    if data.platform not in paths:
        raise HTTPException(400, "不支持的平台")
    if "Netscape HTTP Cookie File" not in data.content:
        raise HTTPException(400, "请使用 Netscape 格式 Cookie 文件内容")
    (config.ROOT / paths[data.platform]).write_text(data.content, encoding="utf-8")
    return {"ok": True}


@app.get("/api/health")
def health(current=Depends(security.user)):
    return {
        "ok": True,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "asr": Path(config.ASR_PYTHON).exists(),
        "model": (config.ROOT / ".hf-cache/vision-model/config.json").exists(),
        "stages": STAGES,
    }


@app.get("/api/policy")
def policy(current=Depends(security.user)):
    external = store.setting("provider", "local") == "api"
    return {
        "provider": "api" if external else "local",
        "destination": (
            urlparse(store.setting("base_url")).hostname if external else "本机"
        ),
        "model": store.setting("model") if external else "Qwen3-VL-2B-Instruct",
    }


def enqueue(url, owner):
    with store.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        used = sum(p.stat().st_size for p in config.MEDIA.rglob("*") if p.is_file())
        if used > 20 * 1024**3 or shutil.disk_usage(config.DATA).free < 2 * 1024**3:
            raise HTTPException(507, "素材空间不足，请管理员删除不需要的视频后重试")
        count = con.execute(
            "SELECT count(*) FROM jobs WHERE status IN ('queued','running')"
        ).fetchone()[0]
        if count >= 20:
            raise HTTPException(429, "队列已满，请等待现有任务完成")
        existing = con.execute(
            "SELECT id FROM jobs WHERE url=? AND status IN ('queued','running')", (url,)
        ).fetchone()
        if existing:
            return {"id": existing["id"]}
        job_id = uuid.uuid4().hex
        now = time.time()
        con.execute(
            "INSERT INTO jobs(id,url,owner,status,stage,created,updated) VALUES(?,?,?,?,?,?,?)",
            (job_id, url, owner, "queued", "queued", now, now),
        )
    worker.wake.set()
    return {"id": job_id}


@app.post("/api/jobs", status_code=202)
def new_job(data: JobInput, current=Depends(security.user)):
    try:
        url = collector.normalize_url(data.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return enqueue(url, current["id"])


@app.get("/api/jobs")
def list_jobs(
    q: str = "", status: str = "", page: int = 1, current=Depends(security.user)
):
    page = max(1, page)
    clauses = ["1=1"]
    args = []
    if q:
        clauses.append("(j.payload LIKE ? OR j.url LIKE ?)")
        args += ["%" + q[:100] + "%"] * 2
    if status:
        clauses.append("j.status=?")
        args.append(status)
    where = " AND ".join(clauses)
    with store.connect() as con:
        total = con.execute(
            "SELECT count(*) FROM jobs j WHERE " + where, args
        ).fetchone()[0]
        rows = con.execute(
            "SELECT j.*,u.name owner_name FROM jobs j JOIN users u ON u.id=j.owner WHERE "
            + where
            + " ORDER BY j.created DESC LIMIT 24 OFFSET ?",
            (*args, (page - 1) * 24),
        ).fetchall()
        counts = dict(
            con.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall()
        )
    jobs = []
    for row in rows:
        job = store.unpack(row)
        r = job["result"]
        job["result"] = {
            k: r.get(k)
            for k in [
                "title",
                "author",
                "platform",
                "duration",
                "metrics",
                "cover_file",
                "analysis",
                "imported",
            ]
        }
        if r.get("analysis"):
            job["result"]["analysis"] = {
                "summary": r["analysis"].get("summary"),
                "mode": r["analysis"].get("mode"),
            }
        jobs.append(job)
    return {"items": jobs, "total": total, "page": page, "counts": counts}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str, current=Depends(security.user)):
    return get_job(job_id)


@app.post("/api/jobs/{job_id}/retry", status_code=202)
def retry(job_id: str, current=Depends(security.user)):
    with store.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "视频不存在")
        if row["status"] in ("running", "queued"):
            raise HTTPException(409, "任务正在处理中")
        con.execute(
            "UPDATE jobs SET status='queued',stage='queued',error=NULL,updated=? WHERE id=?",
            (time.time(), job_id),
        )
    worker.wake.set()
    return {"id": job_id}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, current=Depends(security.admin)):
    with store.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "视频不存在")
        if row["status"] in ("running", "queued"):
            raise HTTPException(409, "不能删除处理中的视频")
        folder = (config.MEDIA / job_id).resolve()
        if folder.is_relative_to(config.MEDIA.resolve()) and folder.is_dir():
            shutil.rmtree(folder)
        con.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    return {"ok": True}


class TranscriptInput(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


@app.put("/api/jobs/{job_id}/transcript")
def edit_transcript(job_id: str, data: TranscriptInput, current=Depends(security.user)):
    job = get_job(job_id)
    if job["status"] in ("running", "queued"):
        raise HTTPException(409, "处理完成后才能编辑文案")
    r = job["result"]
    r["transcript"] = {
        "text": data.text,
        "segments": [],
        "timing": "manual",
        "note": "团队手动校正的全文，未提供句级时间对齐",
    }
    # Invalidate old analysis immediately; next worker run regenerates the report.
    r.pop("analysis", None)
    store.update(job_id, result=r, status="queued", stage="queued")
    worker.wake.set()
    return {"ok": True}


@app.get("/api/library/local")
def local_library(current=Depends(security.admin)):
    items = []
    for path in (config.ROOT / "outputs").glob("*/*/video.info.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "path": path.parent.relative_to(config.ROOT / "outputs").as_posix(),
                    "title": d.get("title", path.parent.name),
                    "duration": d.get("duration"),
                }
            )
        except (ValueError, OSError):
            continue
    return items[:100]


@app.post("/api/library/import", status_code=202)
def import_local(data: JobInput, current=Depends(security.admin)):
    path = (config.ROOT / "outputs" / data.url).resolve()
    if (
        not path.is_relative_to((config.ROOT / "outputs").resolve())
        or not (path / "video.info.json").is_file()
    ):
        raise HTTPException(400, "本地资源不存在")
    return enqueue(
        "local:" + path.relative_to(config.ROOT / "outputs").as_posix(), current["id"]
    )


@app.get("/api/jobs/{job_id}/assets/{asset:path}")
def asset(
    job_id: str, asset: str, download: bool = False, current=Depends(security.user)
):
    job = get_job(job_id)
    r = job["result"]
    allowed = {r.get("video_file"), r.get("playback_file"), r.get("cover_file")} | {
        f["file"] for f in r.get("frames", [])
    }
    folder = (config.MEDIA / job_id).resolve()
    path = (folder / asset).resolve()
    if asset not in allowed or not path.is_relative_to(folder) or not path.is_file():
        raise HTTPException(404, "资源不存在")
    return FileResponse(path, filename=path.name if download else None)


@app.get("/api/jobs/{job_id}/export")
def export(job_id: str, format: str = "markdown", current=Depends(security.user)):
    job = get_job(job_id)
    if format == "json":
        return Response(
            json.dumps(job, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="analysis-{job_id[:8]}.json"'
            },
        )
    return Response(
        markdown(job),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="analysis-{job_id[:8]}.md"'
        },
    )


frontend = config.ROOT / "frontend/dist"
if frontend.exists():
    app.mount(
        "/assets", StaticFiles(directory=frontend / "assets"), name="frontend-assets"
    )

    @app.get("/{path:path}")
    def index(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        return FileResponse(frontend / "index.html")
