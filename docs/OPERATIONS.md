# 操作、持久化与邮件

## 当前正式运行说明（2026-11-09）

云端任务现为每天 09:00 日报、周一 09:00 另发周报（Asia/Shanghai）；唯一收件地址以 config.json 为准。下文旧的“尚未启用”等历史状态不代表当前任务状态，实际以云端任务页面为准。

正式运行先以 `--storage git pending` 查看未发送消息，按提供商幂等窗口处理。审读后以 `--storage git translation-needed --kind daily`（周报改 weekly）列出需要译文的完整英文标题和摘要；Codex 按输出逐条翻译，写成 `[{"paper_id":"...","version":1,"title_zh":"...","abstract_zh":"..."}]`，用 `--storage git translations 文件名` 保存，再生成预览和入队。普通预览可显示待翻译占位，入队前必须提供原摘要和完整译文。翻译只允许当前论文版本，不能将旧译文用于新版本。

arXiv 采集使用远端共享租约协调并发任务（最长 30 分钟），最近一次明确 429 后冷却 30 分钟；其他来源仍可继续，延期会显示为来源限制，游标不推进。租约过期后下次运行可恢复；采集后保存若发生竞争，应重新读取状态和审查来源覆盖，避免盲目发送或覆盖。

## 2026-11-07 定时任务默认时区修正

按用户要求对现有两项任务分别调用原生 automations.update，设置 default_timezone=Asia/Shanghai，并保留 is_enabled=true 和原 schedule。随后 automations.peek 回读完整任务：两项 default_timezone 与 DTSTART 的 TZID 均为 Asia/Shanghai；日报仍每天09:00（首次2026-11-08），周报仍周一09:00（首次2026-11-09）。exact_schedule、提示、任务ID、thread_id、environment_selection=inherited 和完整 environments 数组均与更新前一致，仍继承 ai4se-paper-digest 已发布Cloud配置。

update均成功，无工具错误；没有创建任务或发送邮件。display_schedule=null、next_run_time=null，尚无运行结果；此次通过原生字段确认时区一致，未目视检查界面，不能声称界面刷新已实测。完整更新前/后字段、请求、返回和逐项检查见 evidence/formal-schedules-timezone-fix-2026-11-07.json；原创建证据保留当时 America/Los_Angeles 历史值，不代表当前配置。


## 2026-11-07 正式调度授权与创建（优先于下方旧记录）

用户明确要求立即启用正式发送，不再等待额外预验收；当前唯一固定收件人为 syb38324@126.com。已安全 fetch/快进 main 至 ef77516，23项测试通过，远端状态 revision 16（972篇、4份审读；旧邮件 sent/superseded）读取成功，无重复发送。

原生 automations.create 已创建并启用日报和周报：Asia/Shanghai 每天09:00，首次2026-11-08；每周一09:00额外周报，首次2026-11-09，周一日报照常。任务提示包含采集、Agent实际审读、远端Git持久化、Brevo完整邮件、固定地址、去重、失败保留、无新增不发日报等要求。未使用本地自动化、GitHub Actions或外部调度。

create 输入无环境选择字段，初始返回 environments=null；随后 automations.peek 确认两项均 is_enabled=true、environment_selection=inherited，继承 ai4se-paper-digest 的已发布 environmentConfigId a039e561-c476-487a-a822-3ef38e05576b~asenvcfg_7e4878ae5d008191adb165121a5f320f、当前Cloud environmentId 和 /workspace。原生任务已绑定托管Cloud配置，不依赖本机定时器；尚未观察首次定时运行及电脑关闭实测，不把配置成功当作完整流水线执行成功。next_run_time=null，实际运行/投递待平台日志。创建时 DTSTART 为 Asia/Shanghai、default_timezone 为 America/Los_Angeles；随后已将 default_timezone 修正为 Asia/Shanghai 并回读确认，见顶部修正记录。

config.schedule.enabled=true 记录已启用意图；真正调度由平台两项任务控制，暂停/恢复须同步管理原生任务。完整请求、返回字段、任务标识和限制见 evidence/formal-schedules-2026-11-07.json。没有在此次启用中发送邮件、修改白名单或生产发送状态。当前密钥ready与此前投递/跨任务验证不保证未来网络永远可用。


## 手动与预览

所有命令在仓库根目录使用 Python 3.11+。源目录即可运行，无需 pip：

```sh
python3 -m paper_digest.cli collect --rss --out var/candidates.json
python3 -m paper_digest.cli collect --weekly --rss --out var/weekly-candidates.json
python3 -m paper_digest.cli review var/reviews.json
python3 -m paper_digest.cli preview --kind history --out var/history
python3 -m paper_digest.cli preview --kind daily --out var/daily
python3 -m paper_digest.cli preview --kind weekly --out var/weekly
python3 -m paper_digest.cli status
```

首次采集默认近30天；每日从最后完整成功水位往前回查7天，漏跑后自动扩展窗口。任何 arXiv 查询失败/截断都不推进全局水位，已取得记录保留。RSS 用于核对公告批次/交叉分类；未知 ID 进入补充候选，必须再通过 `seed --ids ...` 补齐元数据。官方 API 检索按全部分类属性覆盖交叉分类，主分类另存。

短名单不是自动审核。运行中的 Codex Agent 审读摘要或正文，按 seed-reviews 字段写 JSON 再导入。无额外模型 API。原生 Agent 只有在定时启动链路验证后才能无人值守分析；Python 脚本单独运行不自动产生研究结论。

## 跨任务状态

`config.json.storage.mode` 初始 local，只用于准备和测试。状态分支 `digest-state:state.json` 已创建，源码在main，状态不使用Actions。

