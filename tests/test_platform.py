import json
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from backend import config, store, security
from backend.main import app
from backend.collector import normalize_url, clean_info
from backend.analysis import ratios, safe_report, comment_insights
from scripts.asr_utils import group_timestamp_items


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "MEDIA", tmp_path / "media")
    monkeypatch.setattr(config, "DB", tmp_path / "db.sqlite3")
    monkeypatch.setenv("PIANXI_NO_WORKER", "1")
    store.init()
    security.create_user("admin", "管理员", "admin-password", "admin")
    security.create_user("member", "成员", "member-password")
    with TestClient(app) as c:
        yield c


def login(c, role="admin"):
    response = c.post(
        "/api/auth/login", json={"username": role, "password": role + "-password"}
    )
    assert response.status_code == 200
    return response.json()


def test_auth_and_team_boundaries(client):
    assert client.get("/api/jobs").status_code == 401
    login(client, "member")
    assert client.get("/api/settings").status_code == 403
    assert (
        client.post(
            "/api/team",
            json={"username": "new", "password": "long-password", "name": "新成员"},
        ).status_code
        == 403
    )
    job = client.post(
        "/api/jobs", json={"url": "https://www.douyin.com/video/12345"}
    ).json()
    assert client.get("/api/jobs/" + job["id"]).status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/jobs/" + job["id"]).status_code == 401


def test_create_disable_member_revokes_session(client):
    login(client)
    user = client.post(
        "/api/team",
        json={"username": "editor", "password": "editor-password", "name": "编辑"},
    ).json()
    with TestClient(app) as member:
        assert (
            member.post(
                "/api/auth/login",
                json={"username": "editor", "password": "editor-password"},
            ).status_code
            == 200
        )
        assert member.get("/api/jobs").status_code == 200
        assert (
            client.patch("/api/team/" + user["id"], json={"active": False}).status_code
            == 200
        )
        assert member.get("/api/jobs").status_code == 401


def test_csrf_and_url_validation(client):
    login(client)
    assert (
        client.post(
            "/api/jobs",
            json={"url": "https://www.douyin.com/video/123"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/jobs", json={"url": "http://127.0.0.1:1234/private"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/jobs", json={"url": "https://douyin.com.evil.test/video/123"}
        ).status_code
        == 400
    )
    assert (
        normalize_url("复制链接 https://www.douyin.com/user/a?modal_id=12345 到浏览器")
        == "https://www.douyin.com/video/12345"
    )
    shared = """0.53 12/07 odA:/ :9pm i\\@P.Kj 第1集：《东北妹子穿书恶毒女配，征服了韩国贵族学院》
东北大妹子一觉醒来穿进韩国校园小说，还成了活不过三集的恶毒女配。
#校园 #甜宠 [https://v.douyin.com/P88u4n8WnOs/](https://v.douyin.com/P88u4n8WnOs/) 复制此链接，打开Dou音搜索，直接观看视频！"""
    assert normalize_url(shared) == "https://v.douyin.com/P88u4n8WnOs/"


def test_unknown_metrics_and_zero_denominators():
    result = clean_info(
        {"view_count": 0, "like_count": 0, "comment_count": 7},
        "https://www.douyin.com/video/123",
    )
    assert result["metrics"]["views"] is None
    assert result["metrics"]["likes"] == 0
    assert all(
        v is None for v in ratios({"views": 0, "likes": 0, "comments": None}).values()
    )
    assert ratios({"views": 100, "likes": 20})["like_rate"] == 20


def test_resource_allowlist_and_download(client):
    current = login(client)
    job_id = uuid.uuid4().hex
    folder = config.MEDIA / job_id
    folder.mkdir()
    (folder / "video.mp4").write_bytes(b"actual-media")
    (folder / "model.log").write_text("private debug log")
    now = time.time()
    with store.connect() as con:
        con.execute(
            "INSERT INTO jobs(id,url,owner,status,stage,created,updated,payload) VALUES(?,?,?,?,?,?,?,?)",
            (
                job_id,
                "https://www.douyin.com/video/123",
                current["id"],
                "done",
                "done",
                now,
                now,
                json.dumps({"video_file": "video.mp4"}),
            ),
        )
    response = client.get(f"/api/jobs/{job_id}/assets/video.mp4?download=true")
    assert response.content == b"actual-media"
    assert "attachment" in response.headers["content-disposition"]
    assert client.get(f"/api/jobs/{job_id}/assets/model.log").status_code == 404
    client.post("/api/auth/logout")
    assert client.get(f"/api/jobs/{job_id}/assets/video.mp4").status_code == 401


def test_secrets_never_returned(client):
    login(client)
    response = client.put(
        "/api/settings",
        json={
            "team_name": "团队",
            "provider": "api",
            "base_url": "https://example.com/v1",
            "model": "vision",
            "api_key": "secret-test-key",
        },
    )
    assert response.status_code == 200
    result = client.get("/api/settings")
    assert result.json()["has_api_key"] is True
    assert "secret-test-key" not in result.text
    client.put(
        "/api/settings",
        json={
            "team_name": "团队",
            "provider": "api",
            "base_url": "https://example.com/v1",
            "model": "vision",
        },
    )
    assert store.setting("api_key") == "secret-test-key"


def test_cloud_vlm_smoke_test_uses_multimodal_endpoint(client, monkeypatch):
    login(client)
    client.put(
        "/api/settings",
        json={
            "team_name": "团队",
            "provider": "api",
            "base_url": "https://vision.example/v1",
            "model": "vision-model",
            "api_key": "secret-test-key",
        },
    )

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "OK"}}]}

    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)
    response = client.post("/api/settings/test")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["kind"] == "api"
    assert captured["url"] == "https://vision.example/v1/chat/completions"
    assert any(
        item["type"] == "image_url"
        for item in captured["json"]["messages"][0]["content"]
    )
    assert "secret-test-key" not in response.text


