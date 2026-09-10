---
name: douyin-video-to-txt
description: 抖音视频转文本知识库 — 默认使用 Qwen3-ASR-1.7B + douyin-qwen-asr conda 环境，转写后写入 Obsidian Vault 根目录。
args: <douyin_url> - 抖音视频链接
version: 3.1.0-local
---

# 抖音视频转文本知识库（默认 Qwen3-ASR）

本项目默认流程已经固定为：

```text
抖音链接 -> yt-dlp 下载 -> ffmpeg 抽音频 -> Qwen3-ASR-1.7B 转写 -> Markdown 笔记 -> Obsidian Vault 根目录
```

只维护当前项目内的 skill：

```text
E:\Group-projects\douyin-video-to-txt\skills\douyin-video-to-txt
```

不要复制或依赖 Codex 全局 skills 目录。

## 默认入口

处理任意抖音视频时，优先使用一键脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\process_douyin_video.ps1 -Url "{DOUYIN_URL}"
```

收藏页链接可以直接传入，脚本会从 `modal_id` 中提取真实视频 ID：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\process_douyin_video.ps1 -Url "https://www.douyin.com/user/self?modal_id=7651933224649706795&showTab=favorite_collection"
```

默认值从这里读取：

```text
config/defaults.json
```

## 默认配置

| 项 | 默认值 |
| --- | --- |
| conda 环境 | `douyin-qwen-asr` |
| ASR 模型 | `Qwen/Qwen3-ASR-1.7B` |
| 时间戳模型 | `Qwen/Qwen3-ForcedAligner-0.6B` |
| 语言 | `Chinese` |
| 时间戳策略 | `auto`，5 分钟以内启用 forced aligner |
| 模型缓存 | `.hf-cache` |
| Obsidian 写入方式 | 直接写入 Vault 根目录 |
| Obsidian Vault | `E:\Obsidian-projects\SecondBrain_Vault\SecondBrain_Vault` |

笔记路径规则固定为：

```text
$OBSIDIAN_VAULT_PATH/{标题}.md
```

不要写入 `douyin_text` 子目录。

## Conda 环境要求

完整说明见：

```text
docs/SETUP_QWEN3_ASR.md
```

快速复现：

```powershell
conda create -y -n douyin-qwen-asr python=3.12
$env:PYTHONNOUSERSITE = '1'
conda run -n douyin-qwen-asr python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
conda run -n douyin-qwen-asr python -m pip install --no-cache-dir -r requirements-qwen-asr.txt
```

也可以执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_qwen_asr_env.ps1
```

RTX 5060 Ti 16G 需要 CUDA 12.8 版 PyTorch 来支持 `sm_120`。

## 默认输出

每个视频的工作目录：

```text
outputs\douyin\{video_id}\
```

输出文件：

| 文件 | 内容 |
| --- | --- |
| `video.*` | 下载的视频 |
| `video.info.json` | yt-dlp 元数据 |
| `audio.wav` | 16 kHz 单声道 WAV |
| `text_plain.txt` | Qwen3-ASR 纯文本稿 |
| `text.txt` | 时间戳稿 |
| `asr_result.json` | ASR 模型、设备、语言、时间戳配置 |

Obsidian 笔记由 `scripts/write_obsidian_note.py` 写入 Vault 根目录。

## 手工 ASR 调用

如果只需要对已有音频转写：

```powershell
$env:HF_HOME = Join-Path (Get-Location) '.hf-cache'
$env:HUGGINGFACE_HUB_CACHE = Join-Path (Get-Location) '.hf-cache\hub'
conda run -n douyin-qwen-asr python scripts\qwen3_asr_transcribe.py --audio "outputs\douyin\{video_id}\audio.wav" --out-dir "outputs\douyin\{video_id}" --language Chinese --timestamps auto
```

## 注意

- 首次运行会下载 `Qwen/Qwen3-ASR-1.7B`；5 分钟以内的时间戳还会下载 `Qwen/Qwen3-ForcedAligner-0.6B`。
- 纯文本稿以 `text_plain.txt` 为准；`text.txt` 更偏时间定位辅助。
- 环境变量 `OBSIDIAN_VAULT_PATH` 可以覆盖默认 Vault，但仍然写入 Vault 根目录。
