import { useEffect, useState, type FormEvent } from "react";
import { Plus, Users, UserPlus, X } from "lucide-react";
import { api, post, date } from "./api";
import type { User } from "./types";
import { ErrorNotice } from "./App";
type Member = User & { active: number; created: number };
export default function Team({
  notify,
  user,
}: {
  notify: (s: string) => void;
  user: User;
}) {
  const [members, setMembers] = useState<Member[]>([]),
    [error, setError] = useState(""),
    [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false);
  function load() {
    api<Member[]>("/team")
      .then(setMembers)
      .catch((e) => setError(e.message));
  }
  useEffect(load, []);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post("/team", Object.fromEntries(new FormData(e.currentTarget)));
      setOpen(false);
      load();
      notify("成员已添加，可使用账号登录");
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
          <span className="eyebrow">YOUR CREATIVE TEAM</span>
          <h1>让洞察，在团队里流动</h1>
          <p className="muted">共同研究、共享素材，把个人发现变成团队积累。</p>
        </div>
        <button className="primary" onClick={() => setOpen(!open)}>
          <UserPlus size={17} />
          添加成员
        </button>
      </div>
      <ErrorNotice message={error} />
      {open && (
        <form className="member-form" onSubmit={create}>
          <div className="inline-heading">
            <h2>添加团队成员</h2>
            <button
              type="button"
              className="icon-button"
              aria-label="关闭添加成员"
              onClick={() => setOpen(false)}
            >
              <X size={18} />
            </button>
          </div>
          <div className="form-grid">
            <label>
              姓名
              <input
                name="name"
                required
                maxLength={64}
                placeholder="如何称呼这位伙伴"
              />
            </label>
            <label>
              登录账号
              <input
                name="username"
                required
                minLength={3}
                maxLength={64}
                placeholder="字母或数字"
              />
            </label>
            <label>
              初始密码
              <input
                name="password"
                type="password"
                required
                minLength={10}
                autoComplete="new-password"
                placeholder="至少 10 位"
              />
            </label>
            <label>
              角色
              <select name="role">
                <option value="member">成员：创建与查看报告</option>
                <option value="admin">管理员：管理成员与设置</option>
              </select>
            </label>
          </div>
          <button className="primary" disabled={busy}>
            创建账号
          </button>
          <p className="muted small">
            请通过团队内部渠道提供账号信息，成员可自行修改密码。
          </p>
        </form>
      )}
      <div className="members-heading">
        <h2>
          全部成员 <span className="total">{members.length}</span>
        </h2>
        <span className="muted">同一团队的成员共享分析库</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>成员</th>
              <th>账号</th>
              <th>角色</th>
              <th>加入日期</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id}>
                <td>
                  <div className="member-name">
                    <span className="avatar">{m.name[0]}</span>
                    <strong>{m.name}</strong>
                    {m.id === user.id && <small>你</small>}
                  </div>
                </td>
                <td>{m.username}</td>
                <td>{m.role === "admin" ? "管理员" : "成员"}</td>
                <td>{date(m.created)}</td>
                <td>
                  <span className={m.active ? "text-green" : "muted"}>
                    {m.active ? "正常" : "已停用"}
                  </span>
                </td>
                <td>
                  {m.id !== user.id && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await api("/team/" + m.id, {
                            method: "PATCH",
                            body: JSON.stringify({ active: !m.active }),
                          });
                          load();
                          notify(m.active ? "成员已停用" : "成员已启用");
                        } catch (e) {
                          setError((e as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      {m.active ? "停用" : "启用"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="team-explainer">
        <Users size={22} />
        <p>
          <strong>为小团队准备的共享工作空间</strong>
          <br />
          管理员管理账户和分析服务；成员可以提交视频、回看证据、校正文案并导出报告。
        </p>
      </div>
    </>
  );
}
