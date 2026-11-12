# 论文日报运维手册

本文件记录当前操作；`CLOUD_HANDOFF.md`、`PLATFORM_EVIDENCE.md` 和旧验收记录包含历史过程，不能用旧日期的状态代替实时平台状态。

## 检查与发布

从仓库根目录执行 `python3 scripts/check_release.py`：它只验证配置并运行本地测试，不访问云端状态、不发送邮件。生产使用的具体命令显式加 `--storage git`。`python3 -m paper_digest.cli --storage git check-config` 只检查配置意向，不检查定时平台或邮箱服务，不读取凭证。

发布代码前查看变更和测试结果；合并后核对主分支代码，并用云端真实运行记录确认代码版本、采集结果和出站情况。本地测试通过、合并成功、邮件服务受理均不能单独证明完整流程成功。回退用代码版本回退，不重置 `digest-state`，不清空待发或已发送记录。

## 日报范围与空日报（2026-11-12）

按首次投稿时间转换为 Asia/Shanghai 日期，仅纳入今天和前两个自然日、且从未推送的论文；新发现的旧论文和旧论文新版不能绕过日期限制。没有选中项也生成并发送一封说明原因的空日报。若采集不完整或审核不足，必须明确限制，不能声称没有新论文。入队与send均遵循durable outbox、固定收件人及幂等保护；旧待发超出范围时不能直接补发或清空历史，先核对原结果且避免重叠。

## 日常状态

- `python3 -m paper_digest.cli --storage git status`：查看论文和审读数量、待发箱状态计数、最近一次采集覆盖与 arXiv 游标；不输出原始候选内容或邮件正文。
- `python3 -m paper_digest.cli --storage git pending`：列出待发、发送中和需重试项；已发送和已替代项不作为待处理项。
- `python3 -m paper_digest.cli --storage git translation-needed --kind daily`：输出当天选中论文中需翻译的标题和摘要。周报使用 `weekly`。
- `python3 -m paper_digest.cli --storage git preview --kind daily --out var/daily`：生成 HTML 和 Markdown 预览，不写状态、不消耗待发论文。入队前须完成完整翻译。

`partial`、`failed`、`deferred` 和 `unconfigured` 均不意味着全量采集成功。429 表示受到限流；不要频繁重复请求，采集游标未推进时后续运行会回查。发送结果 `sent` 表示服务商受理，不代表入箱；不确定结果超出幂等窗口必须先核对服务商记录。

## 调度与配置

实际日程由云端定时任务管理，不由 `config.json` 或本地进程启动。2026-11-09 页面显示日报每天 09:00、周报每周一 09:00，时区 Asia/Shanghai；状态可能变化，以平台页面为准。调整时间、暂停或恢复需在平台修改相应的日报或周报任务，并核对下一次运行；配置文件同名字段仅作意向记录。周一两个任务都保留，采集通过共享状态协调。

仅向 config.json 中用户确认的固定地址发送，邮件服务凭证保存在云端安全配置中，不放入仓库或日志。日志中不打印凭证、请求头、邮件正文或采集的原始候选；Python 进程在持久化之前异常退出时，单靠状态文件不能保证留下完整记录，应查看云端任务日志。