优先在云端实测 `--storage git`：复用环境原生Git授权，通过fetch/show读取、临时index构建提交，再用分支头的`--force-with-lease`做比较后更新。新提交以前次分支头为父提交；竞争写入会拒绝，不覆盖他人的更新。它不切换工作区、不打印或读取密钥。此后端已用两个独立本地clone与bare remote做跨次读写和竞争写入测试；真实云端push及新任务读回已验证，见evidence/cloud-postpublish-validation.json，无需新增GitHub token。

备选 `--storage github` 通过 Contents API 的blob SHA比较更新；大于1MB的响应通过Git Blob API读取。已有GitHub插件/原生git授权不自动代表Python HTTPS凭证已配置。

配置保险库：Settings → Codex Cloud → Personal vault → Add → Network secret；Key=`DIGEST_GITHUB_TOKEN`，Allowed domains=`api.github.com`，Applies to=本环境。使用仅限此私有仓库的 fine-grained token，Contents Read/Write；原始值不能进聊天、日志或源码。GitHub 插件已连接不代表 Python 自动继承同一凭证。

本地存储使用进程锁+原子替换，GitHub 用 blob SHA 比较后更新（CAS）。冲突直接退出，重新加载后重做，不盲目覆盖。没有跨网络永久锁。发送前持久抢占10分钟租约，外部操作后重新读取并核对租约。每条消息保存完整正文、事件集合、发送尝试、提供商 ID。

精确 arXiv ID 和正式 DOI 合并；arXiv 自身 DOI 与正式 DOI 不同，需来源提供明确映射再关联。题目相似匹配只可供人工核对。JSON 随历史增长，个人规模先保持简单；仓库状态超过约500KB应分片/迁移，当前无自动归档。仓库读写 API 有额度，实际费用取决于 GitHub 计划，未购买额外存储。

## 完整邮件

Semantic Scholar若需要官方key，可在同一云端保险库添加`DIGEST_S2_TOKEN`，Allowed domains仅`api.semanticscholar.org`，程序用`x-api-key`头发送。它是文献服务凭证，不是模型API。当前未配置，未认证共享限流仍可能返回429，失败需保留而不能报告为零引用。

目前选择 Brevo HTTPS 事务邮件，固定发件人为 `shaoyibo102@gmail.com`，收件人为 `syb38324@126.com`；Brevo 后台显示该 Gmail 发件人已验证。2026-11-07代理鉴权200，单封测试201受理并查询到delivered；这不证明收件箱位置或已读。详见evidence/cloud-brevo-acceptance-2026-11-07.json。免费邮箱作为发件人的实际投递和可能的发件人改写需要实测。无需 126 SMTP、服务器或 Tailscale。

在 Personal vault 创建仅供本环境使用的 Network secret `DIGEST_MAIL_TOKEN`，并按云环境实际界面配置 `api.brevo.com` 的网络访问与密钥使用。凭证不得进入聊天、仓库或日志。仅在云端实测后确认代理是否正确注入。

```sh
python3 -m paper_digest.cli --storage git preview --kind daily --out var/daily --enqueue
python3 -m paper_digest.cli --storage git send MESSAGE_ID --to syb38324@126.com
```

`--enqueue` 会创建待发记录；普通预览不加此参数，也不消耗待发论文。先核对待发内容和固定收件人。Brevo 接口：https://developers.brevo.com/reference/send-transac-email 。Brevo 的幂等窗口为15分钟，程序超过14分钟停止自动重试并要求对账；即使 API 返回 ID，也只证明受理，不保证入箱。发送后状态保存失败时，应在窗口内以原正文和原键重试，超时先核对 Brevo 日志。Resend 适配器仍在代码中，但当前未选用。

失败保留 retry 与正文，收集继续；无人值守故障通知尚无独立监控链路，未验证前不能承诺必达。固定收件地址之外不发送，GitHub 资料邮箱不能代替确认。

## 调度、暂停与恢复

当前 schedule.enabled=false；这是意图配置，不是平台定时任务。没有安装 cron，没有 Actions。用户已于2026-11-07确认 Asia/Shanghai 日报每天09:00、周报每周一09:00；周一日报照常，周报额外发送。这是期望启动时间，实际入箱时间待测。改配置不会自动更改平台任务，必须同步编辑平台定时配置并复核下次运行。

待云端定时接入后，通过 Scheduled 暂停/恢复对应两个任务，并留存配置和日志证据。现在手动执行即可，退出聊天不会启动任何未配置的定时任务。恢复后先处理待发箱再生成新日报；部分失败的采集从未推进水位补查。

## 成本边界

当前新增付费服务=0，未购买模型 API、邮件套餐或外部调度。Codex 云运行消耗当前计划/额度，不能把已有订阅视为无限免费。邮件、外部调度和数据库仅在用户选择后按官方当期价格估算。本版本不部署常驻服务。

## 2026-11-07 发送去重与历史

已发送消息f875b9f3ee3640a7857cd037f68d6648重跑send返回already_sent，阻断Python网络时transport调用0，远端状态不变。旧400消息70849d806da51fac48e919e06d267951已在报告和事件完全一致、uncertain=false条件下标superseded并关联替代项，保留原payload_hash、首次尝试和正文；发送器拒绝它。不得将其重置为retry或新建同批重复报告。sent在代码中表示受理；delivered须另查提供商事件。

云端新任务可能拿到旧源码快照：检查工作区并安全fetch/快进main，重读文档、运行测试后再操作。代理出口曾变化，既有IP放行不保证永久连通。正式schedule.enabled仍为false。
