export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = "请求失败，请稍后重试";
    try {
      const data = await response.json();
      message =
        typeof data.detail === "string" ? data.detail : "请检查输入内容";
    } catch {}
    if (response.status === 401 && !path.includes("/auth/login"))
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(message);
  }
  return response.json();
}
export const post = <T>(path: string, data: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(data) });
export const asset = (id: string, file: string, download = false) =>
  `/api/jobs/${id}/assets/${file}${download ? "?download=true" : ""}`;
export const timecode = (value: number = 0) =>
  `${Math.floor(value / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(value % 60)
    .toString()
    .padStart(2, "0")}`;
export function count(value: number | null | undefined) {
  if (value == null) return "未提供";
  if (value >= 10000) return (value / 10000).toFixed(1) + "万";
  return value.toLocaleString("zh-CN");
}
export const date = (value?: number) =>
  value ? new Date(value * 1000).toLocaleDateString("zh-CN") : "未提供";
export const statusText: Record<string, string> = {
  done: "分析完成",
  partial: "部分完成",
  failed: "处理失败",
  running: "分析中",
  queued: "排队中",
};
export const stageText: Record<string, string> = {
  queued: "等待前面的任务完成",
  collect: "采集视频与互动数据",
  media: "下载资源与提取画面",
  transcribe: "提取视频文案",
  analyze: "分析文案与视频爆点",
  done: "报告已完成",
  failed: "处理未完成",
};
