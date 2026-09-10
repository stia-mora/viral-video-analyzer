# Qwen3-ASR 默认环境说明

本项目默认使用 `Qwen/Qwen3-ASR-1.7B` 做抖音视频 ASR，不再使用 faster-whisper。

## 默认值

默认配置在：`config/defaults.json`

```json
{
  "conda_env": "douyin-qwen-asr",
  "asr_model": "Qwen/Qwen3-ASR-1.7B",
  "forced_aligner_model": "Qwen/Qwen3-ForcedAligner-0.6B",
  "language": "Chinese",
  "timestamps": "auto",
  "hf_cache": ".hf-cache",
  "obsidian_vault_path": "E:\\Obsidian-projects\\SecondBrain_Vault\\SecondBrain_Vault",
  "obsidian_write_mode": "vault_root"
}
```

Obsidian 笔记直接写入 vault 根目录：

```text
E:\Obsidian-projects\SecondBrain_Vault\SecondBrain_Vault\{标题}.md
```

不写入 `douyin_text` 子目录。

## Conda 环境

环境名：

```text
douyin-qwen-asr
```

Python：

```text
3.12
```

GPU：RTX 5060 Ti 16G。

RTX 5060 Ti 是 `sm_120`，需要 CUDA 12.8 版 PyTorch。不要用旧的 `torch 2.6.0+cu126`，它会提示不支持当前 GPU。

## 从零安装

在项目根目录执行：

```powershell
conda create -y -n douyin-qwen-asr python=3.12
$env:PYTHONNOUSERSITE = '1'
conda run -n douyin-qwen-asr python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
conda run -n douyin-qwen-asr python -m pip install --no-cache-dir -r requirements-qwen-asr.txt
```

也可以直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_qwen_asr_env.ps1
```

## 验证环境

```powershell
conda run -n douyin-qwen-asr python -c "import torch, qwen_asr; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
```

期望看到类似：

```text
2.11.0+cu128
True
NVIDIA GeForce RTX 5060 Ti
```

## 默认处理命令

后续处理抖音视频统一使用这个入口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\process_douyin_video.ps1 -Url "https://www.douyin.com/video/7651933224649706795"
```

收藏页链接也可以直接传入：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\process_douyin_video.ps1 -Url "https://www.douyin.com/user/self?modal_id=7651933224649706795&showTab=favorite_collection"
```

脚本默认会做这些事：

1. 从 URL 中提取视频 ID。
2. 下载视频和 `video.info.json`。
3. 用 `ffmpeg` 提取 `audio.wav`。
4. 在 `douyin-qwen-asr` 环境中调用 `scripts/qwen3_asr_transcribe.py`。
5. 使用 `Qwen/Qwen3-ASR-1.7B` 生成 `text_plain.txt`。
6. 5 分钟以内自动用 `Qwen/Qwen3-ForcedAligner-0.6B` 生成 `text.txt` 时间戳稿。
7. 把 Markdown 笔记写到 Obsidian Vault 根目录。

## 输出文件

每个视频的工作目录：

```text
outputs\douyin\{video_id}\
```

常见输出：

| 文件 | 内容 |
| --- | --- |
| `video.mp4` | 下载的视频 |
| `video.info.json` | yt-dlp 元数据 |
| `audio.wav` | 16 kHz 单声道 WAV |
| `text_plain.txt` | Qwen3-ASR 纯文本稿 |
| `text.txt` | 时间戳稿 |
| `asr_result.json` | ASR 模型、设备、语言、时间戳配置 |
| `note.md` 或 Obsidian 目标笔记 | Markdown 知识笔记 |

## 模型缓存

模型默认缓存到项目内：

```text
.hf-cache\hub\models--Qwen--Qwen3-ASR-1.7B
.hf-cache\hub\models--Qwen--Qwen3-ForcedAligner-0.6B
```

首次运行会下载模型，后续走缓存。
