# douyin-video-to-txt

## 片析 · 团队视频研究平台

完整的团队 Web 前后端：账号、共享分析库、视频信息和评论采集、视频/封面下载、时间戳文案、视觉爆点分析、报告导出。默认本地 Qwen 语音与视觉模型，可配置自有模型 API。

启动：`powershell -ExecutionPolicy Bypass -File scripts/start_platform.ps1`

入口：http://localhost:8765 。初始账号保存在 `data/first-login.txt`。

- [运行与部署](docs/RUNNING.md)
- [GitHub 调研](docs/GITHUB_RESEARCH.md)
- [验收范围](docs/IMPLEMENTATION.md)

以下原有命令行流程继续保留。

当前默认流程：抖音视频 -> Qwen3-ASR-1.7B 本地转写 -> Markdown 笔记 -> Obsidian Vault 根目录。

默认配置见 `config/defaults.json`，conda 环境和安装说明见 `docs/SETUP_QWEN3_ASR.md`。

## 默认命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\process_douyin_video.ps1 -Url "抖音链接"
```

## 默认 ASR

- conda 环境：`douyin-qwen-asr`
- ASR：`Qwen/Qwen3-ASR-1.7B`
- 时间戳：`Qwen/Qwen3-ForcedAligner-0.6B`
- GPU：RTX 5060 Ti 16G，CUDA 12.8 PyTorch
- Obsidian：直接写入 `E:\Obsidian-projects\SecondBrain_Vault\SecondBrain_Vault`
