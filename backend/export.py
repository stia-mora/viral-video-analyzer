import json


def markdown(job):
    r = job["result"]
    a = r.get("analysis", {})
    t = r.get("transcript", {})
    lines = [
        f"# {r.get('title','视频分析')}",
        "",
        f"来源：{r.get('source_url',job['url'])}",
        f"作者：{r.get('author','未提供')} · 平台：{r.get('platform','')}",
        "",
        "## 数据快照",
        "",
    ]
    names = {
        "views": "播放",
        "likes": "点赞",
        "comments": "评论",
        "shares": "分享",
        "saves": "收藏",
    }
    for k, v in r.get("metrics", {}).items():
        lines.append(f"- {names.get(k,k)}：{v if v is not None else '未提供'}")
    lines += [
        "",
        "## 核心判断",
        "",
        a.get("summary", ""),
        "",
        "## 开场钩子",
        "",
        a.get("hook", {}).get("quote", ""),
        "",
        a.get("hook", {}).get("analysis", ""),
        "",
        "## 爆点因素",
        "",
    ]
    for f in a.get("factors", []):
        lines += [
            f"### {f['title']}",
            "",
            f"证据：{f['evidence']}",
            "",
            f["explanation"],
            "",
        ]
    lines += ["## 秒级结构", ""]
    for s in a.get("structure", []):
        lines += [
            f"### {s['start']}–{s['end']} 秒 · {s['role']}",
            "",
            s["text"],
            "",
            s["analysis"],
            "",
        ]
    lines += ["## 可复用公式", "", a.get("formula", ""), "", "## 改进建议", ""] + [
        "- " + s for s in a.get("suggestions", [])
    ]
    lines += ["", "## 评论洞察", "", r.get("comments_note", ""), ""]
    for i in r.get("comment_insights", {}).get("intents", []):
        lines.append(f"- {i['label']}：{i['count']} 条；样本：{i['example']}")
    lines += [
        "",
        "## 完整文案",
        "",
        t.get("text", "未取得文案"),
        "",
        "## 分析限制",
        "",
    ] + ["- " + s for s in a.get("limitations", [])]
    return "\n".join(lines) + "\n"
