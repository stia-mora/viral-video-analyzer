# 片析运行说明

## 启动与登录

本机地址：http://localhost:8765 。初始管理员随机密码位于 `data/first-login.txt`，登录后在设置修改密码。修改 admin 密码后该文件会被删除。

```powershell
# 首次安装
powershell -ExecutionPolicy Bypass -File scripts\setup_platform.ps1
# 后台启动（不打开额外窗口）
powershell -ExecutionPolicy Bypass -File scripts\start_platform.ps1
# 停止
powershell -ExecutionPolicy Bypass -File scripts\stop_platform.ps1
```

前台调试加 `-Foreground`。日志：`data/server.log`、`data/server-error.log`。同一数据目录只支持一个服务进程，OS 文件锁防止多个 worker 抢占同一 GPU。停止后的未完成任务会在重启后恢复。

## 团队使用

管理员在“团队成员”创建成员，设置初始密码。成员共享分析库，可提交视频、回看、下载、校正文案、导出报告。停用成员立即撤销其会话。模型密钥和 Cookie 仅管理员可管理，不会返回给成员。

局域网通过服务器地址访问端口 8765。跨公网部署必须使用 HTTPS 反向代理，设置 `PIANXI_HTTPS=1` 并只允许代理访问后端。HTTP 仅用于本机/受信任局域网调试，不要在不受信任网络传输登录密码。

当前机器局域网入口为 http://10.202.1.26:8765 （Wi-Fi 地址变化后需更新）。本次检查专用/公用网络防火墙均为关闭状态，未修改全局防火墙。若后续启用防火墙后无法访问，可由管理员运行 `scripts/enable_team_network.ps1`，规则仅允许专用网络中的本地子网访问 8765。

## 模型

默认使用 Qwen3-VL-2B-Instruct 本地视觉模型，已下载到 `.hf-cache/vision-model`，约 4.3GB。语音沿用原项目 Qwen3-ASR-1.7B 和 ForcedAligner。有完整缓存时使用离线模型路径，避免元数据请求导致等待。新机器可用视觉环境执行 `scripts/download_vision_model.py` 下载模型。

本机视觉环境：`D:/ProgramData/anaconda3/envs/vlm-qwen3/python.exe`。ASR 环境：用户目录下 `.conda/envs/douyin-qwen-asr/python.exe`。迁移机器时设置 `PIANXI_VLM_PYTHON`、`PIANXI_ASR_PYTHON`；视觉环境需要 CUDA PyTorch、支持 Qwen3-VL 的 transformers、accelerate 和 Pillow。

也可在“系统设置”配置兼容 Chat Completions 的模型 API：根地址（通常以 `/v1` 结尾）、视觉模型名称、API Key。使用 API 会把文案和抽帧发送到该服务，本地模式素材不离开本机。保存后检测配置，再执行分析。

## 采集与分析

链接 → 平台详情/评论 → 下载视频 → 封面/抽帧/音频 → 语音转写 → 视觉与文案分析 → 团队报告。

输入框支持直接粘贴链接、抖音 `v.douyin.com` 短链，或包含链接的完整分享文案/Markdown 链接。系统会识别文案中的第一个受支持视频链接；短链先解析正式地址，报告同时保留原始分享文案来源。

- 抖音采用公开页面详情采集，回退 yt-dlp；哔哩哔哩、YouTube 使用 yt-dlp。
- 登录验证或平台限制可能导致采集失败，管理员可更新 Netscape 格式 Cookie 后重试。
- 评论总数与采集样本分开显示。抖音评论由浏览器驱动平台自己的分页界面，最多采集前 100 条公开样本；平台验证、折叠评论或登录态限制时可能少于该数量。评论意图采用关键词规则，高频片段不是完整语义分词。
- 抖音公开详情未返回真实播放量时，系统显示“未提供”，不会用点赞、评论或分享反推。若需要自己账号作品的真实播放数据，应接入平台提供的已授权创作者数据源。
- 未公开播放量显示“未提供”，比例在分母未知或为零时不计算。
- 语音转写默认使用 Qwen 的自动语言识别，英文会保留单词空格，中文继续按中文分段；报告展示识别语言。
- 抽帧是离散观察。最多 24 张画面独立送入本地视觉模型；云端 API 发送 8 张代表性画面，其他抽帧保留原图和图像统计。不以单帧推断声音或连续运镜。文件内容未变化的画面分析可复用缓存。
- 模型判断不等于爆款概率或因果证明。2B 本地模型可能误读内容，可以换用更强的视觉 API；报告保留原文与画面供核对。
- 当前每条视频限制 15 分钟、500MB，最多 20 个待处理任务。素材库约 20GB 上限，剩余磁盘小于 2GB 时停止新增。
- 分析失败保留资源与基础证据，重新分析可重试模型。重新采集最新互动数请从原链接新建任务。

## 原有功能与备份

原 `scripts/process_douyin_video.ps1`、配置、Obsidian 导出流程保留。新平台可导入 `outputs/<平台>/<视频>/video.info.json` 和相关视频/转写文件，也可导出 Markdown、JSON。

停服后备份 `data/`、`config/` 和平台 Cookie。`data/` 包含账户哈希、会话和模型密钥，应限制文件权限，不提交到 Git。模型缓存可重新下载。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests -q
npm --prefix frontend run build
```

测试使用临时数据库，浏览器验证截图位于 `output/playwright/`。
