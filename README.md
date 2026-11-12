# AI4SE Paper Digest

面向 AI 辅助软件工程的个人论文追踪工具。系统在云端收集论文、由 Codex 审读并翻译标题和摘要，生成适合手机阅读的邮件日报与周报，同时保存 Markdown 报告和处理历史。

研究重点是**跨仓库缺陷修复**：一个需求可能需要同时修改多个关联仓库，并对所有目标仓库联合验证。也会关注可迁移的缺陷定位、代码检索、变更传播、多 Agent 协作和测试验证方法。

## 工作流程

```text
论文来源 → 采集与去重 → Codex 审读与翻译 → HTML / Markdown 报告
                  ↓                          ↓
         私有仓库保存历史和运行状态 ← 持久待发箱 → Brevo 邮件
```

- **采集**：优先使用 arXiv 官方 API 和 RSS；周报补充 Semantic Scholar、DBLP 及重点代码仓库发布信息。失败、限流和未接入的来源会明确标注。
- **筛选**：关键词仅用于产生候选。Codex 判断相关性，区分多仓库协同修改、外部仓库辅助单目标修复、单仓库跨文件修复，以及数据集覆盖多仓库但单任务只修改一个仓库。
- **报告**：日报最多 10 篇，仅收录北京时间当日及前两个自然日首次投稿、且尚未推送过的论文。没有符合条件的论文时发送说明原因的空日报；来源不完整时明确提示。每篇展示英文标题、中文译名和中英文摘要，并附原文及经过核实的相关链接。周报回顾本周实际发现并审读的论文。
- **状态与发送**：论文、审读、采集记录和待发消息存入私有仓库的 `digest-state` 分支。发送前持久化待发消息；失败时保留状态。服务商受理不等于邮件已进入收件箱。

## 当前运行方式

个人部署使用 Codex Cloud 环境和云端定时任务，邮件通过 Brevo HTTPS 接口发往配置中的固定邮箱，无需电脑保持开机，也不使用 GitHub Actions 作为调度器。

截至 2026-11-09，云端界面配置为 **Asia/Shanghai 每天 09:00 启动日报、每周一 09:00 额外启动周报**。配置和历史运行记录不保证以后每次都成功；实际任务状态及运行结果以云端任务页面和日志为准。来源可能限流或暂时不可用，参见[来源台账](docs/SOURCES.md)。

## 快速检查

需要 Python 3.11 或更高版本；运行时使用 Python 标准库，无需另购模型 API。

```bash
# 检查配置并运行本地测试；不发邮件、不访问云端状态
python3 scripts/check_release.py

# 只检查配置文件，不检查云端调度器的实际状态
python3 -m paper_digest.cli --storage git check-config
```

在已配置 Git 授权的云端环境中，可以查看持久状态并生成预览：

```bash
python3 -m paper_digest.cli --storage git status
python3 -m paper_digest.cli --storage git pending
python3 -m paper_digest.cli --storage git translation-needed --kind daily
python3 -m paper_digest.cli --storage git preview --kind daily --out var/daily
```

预览不入队、不改变发送状态。实际发送前，Codex 需审读论文并补齐所选论文的完整标题和摘要译文；使用 `preview --enqueue` 才会写入待发箱。具体步骤、周报命令、恢复与安全注意事项见[运维手册](docs/RUNBOOK.md)。本地默认使用本地状态，不能把临时文件当作跨云端任务的共享存储。

## 项目结构

| 路径 | 职责 |
| --- | --- |
| `paper_digest/collectors.py` | 论文与发布信息采集、初步候选筛选 |
| `paper_digest/review.py` | 审读结果和按版本保存的译文 |
| `paper_digest/reports.py` | 日报、周报和历史回顾的 HTML / Markdown 生成 |
| `paper_digest/storage.py` | 本地或私有 Git 分支的状态读写与冲突检测 |
| `paper_digest/mailer.py` | 持久待发箱、HTTPS 邮件发送和失败状态 |
| `paper_digest/operations.py` | 配置检查与运行状态摘要 |
| `paper_digest/cli.py` | 命令入口与流程编排 |
| `tests/`、`scripts/check_release.py` | 行为测试与本地发布前检查 |

## 文档

- [运维手册](docs/RUNBOOK.md)：检查、预览、发送、故障恢复及调度管理。
- [研究范围](docs/RESEARCH_SCOPE.md)：相关等级与任务类型的判定。
- [来源接入台账](docs/SOURCES.md)：各来源的接入情况与历史验证记录。
- [云端交接](docs/CLOUD_HANDOFF.md)和[平台证据](docs/PLATFORM_EVIDENCE.md)：环境搭建与平台能力的历史记录；部分阶段性状态可能已过时。

凭证只存放在云端安全配置中，不写入仓库、日志或聊天。来源受限、译文缺失或云端流程失败时，不将其描述成检索完成或发送成功。