def test_cloud_vlm_smoke_test_reports_errors(client, monkeypatch):
    login(client)
    client.put(
        "/api/settings",
        json={
            "team_name": "团队",
            "provider": "api",
            "base_url": "https://vision.example/v1",
            "model": "vision-model",
            "api_key": "secret-test-key",
        },
    )

    class Response:
        def __init__(self, code, body=None):
            self.status_code, self.body = code, body or {}

        def json(self):
            return self.body

    monkeypatch.setattr("httpx.post", lambda *a, **k: Response(401))
    assert "鉴权失败" in client.post("/api/settings/test").json()["message"]
    monkeypatch.setattr("httpx.post", lambda *a, **k: Response(200, {"choices": []}))
    assert "返回格式" in client.post("/api/settings/test").json()["message"]


def test_password_change_invalidates_sessions(client):
    login(client)
    assert (
        client.post(
            "/api/auth/password",
            json={"old_password": "wrong", "new_password": "new-password"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/password",
            json={"old_password": "admin-password", "new_password": "new-password"},
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": "new-password"}
        ).status_code
        == 200
    )


def test_model_report_filters_invalid_segments():
    report = safe_report(
        {
            "summary": "测试",
            "factors": [],
            "structure": [
                {
                    "start": -1,
                    "end": 5,
                    "text": "假",
                    "role": "开场",
                    "analysis": "错误",
                },
                {
                    "start": 0,
                    "end": 3,
                    "text": "原文",
                    "role": "开场",
                    "analysis": "判断",
                    "emotion": 99,
                },
            ],
        },
        {"duration": 10, "transcript": {"text": "原文"}},
    )
    assert len(report["structure"]) == 1
    assert report["structure"][0]["emotion"] is None


def test_comment_counts_use_samples_only():
    comments = [{"text": "求链接教程"}, {"text": "哈哈真实"}, {"text": "没有标签"}]
    result = comment_insights(comments)
    assert result["sample_size"] == 3
    assert sum(i["count"] for i in result["intents"]) == 3


def test_job_dedup_and_retry(client):
    login(client)
    first = client.post(
        "/api/jobs", json={"url": "https://www.douyin.com/video/123"}
    ).json()
    second = client.post(
        "/api/jobs", json={"url": "https://www.douyin.com/video/123"}
    ).json()
    assert first == second
    assert client.post("/api/jobs/" + first["id"] + "/retry").status_code == 409
    store.update(first["id"], status="partial")
    assert client.post("/api/jobs/" + first["id"] + "/retry").status_code == 202


def test_report_uses_source_quote_and_intervals():
    result = {
        "duration": 20,
        "transcript": {
            "text": "原始开场。后续内容。",
            "timing": "aligned",
            "segments": [
                {"start": 0, "end": 4, "text": "原始开场。"},
                {"start": 8, "end": 12, "text": "后续内容。"},
            ],
        },
    }
    report = safe_report(
        {
            "summary": "总结",
            "factors": [],
            "hook": {"quote": "模型编造的开场", "analysis": "判断"},
            "structure": [
                {
                    "start": 2,
                    "end": 6,
                    "text": "后续内容。",
                    "role": "展开",
                    "analysis": "解释",
                }
            ],
        },
        result,
    )
    assert report["hook"]["quote"] == "原始开场。"
    assert report["structure"][0]["start"] == 8
    assert report["structure"][0]["end"] == 12


def test_english_timestamp_groups_keep_word_spaces():
    class Word:
        def __init__(self, text, start, end):
            self.text, self.start_time, self.end_time = text, start, end

    result = group_timestamp_items(
        [Word("Some", 0, 0.2), Word("girls", 0.2, 0.4), Word("can", 0.4, 0.6)],
        language="English",
    )
    assert result == ["[0.0s -> 0.6s] Some girls can"]


def test_admin_can_delete_completed_job(client):
    login(client)
    ident = client.post(
        "/api/jobs", json={"url": "https://www.douyin.com/video/567"}
    ).json()["id"]
    assert client.delete("/api/jobs/" + ident).status_code == 409
    store.update(ident, status="done")
    folder = config.MEDIA / ident
    folder.mkdir()
    (folder / "cover.jpg").write_bytes(b"image")
    assert client.delete("/api/jobs/" + ident).status_code == 200
    assert not folder.exists()
    assert client.get("/api/jobs/" + ident).status_code == 404


def test_interrupted_media_keeps_last_complete_file(tmp_path, monkeypatch):
    from backend import media

    target = tmp_path / "audio.wav"
    target.write_bytes(b"complete audio")

    def interrupted(args, timeout):
        from pathlib import Path

        Path(args[-1]).write_bytes(b"partial")
        raise RuntimeError("simulated ffmpeg interruption")

    monkeypatch.setattr(media, "run", interrupted)
    with pytest.raises(RuntimeError):
        media.atomic_media(["ffmpeg"], target)
    assert target.read_bytes() == b"complete audio"
    assert not (tmp_path / "audio.pending.wav").exists()
