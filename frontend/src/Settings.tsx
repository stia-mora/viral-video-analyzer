import { useEffect, useState, type FormEvent } from "react";
import {
  Check,
  ShieldCheck,
  Server,
  KeyRound,
  Save,
  FlaskConical,
  ChevronRight,
  LockKeyhole,
  Loader2,
} from "lucide-react";
import { api, post } from "./api";
import type { User } from "./types";
import { ErrorNotice } from "./App";
type Config = {
  team_name: string;
  provider: string;
  base_url: string;
  model: string;
  has_api_key: boolean;
  local_model: string;
  cookies: Record<string, boolean>;
};
export default function Settings({
  user,
  notify,
  refreshUser,
}: {
  user: User;
  notify: (text: string) => void;
  refreshUser: () => void;
}) {
  const [config, setConfig] = useState<Config | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [key, setKey] = useState(""),
    [test, setTest] = useState(""),
    [cookie, setCookie] = useState(""),
    [platform, setPlatform] = useState("抖音");
  useEffect(() => {
    if (user.role === "admin")
      api<Config>("/settings")
        .then(setConfig)
        .catch((e) => setError(e.message));
  }, [user.role]);
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!config) return;
    setBusy(true);
    setError("");
    try {
      await api("/settings", {
        method: "PUT",
        body: JSON.stringify({
          team_name: config.team_name,
          provider: config.provider,
          base_url: config.base_url,
          model: config.model,
          api_key: key || undefined,
        }),
      });
      setKey("");
      notify("团队设置已保存");
      refreshUser();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function password(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    try {
      await post("/auth/password", Object.fromEntries(new FormData(form)));
      notify("密码已修改，请重新登录");
      window.dispatchEvent(new Event("session-expired"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WORKSPACE SETTINGS</span>
          <h1>{user.role === "admin" ? "让工作台适合你的团队" : "账户设置"}</h1>
          <p className="muted">
            {user.role === "admin"
              ? "管理研究空间、分析引擎与平台连接。"
              : "管理你的登录信息。"}
          </p>
        </div>
        <ShieldCheck className="heading-icon" size={36} />
      </div>
      <ErrorNotice message={error} />
      {config && (
        <form onSubmit={save}>
          <section className="settings-section">
            <div className="settings-label">
              <h2>团队空间</h2>
              <p>所有成员共享分析库与处理队列。</p>
            </div>
            <div className="settings-fields">
              <label>
                空间名称
                <input
                  value={config.team_name}
                  maxLength={64}
                  required
                  onChange={(e) =>
                    setConfig({ ...config, team_name: e.target.value })
                  }
                />
              </label>
            </div>
          </section>
          <section className="settings-section">
            <div className="settings-label">
              <h2>分析引擎</h2>
              <p>
                文案和关键帧会交给所选模型共同分析。选择 API
                时，素材将发送到你配置的服务。
              </p>
            </div>
            <div className="settings-fields">
              <div className="provider-options">
                <button
                  type="button"
                  onClick={() => setConfig({ ...config, provider: "local" })}
                  className={config.provider === "local" ? "selected" : ""}
                >
                  <Server size={22} />
                  <strong>本地视觉模型</strong>
                  <span>数据留在服务器 · 无 API 费用</span>
                  {config.provider === "local" && <Check size={17} />}
                </button>
                <button
                  type="button"
                  onClick={() => setConfig({ ...config, provider: "api" })}
                  className={config.provider === "api" ? "selected" : ""}
                >
                  <KeyRound size={22} />
                  <strong>自有模型 API</strong>
                  <span>兼容 Chat Completions 接口</span>
                  {config.provider === "api" && <Check size={17} />}
                </button>
              </div>
              {config.provider === "local" ? (
                <div className="local-model">
                  <span className="live-dot" />
                  <div>
                    <strong>{config.local_model}</strong>
                    <p>
                      本地多模态分析 + Qwen3-ASR 语音转写。任务逐个执行，减少
                      GPU 显存冲突。
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <label>
                    API 地址
                    <input
                      required
                      placeholder="https://your-provider.com/v1"
                      value={config.base_url}
                      onChange={(e) =>
                        setConfig({ ...config, base_url: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    视觉模型名称
                    <input
                      required
                      placeholder="支持图片输入的模型名称"
                      value={config.model}
                      onChange={(e) =>
                        setConfig({ ...config, model: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    API Key
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={key}
                      placeholder={
                        config.has_api_key
                          ? "已保存密钥；留空保留"
                          : "输入密钥（本地服务可留空）"
                      }
                      onChange={(e) => setKey(e.target.value)}
                    />
                  </label>
                </>
              )}
              <div className="button-row">
                <button className="primary" disabled={busy}>
                  <Save size={16} />
                  保存设置
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      const t = await post<{ ok: boolean; message: string }>(
                        "/settings/test",
                      );
                      setTest(t.message);
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <FlaskConical size={16} />
                  检测已保存配置
                </button>
              </div>
              {test && (
                <p className="test-result" role="status">
                  {test}
                </p>
              )}
            </div>
          </section>
        </form>
      )}
      {config && (
        <section className="settings-section">
          <div className="settings-label">
            <h2>平台登录状态</h2>
            <p>
              公开信息受平台限制时，管理员可更新授权账号的 Cookie。密钥和 Cookie
              不会返回给团队成员。
            </p>
          </div>
          <div className="settings-fields">
            <div className="cookie-status">
              {Object.entries(config.cookies).map(([name, ready]) => (
                <div key={name}>
                  <strong>{name}</strong>
                  <span className={ready ? "ready" : ""}>
                    {ready ? "已配置" : "未配置"}
                  </span>
                </div>
              ))}
            </div>
            <details className="cookie-details">
              <summary>
                更新平台 Cookie
                <ChevronRight size={15} />
              </summary>
              <label>
                平台
                <select
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                >
                  <option>抖音</option>
                  <option>哔哩哔哩</option>
                  <option>YouTube</option>
                </select>
              </label>
              <label>
                Netscape Cookie 文件内容
                <textarea
                  value={cookie}
                  onChange={(e) => setCookie(e.target.value)}
                  placeholder="# Netscape HTTP Cookie File"
                  rows={5}
                />
              </label>
              <button
                className="secondary"
                disabled={busy || !cookie}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api("/settings/cookies", {
                      method: "PUT",
                      body: JSON.stringify({ platform, content: cookie }),
                    });
                    setCookie("");
                    setConfig(await api("/settings"));
                    notify("Cookie 已更新");
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                保存 Cookie
              </button>
            </details>
          </div>
        </section>
      )}
      <section className="settings-section">
        <div className="settings-label">
          <h2>账户安全</h2>
          <p>修改密码后，所有已登录会话会失效。</p>
        </div>
        <form className="settings-fields" onSubmit={password}>
          <label>
            当前密码
            <input
              type="password"
              name="old_password"
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            新密码
            <input
              type="password"
              name="new_password"
              minLength={10}
              maxLength={256}
              required
              autoComplete="new-password"
              placeholder="至少 10 位"
            />
          </label>
          <button className="secondary" disabled={busy}>
            <LockKeyhole size={16} />
            修改密码
          </button>
        </form>
      </section>
    </>
  );
}
