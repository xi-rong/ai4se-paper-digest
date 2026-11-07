# 云端设置与新聊天交接

仓库：https://github.com/xi-rong/ai4se-paper-digest （Private）

## 本轮已完成的准备

- 环境名 `ai4se-paper-digest`，Only me；环境配置ID `a039e561-c476-487a-a822-3ef38e05576b~asenvcfg_7e4878ae5d008191adb165121a5f320f`。
- 北京时间2026-11-03 16:37界面明确确认发布，列表ready/runnable=true。发布不是系统验收，见evidence/environment-published.json。
- 设置任务 `01a1a07d-21f2-714f-be53-194b9ba6c02c` 运行20项测试通过；GitStore复用云端授权写入并读回 `digest-state`，提交 `de97ddfc44fa3678f474e12df4c2da0e4c02a1f2`，不需要新增GitHub token。
- 设置VM的arXiv受旧网络策略拒绝，未绕过；首次新任务启动容器HTTP400，不能标为论文API失败。发布成功后的复验任务 `01a1a08f-a324-70c0-893a-7367656b902a` 的最终结果应优先查看。
- 发布后复验已成功：20项测试，arXiv200，4篇种子/两份reviews/预览，dry-run状态哈希不变且outbox为空。另一个新VM成功读旧探针，再写 `b9c60f8016337237371943063245f6ce296138f9` 并重读；跨任务状态已验证。证据 `evidence/cloud-postpublish-validation.json`，由云任务提交 `dc9903c886ba688930e0a4d7987b4d3ae908e732`。该首轮网络诊断使用临时transport instrumentation保留精确错误，原始CLI不替换transport的完整采集复验另记。
- 近30天本地最初采集合并970条，连同种子总973条。随后原始CLI已在新云任务完整运行：`collect --rss`退出0，新增968条，远端总972条；596条候选待审核，4条已审核。两次30天窗口起点不同，不能把计数差直接当成漏采；各自API分页均完整。全量云端元数据现已保存私有状态分支，非仅存在VM。
- 原始CLI四篇重跑 `new_versions=0`；日报/历史/周报预览均成功，前后远端头与状态哈希不变、outbox为空，已有send状态未变；证据见 `evidence/cloud-original-cli-validation.json`。
- 最终源码d94b2af的21项测试已在云端通过，原始日报CLI确认保留collect覆盖且不修改远端状态；证据 `evidence/cloud-final-check.json`，云任务提交260dafc。
- 日报/周报预览已生成；真实邮件、定时桥接和关机验证均未完成。没有外部调度/额外模型API/付费服务。

## 下一阶段直接复制到云端聊天

> 继续本仓库的个人 AI4SE 论文追踪系统。先读 AGENTS.md、docs/CLOUD_HANDOFF.md、docs/ACCEPTANCE.md 与最新 evidence，跳过已通过的环境创建、发布、21项测试、原始CLI采集、跨任务状态和dry-run验证。先运行 `python3 -m paper_digest.cli --storage git status` 读取私有digest-state；从已保存的596条候选继续摘要/正文审读，优先跨仓库bugfix，扩大已验证的阅读清单并记录未审核范围。补齐会议具体论文列表、期刊官方接口、作者ID等来源；S2 429与DBLP挑战要如实标注。用户已注册 Brevo，固定收件人和经 Brevo 验证的发件人均为 shaoyibo102@gmail.com；按 docs/OPERATIONS.md 验证云端网络密钥注入、Brevo 事务邮件启用和真实投递。仅在云端保险库填凭证，测试完整HTML邮件和发送失败保留待发。最后实测原生云定时任务通过受支持工具启动指定编程环境的桥接，安排短期测试并保留日志；未证实前不要启用正式日报或外部调度。关机测试由我配合。未授权购买服务，不用GitHub Actions。所有新审核、发送记录通过GitStore持久保存，预览不得消耗待发。

## 创建和发布

Settings → Codex Cloud → Environments → Create environment，或新聊天 Work in → Cloud → 选择环境 → 创建环境。
只选择 `xi-rong/ai4se-paper-digest`。可见范围 Only me。Python 3.11+，无需模型 API 或第三方 Python 依赖。

允许 HTTPS 域名：`export.arxiv.org`、`arxiv.org`、`rss.arxiv.org`、`api.github.com`、`github.com`、`raw.githubusercontent.com`、`api.semanticscholar.org`、`dblp.org`。按实际需要添加 `huggingface.co` 与各会议/出版社。当前邮件服务使用 `api.brevo.com`；还须验证密钥注入及请求是否可用。

Install script/设置验证：

```sh
python3 --version
python3 -m unittest discover -s tests -v
python3 -m paper_digest.cli seed --ids 2609.33382 2603.03194 2407.01489
python3 -m paper_digest.cli review examples/seed-reviews.json
python3 -m paper_digest.cli preview --kind history --out var/cloud-preview
```

保存命令输出、云端任务链接与运行时间。所有错误处理后再点击 Publish，等待 Environment published。发布不是启动新任务；在发布环境点击 Start a new task 才测试快照可复现性。

## 环境重建时的完整验证提示（正常续接无需重复）

> 继续这个仓库中的个人 AI4SE 论文日报项目。先读 AGENTS.md、docs/PLATFORM_EVIDENCE.md、docs/OPERATIONS.md、docs/SOURCES.md，确认当前确实在 Codex Cloud。不要购买服务、不要用 GitHub Actions、不要创建本地定时器。先运行测试和 seed/review/history preview，给出云端任务与日志证据。检查私有 digest-state 分支已有状态，先实测 --storage git 复用云端原生 Git 授权；通过 GitStore 做带分支头比较的探针写入并记录 SHA，若成功无需新增 token。只有原生 Git 写入确实不可用时，才请我在 Personal vault 配置 DIGEST_GITHUB_TOKEN（api.github.com 专用 HTTPS 网络密钥），并改用 --storage github。随后在第二个新的云端聊天读取该探针，验证跨任务持久化，不以 VM 本地文件替代。执行近30天 arXiv 回顾和 RSS，将候选交由你阅读摘要/正文，写 review JSON，再生成历史清单；明确来源失败及未接入范围。之后按 docs/OPERATIONS.md 验证 Brevo HTTPS 发信，固定收件人 shaoyibo102@gmail.com；凭证只在云端安全配置填写。最后实查原生云端定时能否绑定/启动此环境，安排一次短期启动测试，记录配置、预期与实际时间、运行 ID 和日志。若没有受支持的衔接，不虚构；给出具体缺口与需我选择的最小外部替代。各项验收成功后才启用 Asia/Shanghai 每日09:00、每周一09:00额外周报（周一日报照常）；无新增不发空日报。关机运行由我配合验证。更新 evidence 与逐项验收表。

## 待补证据

- 环境 ID、发布状态：已记录于evidence/environment-published.json；设置页为当前云端设置聊天的环境面板。
- 新云任务运行、arXiv请求、预览：已验证；原始CLI完整采集复验见最新证据。
- 私有 GitHub 状态跨云任务读写：GitStore已验证，无新增凭证；备选HTTPS令牌模式仍未配置/实测。
- 完整日报真实邮件：已选 Brevo HTTPS 和 Gmail 固定收件地址，尚需验证凭证注入、实际发送和入箱，见 docs/OPERATIONS.md。
- 云端定时桥接、短期测试与关机执行：待验证。

不要把仅源码完成、仅本地成功、仅通知邮件收到写作系统验收完成。
