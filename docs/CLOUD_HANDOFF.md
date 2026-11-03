# 云端设置与新聊天交接

仓库：https://github.com/xi-rong/ai4se-paper-digest （Private）

## 创建和发布

Settings → Codex Cloud → Environments → Create environment，或新聊天 Work in → Cloud → 选择环境 → 创建环境。
只选择 `xi-rong/ai4se-paper-digest`。可见范围 Only me。Python 3.11+，无需模型 API 或第三方 Python 依赖。

允许 HTTPS 域名：`export.arxiv.org`、`arxiv.org`、`rss.arxiv.org`、`api.github.com`、`github.com`、`raw.githubusercontent.com`、`api.semanticscholar.org`、`dblp.org`。按实际需要添加 `huggingface.co` 与各会议/出版社。邮件服务确认后才加对应域名。

Install script/设置验证：

```sh
python3 --version
python3 -m unittest discover -s tests -v
python3 -m paper_digest.cli seed --ids 2609.33382 2603.03194 2407.01489
python3 -m paper_digest.cli review examples/seed-reviews.json
python3 -m paper_digest.cli preview --kind history --out var/cloud-preview
```

保存命令输出、云端任务链接与运行时间。所有错误处理后再点击 Publish，等待 Environment published。发布不是启动新任务；在发布环境点击 Start a new task 才测试快照可复现性。

## 云端新对话可直接复制

> 继续这个仓库中的个人 AI4SE 论文日报项目。先读 AGENTS.md、docs/PLATFORM_EVIDENCE.md、docs/OPERATIONS.md、docs/SOURCES.md，确认当前确实在 Codex Cloud。不要购买服务、不要用 GitHub Actions、不要创建本地定时器。先运行测试和 seed/review/history preview，给出云端任务与日志证据。检查私有 digest-state 分支已有状态，使用 GitHub 连接工具读取它；若程序尚未获得凭证，则请我只在 Personal vault 配置 DIGEST_GITHUB_TOKEN（api.github.com 专用 HTTPS 网络密钥）。通过程序 GitHubStore 做 CAS 写入一条探针并记录 SHA。随后在第二个新的云端聊天读取该探针，验证跨任务持久化，不以 VM 本地文件替代。执行近30天 arXiv 回顾和 RSS，将候选交由你阅读摘要/正文，写 review JSON，再生成历史清单；明确来源失败及未接入范围。之后取得我的固定收件地址和邮件服务选择，通过保险库配置并发测试邮件。最后实查原生云端定时能否绑定/启动此环境，安排一次短期启动测试，记录配置、预期与实际时间、运行 ID 和日志。若没有受支持的衔接，不虚构；给出具体缺口与需我选择的最小外部替代。各项验收成功后才启用 Asia/Shanghai 每日14:17、周日20:17；无新增不发空日报。关机运行由我配合验证。更新 evidence 与逐项验收表。

## 待补证据

- 环境 ID、发布状态与环境页链接：设置完成后记录。
- 新云任务重跑：待验证。
- 私有 GitHub 状态跨云任务读写：待验证（连接工具与 Python 凭证分别验证）。
- 完整日报真实邮件：待收件地址及服务。
- 云端定时桥接、短期测试与关机执行：待验证。

不要把仅源码完成、仅本地成功、仅通知邮件收到写作系统验收完成。
