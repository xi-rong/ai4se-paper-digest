# 平台能力与证据（2026-11-03）

本地准备与云端验收分别计数。以下结论不把三个产品表面混用。

官方原文：
- https://learn.chatgpt.com/docs/environments/cloud-environments
- https://learn.chatgpt.com/docs/automations
- https://developers.openai.com/training/walkthroughs/scheduled-tasks

| 能力 | 官方说明与实际检查 | 当前结论 |
|---|---|---|
| A 创建/发布/启动 Codex Cloud | 文档有 Work in → Cloud → Create environment → Publish；账号列表最初为空；网页实际出现创建入口且能访问新私有仓库 | 创建与发布正在实施，最终证据见交接状态 |
| B 定时启动指定编程环境 | 文档区分网页定时任务与本地项目；当前 automation_update schema 仅 local cron / 当前聊天 heartbeat，无 environmentConfigId 参数 | 未找到可直接绑定 Codex Cloud 环境的已验证调度；不可宣称绝对不支持所有账号 |
| C 关闭电脑仍运行 | Cloud 环境文档说明任务可在电脑睡眠时继续；本地项目调度需电脑与 app 在线 | 原生云端单次任务有文档支持；本项目关机测试待验证 |
| D 来源/模型/邮件/存储网络 | 环境可配置允许域名、直接变量及 HTTPS 网络密钥 | 本地真实 arXiv 已通；所有云端目标待实测 |
| E 无人值守完整邮件 | 未连接邮件发送插件；任务通知邮件与自定义 HTML 正文发送不同 | HTTPS 适配器已实现，真实发信待固定收件人/服务凭证 |
| F 跨任务状态 | 新任务使用发布快照，各自工作文件分离；重要数据需持久保存 | GitHub 私有状态分支 + CAS 实现；远端读写和新云任务读取需分别验证 |

工具实测：`list_cloud_environments({})` 初始返回 `environments: []`、`nextCursor: null`。GitHub 插件可读写新私有仓库。GitHub 插件没有创建仓库工具，因此通过已登录 GitHub 网页创建；创建后插件核实 visibility=private。桌面 app 的 Computer Use 被安全策略禁止；通过 Edge 的公开 UI 创建环境，不访问隐藏接口。

官方所述网络密钥把真实值保存在代理侧，仅对指定 HTTPS 443 目的地替换占位值；这不是 SMTP 密码，也不等同于程序能读到原始密钥。当前适配器选择 HTTPS，生产须实测占位值替换。

原生衔接缺口：即使 ChatGPT/Work 云端定时任务可运行连接工具，也不能据此证明它能启动指定编程环境。后续需在云端新聊天检查可用 create_thread/任务工具并做短期触发、保存任务 ID 和日志；只能在 UI/工具支持时配置。不得用本地调度或通知代替。

没有启用外部调度。若原生衔接最终不可用，可供用户选择托管 Scheduler + Python 云运行服务 + 状态仓库；这会引入额外账号/费用及独立分析模型问题，必须先获选择再部署。此处未声称已经实测。
