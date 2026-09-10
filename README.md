# 片析 · PIANXI

> 团队视频研究平台：将公开视频链接转化为可回看的文案、画面、互动与创作洞察。

片析（PIANXI）面向短视频创作团队。粘贴抖音、哔哩哔哩或 YouTube 视频链接，平台会采集可公开获取的素材与互动信息，下载视频和封面，提取带时间戳的口播文案，并从开场钩子、画面、脚本结构和评论样本中生成可复用的分析报告。

> 仓库不包含任何视频、账号 Cookie、团队数据或模型密钥。

## 功能

- 支持直接链接、抖音短链接、分享文案和 Markdown 链接自动识别
- 支持抖音、哔哩哔哩、YouTube 视频下载和封面下载
- 采集标题、作者、点赞、评论、收藏和分享等可公开获取指标
- 使用 Qwen3-ASR 自动识别中文、英文等音频并生成时间戳文案
- 使用本地 Qwen3-VL 或兼容 Chat Completions 的云端视觉模型分析画面
- 分析开场钩子、内容结构、视觉证据、评论意图和创作建议
- 逐段文案和关键帧可跳转回原视频时间点
- 团队成员、管理员权限、共享分析库、任务队列和 Markdown/JSON 报告导出
- 支持导入原项目 `outputs/` 中已经下载并转写的视频

## 工作流

```text
视频链接 / 分享文案
        |
        v
采集公开信息 -> 下载视频与封面 -> 抽帧与音频 -> 自动转写
        |                                      |
        +-------------------> 视频、文案、评论和画面证据
                                               |
                                               v
        开场钩子 / 脚本结构 / 视觉观察 / 评论洞察 / 创作建议
```

报告会清楚区分：平台公开指标、已采集评论样本、原始文案和模型分析结论。未公开的播放量不会由点赞或评论数据推算。

## 快速开始

### 运行环境

- Windows 10/11
- Python 3.11+
- Node.js 20+
- FFmpeg
- Conda（本地 Qwen3-ASR 和 Qwen3-VL 模式需要）
- NVIDIA GPU（推荐，CPU 可运行但会明显变慢）

首次安装和构建：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_platform.ps1
```

启动平台：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_platform.ps1
```

打开 http://localhost:8765 。首次启动会创建随机管理员密码，保存在 `data/first-login.txt`。登录后应立即修改密码。

停止平台：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_platform.ps1
```

完整的运行、团队管理、模型配置、Cookie 和局域网部署说明见 [docs/RUNNING.md](docs/RUNNING.md)。

## 模型配置

默认使用本地模型：

| 工作 | 默认模型 |
| --- | --- |
| 语音转写 | `Qwen/Qwen3-ASR-1.7B` |
| 时间戳对齐 | `Qwen/Qwen3-ForcedAligner-0.6B` |
| 画面理解 | `Qwen/Qwen3-VL-2B-Instruct` |

也可以在“系统设置”配置兼容 OpenAI Chat Completions 的视觉模型 API。点击“检测已保存配置”会实际发送一张无用户数据的 1×1 测试图片，验证密钥、模型名称、图片输入和响应格式是否可用。

本地视觉模型下载：

```powershell
D:\path\to\vision-python.exe scripts\download_vision_model.py
```

具体环境变量和离线模型配置见 [docs/RUNNING.md](docs/RUNNING.md)。

## 评论与播放量

抖音评论通过已登录浏览器会话驱动平台自身的分页界面采集，默认最多保存前 100 条公开样本。更新有效的 Netscape Cookie 后可提升可访问评论数量。平台返回的评论总数与实际采集样本数会分开显示。

对未公开的播放量，平台显示“未提供”。它不会从点赞、评论、收藏或分享反推播放量。若要获取自己账号作品的真实播放数据，需要接入平台提供的已授权创作者数据源。

## 原有命令行流程

原本的抖音下载、Qwen3-ASR 转写和 Obsidian 笔记导出流程仍然保留：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\process_douyin_video.ps1 -Url "抖音链接"
```

默认配置在 [config/defaults.json](config/defaults.json)，Qwen3-ASR 环境说明在 [docs/SETUP_QWEN3_ASR.md](docs/SETUP_QWEN3_ASR.md)。

## 开发

后端测试：

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

前端生产构建：

```powershell
npm --prefix frontend run build
```

调研与架构参考见 [docs/GITHUB_RESEARCH.md](docs/GITHUB_RESEARCH.md) 和 [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md)。

## 使用边界

请只分析、下载和使用你拥有权利或已获授权的内容，并遵守目标平台条款和适用法律。平台公开数据及模型分析仅供内容研究参考，不构成对传播效果、播放量或商业结果的保证。

## License

本仓库尚未声明许可证。公开发布前，请根据你的开源策略添加 `LICENSE` 文件。
