import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  Download,
  Copy,
  Play,
  Link2,
  RefreshCw,
  Clock3,
  MessageSquare,
  FileText,
  Clapperboard,
  ChartNoAxesCombined,
  ChevronRight,
  AlertCircle,
  Check,
  Loader2,
  ScanLine,
  Quote,
  Pencil,
  X,
} from "lucide-react";
import {
  api,
  post,
  asset,
  count,
  date,
  timecode,
  statusText,
  stageText,
} from "./api";
import type { Job, Result, Analysis } from "./types";
import { Badge, Empty, ErrorNotice } from "./App";

export default function Detail({
  id,
  notify,
  admin,
}: {
  id: string;
  notify: (text: string) => void;
  admin: boolean;
}) {
  const [job, setJob] = useState<Job | null>(null),
    [error, setError] = useState(""),
    [tab, setTab] = useState("overview"),
    [busy, setBusy] = useState(false),
    [editing, setEditing] = useState(false),
    [draft, setDraft] = useState(""),
    [intent, setIntent] = useState(""),
    [commentQ, setCommentQ] = useState(""),
    [confirmDelete, setConfirmDelete] = useState(false);
  const player = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const j = await api<Job>("/jobs/" + id);
        if (active) {
          setJob(j);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    load();
    const timer = setInterval(load, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id]);
  function seek(t: number) {
    if (player.current) {
      player.current.currentTime = t;
      player.current.play().catch(() => {});
      player.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      notify("已复制到剪贴板");
    } catch {
      notify("当前浏览器不支持复制，请手动选择文本");
    }
  }
  async function retry() {
    setBusy(true);
    try {
      await post("/jobs/" + id + "/retry");
      setJob(await api("/jobs/" + id));
      notify("已重新加入分析队列");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveTranscript() {
    setBusy(true);
    try {
      await api("/jobs/" + id + "/transcript", {
        method: "PUT",
        body: JSON.stringify({ text: draft }),
      });
      setEditing(false);
      setJob(await api("/jobs/" + id));
      notify("文案已保存，正在重新分析");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!job)
    return (
      <>
        <ErrorNotice message={error} />
        <div className="skeleton-detail" />
      </>
    );
  const r = job.result,
    a = r.analysis,
    processing = ["running", "queued"].includes(job.status);
  const samples = (r.comments || []).filter(
    (c) =>
      (!intent || c.intent === intent) &&
      (!commentQ || c.text.includes(commentQ) || c.author.includes(commentQ)),
  );
  const metrics = [
    ["播放量", "views"],
    ["点赞", "likes"],
    ["评论", "comments"],
    ["收藏", "saves"],
    ["分享", "shares"],
  ] as const;
  return (
    <>
      <div className="detail-toolbar">
        <a href="#dashboard" className="back-link">
          <ArrowLeft size={17} />
          返回分析库
        </a>
        <div>
          <Badge status={job.status} />
          {admin && !processing && (
            <button
              className="text-button"
              disabled={busy}
              onClick={() => setConfirmDelete(!confirmDelete)}
            >
              删除
            </button>
          )}
          {!processing && (
            <button className="secondary" disabled={busy} onClick={retry}>
              <RefreshCw size={15} />
              重新分析
            </button>
          )}
          <a className="secondary" href={`/api/jobs/${id}/export`}>
            <Download size={15} />
            导出报告
          </a>
        </div>
      </div>
      <ErrorNotice message={error} />
      {confirmDelete && (
        <div className="notice warning">
          <div>
            <strong>删除这份报告和平台内的视频素材？</strong>
            <p>原 outputs 目录中的历史文件会保留。</p>
            <div className="button-row">
              <button
                className="secondary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api("/jobs/" + id, { method: "DELETE" });
                    location.hash = "dashboard";
                    notify("报告和素材已删除");
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                确认删除
              </button>
              <button
                className="secondary"
                onClick={() => setConfirmDelete(false)}
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
      {processing && (
        <div className="processing">
          <div>
            <Loader2 className="spin" size={21} />
            <strong>{stageText[job.stage] || job.stage}</strong>
            <span>可离开页面，任务会继续处理</span>
          </div>
          <ol>
            {["collect", "media", "transcribe", "analyze"].map((stage, i) => {
              const current = [
                "collect",
                "media",
                "transcribe",
                "analyze",
              ].indexOf(job.stage);
              return (
                <li
                  key={stage}
                  className={
                    i < current ? "complete" : i === current ? "current" : ""
                  }
                >
                  <span>{i < current ? <Check size={12} /> : i + 1}</span>
                  {["采集信息", "准备素材", "提取文案", "深度分析"][i]}
                </li>
              );
            })}
          </ol>
        </div>
      )}
      {job.error && (
        <div className="notice warning">
          <AlertCircle size={18} />
          <div>
            <strong>
              {job.status === "partial"
                ? "已有素材和基础报告可用，深度分析需要重试"
                : "任务未能完整完成"}
            </strong>
            <p>{job.error}</p>
          </div>
        </div>
      )}
      <section className="video-summary">
        <div className="player-column">
          <div className="player-wrap">
            {r.playback_file ? (
              <video
                ref={player}
                src={asset(id, r.playback_file)}
                poster={r.cover_file ? asset(id, r.cover_file) : undefined}
                controls
                preload="metadata"
              />
            ) : r.cover_file ? (
              <img src={asset(id, r.cover_file)} alt="视频封面" />
            ) : (
              <div className="player-placeholder">
                <Clapperboard size={46} />
                <p>视频素材准备中</p>
              </div>
            )}
          </div>
          <div className="resource-links">
            {r.video_file && (
              <a href={asset(id, r.video_file, true)}>
                <Download size={14} />
                完整视频
              </a>
            )}
            {r.cover_file && (
              <a href={asset(id, r.cover_file, true)}>
                <Download size={14} />
                封面图
              </a>
            )}
            {r.source_url && (
              <a href={r.source_url} target="_blank" rel="noreferrer">
                <ArrowUpRight size={14} />
                打开原视频
              </a>
            )}
          </div>
        </div>
        <div className="summary-content">
          <div className="summary-eyebrow">
            <span className="platform-chip">{r.platform || "视频研究"}</span>
            <span>
              <Clock3 size={13} />
              {timecode(r.duration)}
            </span>
            <span>{r.width && `${r.width} × ${r.height}`}</span>
          </div>
          <h1>{r.title || "正在解析视频链接…"}</h1>
          <div className="author-line">
            <span className="avatar small">{(r.author || "作")[0]}</span>
            <b>{r.author || "作者信息待采集"}</b>
            <span>发布于 {date(r.published_at)}</span>
          </div>
          <div className="tag-list">
            {r.tags?.map((t) => (
              <span key={t}>#{t}</span>
            ))}
          </div>
          <div className="research-summary">
            <span className="section-kicker">
              <ScanLine size={15} />
              研究摘要
            </span>
            <p>
              {a?.summary ||
                (processing
                  ? "正在收集原片、文案与画面证据，分析完成后会在这里生成核心判断。"
                  : "素材尚未准备好，请重试采集。")}
            </p>
          </div>
          <div className="evidence-badges">
            <span className={r.transcript?.text ? "ready" : ""}>
              <Check size={13} />
              文案{r.transcript?.text ? "已提取" : "待提取"}
            </span>
            <span className={r.frames?.length ? "ready" : ""}>
              <Check size={13} />
              {r.frames?.length || 0} 张画面证据
            </span>
            <span className={r.comments?.length ? "ready" : ""}>
              <MessageSquare size={13} />
              {r.comments?.length || 0} 条评论样本
            </span>
          </div>
        </div>
      </section>
      <div className="metrics-bar">
        {metrics.map(([label, key]) => (
          <div key={key}>
            <span>{label}</span>
            <strong>{count(r.metrics?.[key])}</strong>
          </div>
        ))}
        <div className="metrics-date">
          <small>
            数据采集于
            <br />
            {date(r.collected_at)}
          </small>
        </div>
      </div>
      <div className="detail-tabs" role="tablist">
        {[
          ["overview", "爆点分析", ChartNoAxesCombined],
          ["transcript", "视频文案", FileText],
          ["frames", "画面拆解", Clapperboard],
          ["comments", "评论洞察", MessageSquare],
        ].map(([value, label, Icon]) => (
          <button
            key={String(value)}
            role="tab"
            aria-selected={tab === value}
            className={tab === value ? "active" : ""}
            onClick={() => setTab(String(value))}
          >
            <Icon size={17} />
            {String(label)}
            {value === "comments" && <small>{r.comments?.length || 0}</small>}
          </button>
        ))}
      </div>
      <div className="tab-content" role="tabpanel">
        {tab === "overview" &&
          (a ? (
            <Overview a={a} r={r} seek={seek} />
          ) : (
            <Empty title="分析正在准备">完成素材采集后，将自动生成报告。</Empty>
          ))}
        {tab === "transcript" && (
          <>
            <div className="section-head">
              <div>
                <span className="eyebrow">COPYWRITING</span>
                <h2>每一句话，如何推动观看</h2>
                <p className="muted">{r.transcript?.note || "等待语音转写"}</p>
              </div>
              <div className="button-row">
                <button
                  className="secondary"
                  disabled={!r.transcript?.text}
                  onClick={() => copy(r.transcript?.text || "")}
                >
                  <Copy size={15} />
                  复制全文
                </button>
                <button
                  className="secondary"
                  disabled={processing}
                  onClick={() => {
                    setDraft(r.transcript?.text || "");
                    setEditing(!editing);
                  }}
                >
                  <Pencil size={15} />
                  校正文案
                </button>
              </div>
            </div>
            {editing ? (
              <section className="editor-panel">
                <label>
                  校正逐字稿
                  <textarea
                    rows={12}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                </label>
                <p className="muted">
                  保存后会重新生成分析；手动全文不再保留旧句子的时间对齐。
                </p>
                <div className="button-row">
                  <button
                    className="primary"
                    disabled={busy || !draft.trim()}
                    onClick={saveTranscript}
                  >
                    保存并重新分析
                  </button>
                  <button
                    className="secondary"
                    onClick={() => setEditing(false)}
                  >
                    取消
                  </button>
                </div>
              </section>
            ) : r.transcript?.text ? (
              <div className="copy-layout">
                <div className="transcript-lines">
                  {r.transcript.timing === "aligned" &&
                  r.transcript.segments.length ? (
                    r.transcript.segments.map((s, i) => (
                      <button key={i} onClick={() => seek(s.start)}>
                        <span>
                          {timecode(s.start)}
                          <Play size={11} />
                        </span>
                        <p>{s.text}</p>
                      </button>
                    ))
                  ) : (
                    <p className="prose prewrap">{r.transcript.text}</p>
                  )}
                </div>
                <aside className="copy-notes">
                  <span className="section-kicker">文案观察</span>
                  <h3>标题与开头</h3>
                  <p>{a?.copywriting.title_analysis || "等待深度分析"}</p>
                  <hr />
                  <span className="muted">口播文字密度</span>
                  <strong className="density">
                    {a?.copywriting.density ?? "—"}
                    <small>字 / 秒</small>
                  </strong>
                  <p className="small muted">
                    按全文字数与视频时长计算，不等于真实语速。
                  </p>
                  {a?.copywriting.rewrite?.length ? (
                    <>
                      <hr />
                      <h3>可以尝试的新开场</h3>
                      {a.copywriting.rewrite.map((text, i) => (
                        <div className="rewrite" key={i}>
                          <span>0{i + 1}</span>
                          <p>{text}</p>
                          <button
                            className="icon-button"
                            aria-label="复制改写"
                            onClick={() => copy(text)}
                          >
                            <Copy size={14} />
                          </button>
                        </div>
                      ))}
                    </>
                  ) : null}
                </aside>
              </div>
            ) : (
              <Empty title="暂未取得视频文案">
                可在这里手动补充文案，或检查本地 ASR 环境后重新分析。
              </Empty>
            )}
          </>
        )}
        {tab === "frames" && (
          <>
            <div className="section-head">
              <div>
                <span className="eyebrow">VISUAL BREAKDOWN</span>
                <h2>沿着时间线，细看每一帧</h2>
                <p className="muted">
                  约每 {r.frame_interval || 3} 秒采样 · 点击画面回看原片 ·
                  抽帧不代表连续镜头的完整变化
                </p>
              </div>
              <span className="count-label">
                {r.frames?.length || 0} 个观察点
              </span>
            </div>
            {r.frames?.length ? (
              <div className="frames-list">
                {r.frames.map((f, i) => (
                  <article className="frame-row" key={f.file}>
                    <button
                      className="frame-image"
                      onClick={() => seek(f.time)}
                    >
                      <img
                        src={asset(id, f.file)}
                        alt={`${timecode(f.time)} 视频画面`}
                        loading="lazy"
                      />
                      <span>
                        <Play size={12} />
                        {timecode(f.time)}
                      </span>
                    </button>
                    <div className="frame-description">
                      <div className="frame-title">
                        <span className="frame-number">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <h3>
                          {timecode(f.time)} <span>画面观察</span>
                        </h3>
                        <small>
                          {f.method === "vision_model"
                            ? "视觉模型分析"
                            : "图像统计"}
                        </small>
                      </div>
                      <p className="prewrap">
                        {f.description ||
                          "已保留实际画面，暂无语义描述。可结合原片人工观察或重新执行深度分析。"}
                      </p>
                      <div className="frame-stats">
                        <span>
                          画面亮度 <b>{f.brightness}%</b>
                        </span>
                        <span>
                          与前帧像素差异{" "}
                          <b>{f.change == null ? "首帧" : f.change + "%"}</b>
                        </span>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <Empty title="画面证据尚未准备好">
                下载视频后将自动抽取关键时刻。
              </Empty>
            )}
          </>
        )}
        {tab === "comments" && (
          <>
            <div className="section-head">
              <div>
                <span className="eyebrow">AUDIENCE INSIGHTS</span>
                <h2>观众真正关心的是什么</h2>
                <p className="muted">{r.comments_note}</p>
              </div>
              <span className="count-label">
                已采集 {r.comments?.length || 0} / 总评论{" "}
                {count(r.metrics?.comments)}
              </span>
            </div>
            {r.comments?.length ? (
              <>
                <div className="comment-overview">
                  <section>
                    <h3>评论意图分布</h3>
                    <p className="muted small">{r.comment_insights?.method}</p>
                    <div className="intent-bars">
                      {r.comment_insights?.intents.map((item) => (
                        <button
                          key={item.label}
                          onClick={() =>
                            setIntent(intent === item.label ? "" : item.label)
                          }
                        >
                          <span>{item.label}</span>
                          <div>
                            <i
                              style={{
                                width:
                                  Math.max(
                                    3,
                                    (item.count / (r.comments?.length || 1)) *
                                      100,
                                  ) + "%",
                              }}
                            />
                          </div>
                          <b>{item.count}</b>
                        </button>
                      ))}
                    </div>
                  </section>
                  <section>
                    <h3>评论高频片段</h3>
                    <p className="muted small">
                      基于已采集文本的片段频次，点击筛选
                    </p>
                    <div className="word-cloud">
                      {r.comment_insights?.keywords.map((k, i) => (
                        <button
                          key={k.word}
                          style={{ fontSize: Math.max(14, 26 - i * 0.6) }}
                          onClick={() => setCommentQ(k.word)}
                        >
                          {k.word}
                          <small>{k.count}</small>
                        </button>
                      ))}
                    </div>
                  </section>
                </div>
                <div className="comments-filter">
                  <button
                    className={!intent ? "active" : ""}
                    onClick={() => {
                      setIntent("");
                      setCommentQ("");
                    }}
                  >
                    全部评论
                  </button>
                  {r.comment_insights?.intents.map((i) => (
                    <button
                      className={intent === i.label ? "active" : ""}
                      key={i.label}
                      onClick={() => setIntent(i.label)}
                    >
                      {i.label}
                    </button>
                  ))}
                  <input
                    aria-label="搜索评论"
                    value={commentQ}
                    onChange={(e) => setCommentQ(e.target.value)}
                    placeholder="搜索评论内容"
                  />
                </div>
                <div className="comments-list">
                  {samples.map((c) => (
                    <article key={c.id}>
                      <span className="avatar">{c.author[0]}</span>
                      <div>
                        <div className="comment-author">
                          <strong>{c.author}</strong>
                          <small>{c.intent}</small>
                          <span>{date(c.timestamp)}</span>
                        </div>
                        <p>{c.text}</p>
                      </div>
                      <small>{count(c.likes)} 赞</small>
                    </article>
                  ))}
                  {!samples.length && (
                    <Empty title="没有匹配的评论">清除筛选后重试。</Empty>
                  )}
                </div>
              </>
            ) : (
              <Empty title="评论内容暂未采集到">
                平台可能需要登录或未公开评论。管理员可更新 Cookie
                后重新提交视频链接；已有评论总数仍会保留展示。
              </Empty>
            )}
          </>
        )}
      </div>
      <details className="source-notes">
        <summary>
          数据来源与分析边界
          <ChevronRight size={14} />
        </summary>
        <p>
          创建者：{job.owner_name} · {date(job.created)} ·{" "}
          {a?.model || "基础证据分析"}
        </p>
        {r.warnings?.map((w, i) => (
          <p key={i}>{w}</p>
        ))}
        {a?.limitations?.map((w, i) => (
          <p key={i}>{w}</p>
        ))}
      </details>
    </>
  );
}

function Overview({
  a,
  r,
  seek,
}: {
  a: Analysis;
  r: Result;
  seek: (t: number) => void;
}) {
  const ratios = [
    ["点赞 / 播放", "like_rate", "%"],
    ["收藏 / 点赞", "save_like", "×"],
    ["分享 / 评论", "share_comment", "×"],
    ["评论 / 播放", "comment_rate", "%"],
  ];
  return (
    <>
      <div className="ratio-strip">
        {ratios.map(([label, key, unit]) => (
          <div key={key}>
            <span>{label}</span>
            <strong>
              {r.ratios?.[key] == null ? "—" : r.ratios[key]?.toFixed(2) + unit}
            </strong>
            <small>
              {r.ratios?.[key] == null
                ? "缺少公开数据，暂不计算"
                : "按采集快照计算"}
            </small>
          </div>
        ))}
      </div>
      <div className="analysis-columns">
        <section className="hook-section">
          <div className="section-kicker">
            <span className="orange">01</span>开场钩子
          </div>
          <h2>第一句话，给了什么理由留下</h2>
          <blockquote>
            <Quote size={20} />
            {a.hook.quote || "暂无开场文案"}
          </blockquote>
          <p className="prose">{a.hook.analysis}</p>
          <div className="audience">
            <span>目标受众</span>
            <p>{a.audience}</p>
          </div>
        </section>
        <section className="factor-section">
          <div className="section-kicker">
            <span className="orange">02</span>内容吸引力
          </div>
          <h2>值得复用的创作因素</h2>
          {a.factors.map((f, i) => (
            <article className="factor" key={i}>
              <span className="factor-number">0{i + 1}</span>
              <div>
                <h3>{f.title}</h3>
                <p>{f.explanation}</p>
                <div className="factor-evidence">
                  分析依据：{f.evidence}
                  {f.time != null && (
                    <button onClick={() => seek(f.time!)}>
                      {timecode(f.time)}
                      <Play size={10} />
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </section>
      </div>
      <section className="structure-section">
        <div className="section-head">
          <div>
            <div className="section-kicker">
              <span className="orange">03</span>脚本结构
            </div>
            <h2>让内容成立的节奏与推进</h2>
          </div>
          <small className="muted">时间来自素材；张力为模型主观判断</small>
        </div>
        <div className="structure-list">
          {a.structure.map((s, i) => (
            <article key={i}>
              <button className="time-pill" onClick={() => seek(s.start)}>
                {timecode(s.start)}
                <span>— {timecode(s.end)}</span>
                <Play size={12} />
              </button>
              <div className="structure-body">
                <h3>{s.role}</h3>
                <p className="structure-quote">
                  {s.text || "该时段无对应转写文案"}
                </p>
                <p className="muted">{s.analysis}</p>
              </div>
              <div className="emotion">
                <small>内容张力 {s.emotion ?? "—"}/5</small>
                <div>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <i
                      className={
                        s.emotion != null && n <= s.emotion ? "filled" : ""
                      }
                      key={n}
                    />
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="takeaways">
        <div>
          <div className="section-kicker">
            <span className="orange">04</span>创作启发
          </div>
          <h2>带走结构，创造新的表达</h2>
          <p className="formula">{a.formula}</p>
        </div>
        <ol>
          {a.suggestions.length ? (
            a.suggestions.map((s, i) => (
              <li key={i}>
                <span>0{i + 1}</span>
                {s}
              </li>
            ))
          ) : (
            <li>深度分析完成后将在这里给出有针对性的创作建议。</li>
          )}
        </ol>
      </section>
    </>
  );
}
