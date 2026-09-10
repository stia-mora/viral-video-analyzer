import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowUpRight,
  Clapperboard,
  LayoutDashboard,
  LogOut,
  Settings,
  Users,
  ChevronDown,
  PanelLeftClose,
  Menu,
  Search,
  Link2,
  ArrowRight,
  Plus,
  FolderInput,
  Check,
  Film,
  Clock3,
  Layers3,
  Loader2,
  AlertCircle,
  X,
  Download,
  Command,
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
import type { User, Job } from "./types";
import Detail from "./Detail";
import SettingsPage from "./Settings";
import Team from "./Team";

export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Film size={32} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function ErrorNotice({ message }: { message: string }) {
  return message ? (
    <div className="notice error" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
    </div>
  ) : null;
}
export function Badge({ status }: { status: string }) {
  return (
    <span className={`status ${status}`}>
      <i />
      {statusText[status] || status}
    </span>
  );
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setError("");
    setBusy(true);
    try {
      onLogin(await post<User>("/auth/login", Object.fromEntries(data)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <section className="login-story">
        <a className="brand">
          <span className="brand-mark">
            <Clapperboard size={24} />
          </span>
          片析<span className="brand-en">PIANXI</span>
        </a>
        <div>
          <span className="eyebrow">每一条好内容，都有迹可循</span>
          <h1>
            不止看见热度。
            <br />
            更看懂<span>为什么。</span>
          </h1>
          <p>
            把一条视频，变成整个团队的创作洞察。
            <br />
            从原始素材到文案、镜头与评论，一处完成研究。
          </p>
          <div className="story-timeline">
            <span>
              01<small>收集素材</small>
            </span>
            <i />
            <span>
              02<small>拆解内容</small>
            </span>
            <i />
            <span>
              03<small>沉淀洞察</small>
            </span>
          </div>
        </div>
        <small>视频研究工作台 · 为创作者与团队而建</small>
      </section>
      <section className="login-form">
        <div>
          <span className="eyebrow">TEAM WORKSPACE</span>
          <h2>回到你的创作研究室</h2>
          <p className="muted">登录后，与团队一起发现内容的更多可能。</p>
          <form onSubmit={submit}>
            <label>
              账号
              <input
                name="username"
                autoComplete="username"
                required
                placeholder="输入团队账号"
              />
            </label>
            <label>
              密码
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                placeholder="输入密码"
              />
            </label>
            <ErrorNotice message={error} />
            <button className="primary wide" disabled={busy}>
              {busy ? <Loader2 className="spin" size={18} /> : null}登录工作台
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="login-help">
            还没有账号？请联系团队管理员添加成员。
            <br />
            首次管理员登录信息保存在服务器的 data/first-login.txt。
          </p>
        </div>
      </section>
    </div>
  );
}

function Dashboard({
  user,
  navigate,
  notify,
}: {
  user: User;
  navigate: (path: string) => void;
  notify: (text: string) => void;
}) {
  const [jobs, setJobs] = useState<Job[]>([]),
    [counts, setCounts] = useState<Record<string, number>>({}),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [filter, setFilter] = useState(""),
    [error, setError] = useState(""),
    [url, setUrl] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [showImport, setShowImport] = useState(false),
    [policy, setPolicy] = useState<{
      provider: string;
      destination: string;
      model: string;
    } | null>(null),
    [local, setLocal] = useState<
      { path: string; title: string; duration: number }[]
    >([]);
  useEffect(() => {
    api<{ provider: string; destination: string; model: string }>("/policy")
      .then(setPolicy)
      .catch(() => {});
  }, []);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await api<{
          items: Job[];
          total: number;
          counts: Record<string, number>;
        }>(`/jobs?q=${encodeURIComponent(q)}&status=${filter}&page=${page}`);
        if (active) {
          setJobs(data.items);
          setTotal(data.total);
          setCounts(data.counts);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    const timer = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [q, filter, page]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const j = await post<{ id: string }>("/jobs", { url });
      navigate("video/" + j.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function importList() {
    setShowImport(!showImport);
    try {
      setLocal(await api("/library/local"));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function importVideo(path: string) {
    setBusy(true);
    try {
      const j = await post<{ id: string }>("/library/import", { url: path });
      navigate("video/" + j.id);
      notify("历史素材已加入处理队列");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const all = Object.values(counts).reduce((a, b) => a + b, 0);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">内容研究 / WORKSPACE</div>
          <h1>
            把好内容，拆解成下一次灵感<span className="orange">。</span>
          </h1>
          <p className="muted">
            一个链接，看懂文案、画面与用户反馈背后的创作逻辑。
          </p>
        </div>
        <span className="workspace-tag">
          <Users size={15} />
          团队共享空间
        </span>
      </div>
      <section className="create-panel">
        <div className="section-label">
          <span>
            <Link2 size={18} />
            开始一次视频研究
          </span>
          <div className="platforms">
            <b>抖音</b>
            <b>哔哩哔哩</b>
            <b>YouTube</b>
          </div>
        </div>
        <form className="url-form" onSubmit={submit}>
          <Link2 size={20} />
          <input
            aria-label="视频链接"
            placeholder="粘贴视频链接，或包含链接的分享文案…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
          <button className="primary" disabled={busy}>
            {busy ? (
              <Loader2 size={18} className="spin" />
            ) : (
              <span className="spark">✦</span>
            )}
            开始分析
            <ArrowUpRight size={17} />
          </button>
        </form>
        <div className="input-foot">
          <span>
            公开信息采集<span>·</span>原片与封面下载<span>·</span>多模态深度拆解
          </span>
          <small>
            <Clock3 size={13} />
            长视频将进入后台队列
          </small>
        </div>
      </section>
      {policy?.provider === "api" && (
        <div className="notice warning">
          <AlertCircle size={17} />
          <span>
            团队已启用外部分析服务 {policy.destination}（{policy.model}
            ），提交后会发送视频抽帧与文案至该服务。
          </span>
        </div>
      )}
      <div className="overview-strip">
        <div>
          <span className="stat-icon">
            <Layers3 size={20} />
          </span>
          <p>
            研究视频
            <strong>
              {all}
              <small>条</small>
            </strong>
          </p>
        </div>
        <div>
          <span className="stat-icon">
            <Check size={20} />
          </span>
          <p>
            已完成报告
            <strong>
              {counts.done || 0}
              <small>份</small>
            </strong>
          </p>
        </div>
        <div>
          <span className="stat-icon">
            <Clock3 size={20} />
          </span>
          <p>
            正在处理
            <strong>
              {(counts.running || 0) + (counts.queued || 0)}
              <small>个任务</small>
            </strong>
          </p>
        </div>
        <div className="stat-note">
          <span className="orange">让每次研究都有积累</span>
          <p>素材、文案与洞察，自动保存在团队分析库。</p>
        </div>
      </div>
      <div className="library-heading">
        <div>
          <h2>
            团队分析库 <span className="total">{total}</span>
          </h2>
          <p className="muted">从看过的视频，到可以复用的方法。</p>
        </div>
        {user.role === "admin" && (
          <button className="secondary" onClick={importList}>
            <FolderInput size={16} />
            导入已有素材
          </button>
        )}
      </div>
      {showImport && (
        <div className="import-panel">
          <div className="inline-heading">
            <h3>导入项目内已有视频</h3>
            <button
              className="icon-button"
              aria-label="关闭导入"
              onClick={() => setShowImport(false)}
            >
              <X size={18} />
            </button>
          </div>
          {local.length ? (
            local.map((item) => (
              <div className="import-row" key={item.path}>
                <span>{item.title}</span>
                <small>{timecode(item.duration)}</small>
                <button
                  disabled={busy}
                  onClick={() => importVideo(item.path)}
                  className="secondary"
                >
                  导入
                  <ArrowRight size={14} />
                </button>
              </div>
            ))
          ) : (
            <p className="muted">outputs 下没有可导入的视频。</p>
          )}
        </div>
      )}
      <div className="library-toolbar">
        <div className="filter-tabs">
          {[
            ["", "全部视频"],
            ["done", "已完成"],
            ["running", "分析中"],
            ["partial", "待完善"],
          ].map(([value, label]) => (
            <button
              key={value}
              className={filter === value ? "active" : ""}
              onClick={() => {
                setFilter(value);
                setPage(1);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="search">
          <Search size={16} />
          <input
            aria-label="搜索分析库"
            placeholder="搜索标题或链接"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>
      <ErrorNotice message={error} />
      {loading ? (
        <div className="skeleton-list">
          {[1, 2, 3].map((n) => (
            <div key={n} />
          ))}
        </div>
      ) : jobs.length ? (
        <div className="video-grid">
          {jobs.map((job) => (
            <button
              key={job.id}
              className="video-card"
              onClick={() => navigate("video/" + job.id)}
            >
              <div className="thumbnail">
                {job.result.cover_file ? (
                  <img
                    src={asset(job.id, job.result.cover_file)}
                    alt=""
                    loading="lazy"
                  />
                ) : (
                  <div className="thumbnail-empty">
                    <Clapperboard size={34} />
                    <span>{stageText[job.stage] || "正在准备素材"}</span>
                  </div>
                )}
                <span className="platform-label">
                  {job.result.platform || "视频"}
                </span>
                <span className="duration">
                  {timecode(job.result.duration)}
                </span>
              </div>
              <div className="video-card-body">
                <div className="card-meta">
                  <Badge status={job.status} />
                  <small>{date(job.created)}</small>
                </div>
                <h3>{job.result.title || "正在读取视频信息…"}</h3>
                <p className="card-author">
                  {job.result.author || job.owner_name}
                </p>
                <div className="card-metrics">
                  <span>
                    点赞 <b>{count(job.result.metrics?.likes)}</b>
                  </span>
                  <span>
                    评论 <b>{count(job.result.metrics?.comments)}</b>
                  </span>
                  <ArrowUpRight size={17} />
                </div>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <Empty title={q ? "没有匹配的视频" : "你的下一条灵感，从这里开始"}>
          {q
            ? "换一个关键词试试。"
            : "粘贴一条视频链接，或导入已有素材。分析结果会自动归档在这里。"}
        </Empty>
      )}
      {total > 24 && (
        <div className="pagination">
          <button
            className="secondary"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            上一页
          </button>
          <span>
            {page} / {Math.ceil(total / 24)}
          </span>
          <button
            className="secondary"
            disabled={page * 24 >= total}
            onClick={() => setPage(page + 1)}
          >
            下一页
          </button>
        </div>
      )}
      <footer>
        每一次拆解，都为下一次创作多一点把握。<span>片析 · PIANXI</span>
      </footer>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [ready, setReady] = useState(false),
    [route, setRoute] = useState(location.hash.slice(1) || "dashboard"),
    [toast, setToast] = useState(""),
    [mobile, setMobile] = useState(false);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setReady(true));
    const hash = () => setRoute(location.hash.slice(1) || "dashboard");
    const expired = () => setUser(null);
    window.addEventListener("hashchange", hash);
    window.addEventListener("session-expired", expired);
    return () => {
      window.removeEventListener("hashchange", hash);
      window.removeEventListener("session-expired", expired);
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(id);
  }, [toast]);
  function navigate(path: string) {
    location.hash = path;
    setMobile(false);
    window.scrollTo(0, 0);
  }
  if (!ready)
    return (
      <div className="boot">
        <Clapperboard />
        <span>正在打开片析…</span>
      </div>
    );
  if (!user)
    return (
      <Login
        onLogin={(u) => {
          setUser(u);
          api<User>("/auth/me").then(setUser);
        }}
      />
    );
  const detail = route.startsWith("video/");
  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <a className="brand" href="#dashboard">
          <span className="brand-mark">
            <Clapperboard size={23} />
          </span>
          片析<span className="brand-en">PIANXI</span>
        </a>
        <div className="team-switch">
          <span className="team-avatar">{(user.team_name || "创")[0]}</span>
          <div>
            <strong>{user.team_name || "创作研究室"}</strong>
            <small>团队工作空间</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <div className="nav-caption">工作空间</div>
        <nav>
          <button
            className={route === "dashboard" || detail ? "selected" : ""}
            onClick={() => navigate("dashboard")}
          >
            <LayoutDashboard size={19} />
            视频研究
            <span className="nav-dot" />
          </button>
          {user.role === "admin" && (
            <button
              className={route === "team" ? "selected" : ""}
              onClick={() => navigate("team")}
            >
              <Users size={19} />
              团队成员
            </button>
          )}
          <button
            className={route === "settings" ? "selected" : ""}
            onClick={() => navigate("settings")}
          >
            <Settings size={19} />
            {user.role === "admin" ? "系统设置" : "账户设置"}
          </button>
        </nav>
        <div className="sidebar-note">
          <span className="tiny-frame">
            <Film size={19} />
          </span>
          <strong>好内容，值得细看</strong>
          <p>
            收集证据，拆解方法，
            <br />
            让灵感成为团队的积累。
          </p>
        </div>
        <div className="profile">
          <span className="avatar">{user.name[0]}</span>
          <div>
            <strong>{user.name}</strong>
            <small>{user.role === "admin" ? "管理员" : "团队成员"}</small>
          </div>
          <button
            className="icon-button"
            aria-label="退出登录"
            onClick={async () => {
              await post("/auth/logout");
              setUser(null);
            }}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="关闭导航"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="打开导航"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">
              工作空间<span>/</span>
              <b>
                {detail
                  ? "视频拆解"
                  : route === "team"
                    ? "团队成员"
                    : route === "settings"
                      ? "设置"
                      : "视频研究"}
              </b>
            </span>
          </div>
          <div className="topbar-right">
            <span className="live-dot" />
            团队协作版
            <span className="top-divider" />
            <span>
              {new Date().toLocaleDateString("zh-CN", {
                month: "long",
                day: "numeric",
              })}
            </span>
          </div>
        </header>
        <main>
          {detail ? (
            <Detail
              key={route.slice(6)}
              id={route.slice(6)}
              notify={setToast}
              admin={user.role === "admin"}
            />
          ) : route === "settings" ? (
            <SettingsPage
              user={user}
              notify={setToast}
              refreshUser={() => api<User>("/auth/me").then(setUser)}
            />
          ) : route === "team" && user.role === "admin" ? (
            <Team notify={setToast} user={user} />
          ) : (
            <Dashboard user={user} navigate={navigate} notify={setToast} />
          )}
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Check size={17} />
          {toast}
          <button
            className="icon-button"
            onClick={() => setToast("")}
            aria-label="关闭通知"
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
