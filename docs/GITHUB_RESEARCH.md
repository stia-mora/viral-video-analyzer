# 开源参考调研

检索日期：2026-09-10。范围为视频内容分析、短视频拉片、视频笔记与互动数据采集。Star 反映社区关注度，不代表分析质量；没有证据能够声明某个仓库是整个 GitHub 的绝对最高或最新。

| 项目 | 检索时 star | 发布 / 活跃度证据 | 对本项目的参考价值 |
| --- | ---: | --- | --- |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 189,973（API） | API pushed_at 2026-08-30；本地安装版 2026.08.19 | 保留原项目下载器，使用成熟提取器获取视频、公开指标、封面和可用评论 |
| [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 64.7k（页面） | 页面显示 807 次提交；未核实正式 Release 日期 | 已登录浏览器上下文与平台采集解耦、评论采样。该仓库有用途限制，只研究设计思路，未复制源码 |
| [BiliNote](https://github.com/JefferyHcool/BiliNote) | 7.3k（页面） | [最新 Release v2.4.5](https://github.com/JefferyHcool/BiliNote/releases)，2026-08-25 | 任务化视频处理、笔记持久化、下载失败恢复；保留本项目 Qwen3-ASR |
| [viral-video-analyzer](https://github.com/pelpeljakob-creator/viral-video-analyzer) | 119（页面） | [最新提交](https://github.com/pelpeljakob-creator/viral-video-analyzer/commits/main/) 2026-03-30，两个提交；未核实正式 Release | 最贴近需求：下载、抽帧、逐字稿、视觉描述、钩子与结构报告；研究了 downloader、vision_analyzer、viral_analyzer 三个服务 |
| [video-ai-analysis](https://github.com/yangchen0991/video-ai-analysis) | 14（API） | 创建 2026-06-01，pushed_at 2026-06-03 | 分镜时间码和多种观察视角；AGPL 项目，仅参考架构概念 |
| [viral-video-analyze](https://github.com/Danyangkk/viral-video-analyze) | 1（页面） | 已检索提交页，发布日期未充分核实 | 新的小型视频分析 Skill，参考证据驱动的报告组织 |

GitHub API 出现未认证限流，部分数字采用仓库公开页面当次值。初次搜索缓存中 viral-video-analyzer 为 104 star，打开仓库后已更新为 119，以页面值为准。未把最后提交时间混同于正式发布时间。

## 实施选择

采用本项目已有 Python、FFmpeg 和 Qwen3-ASR，新增 FastAPI、SQLite 持久任务与 React 工作台。不直接克隆竞争产品代码。抽帧和有时间戳的逐字稿作为证据输入；分别输出文案钩子、脚本结构、视觉观察、评论样本和创作建议。

与参考实现相比特别处理：缺失播放量不补零、零分母不计算比例、不输出未经标定的爆款概率；模型输出按字段验证，未观察的声音/连续运镜不能写成事实；模型失败仍保留视频资源与基础证据；团队数据端点均需认证。

本地视觉模型采用 [Qwen3-VL-2B-Instruct 官方模型](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)，Apache-2.0。模型能力有限，结果为辅助分析，不作为因果证明；也支持配置更强的兼容视觉 API。
