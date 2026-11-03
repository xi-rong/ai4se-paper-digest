# AI4SE Paper Digest

个人科研论文追踪与中文 HTML/Markdown 日报、周报。优先验证 Codex Cloud；无 GitHub Actions 定时器，无额外模型 API 依赖。

**当前状态：准备与验收阶段，尚未启用正式调度或真实邮件。** 以 [平台证据](docs/PLATFORM_EVIDENCE.md) 和 [云端交接](docs/CLOUD_HANDOFF.md) 的最新记录为准。

Python 3.11+，标准库即可运行：

```sh
python3 -m unittest discover -s tests -v
python3 -m paper_digest.cli seed --ids 2609.33382 2603.03194 2407.01489
python3 -m paper_digest.cli review examples/seed-reviews.json
python3 -m paper_digest.cli preview --kind history --out var/history
python3 -m paper_digest.cli collect --rss --out var/candidates.json
python3 -m paper_digest.cli status
```

`collect` 有来源失败/截断时返回 2，成功数据仍保存；没有新论文与执行失败明确区分。候选需 Codex Agent 根据摘要/正文审读，再写 review JSON，不能只凭关键词入选。

`preview` 默认是 dry-run：不排队、不消耗论文、不标为已发送。`--enqueue` 才创建持久待发箱。真实发送需固定收件地址确认、HTTPS 邮件服务和云端保险库配置。

- [研究范围](docs/RESEARCH_SCOPE.md)
- [来源接入状态](docs/SOURCES.md)
- [运行与安全配置](docs/OPERATIONS.md)
- [云端新对话交接](docs/CLOUD_HANDOFF.md)
- [初始种子阅读预览](examples/history-seed-preview.md)（不代表已完成近30天全量检索）
- [真实日报预览：CrossSWE](examples/daily-preview.md)（新发现的近期投稿，未发送）
- [近30天已审读条目及独立标记种子](examples/history-30day-reviewed-preview.md)（其余候选待审核）
- [周报样例](examples/weekly-seed-preview.md)（本周首次发现的历史种子，未发送）

模块：`collectors` 采集；`review` 证据审核；`reports` 报告；`storage` 本地原子写/GitHub CAS；`mailer` 持久待发与 HTTPS 发送；`cli` 手动运行。
