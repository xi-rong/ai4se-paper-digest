# 验收台账

本轮交付阶段是项目准备、环境发布与最小验证；完整日报系统尚未启用。

| 项目 | 状态 | 证据/限制 |
|---|---|---|
| 私有代码仓库 | 已验证 | xi-rong/ai4se-paper-digest，Private |
| Codex Cloud 创建/发布 | 已验证 | environment-published.json，界面16:37发布确认 |
| 从新云任务运行 | 已验证 | 01a1a08f，运行环境connected/running |
| 云端测试 | 已验证 | 源码53a21ed，23项通过；cloud-brevo-acceptance-2026-11-07.json |
| 真实云端论文请求 | 已验证 | arXiv200，四篇元数据；首轮保留精确错误使用临时transport诊断，未修改源码 |
| 原始CLI完整采集 | 已验证 | cloud-original-cli-validation.json：collect退出0，14页API、4类RSS，状态分支972条论文；再次seed四篇new_versions=0 |
| 中文HTML/Markdown报告 | 已生成 | daily-preview、history与weekly样例；当前仅4条经过审读 |
| dry-run不消费状态 | 已验证 | 原始CLI预览前后远端头与完整状态不变，outbox为空；日报保留最近collect覆盖 |
| 跨云任务共享持久状态 | 已验证 | de97ddf旧探针→新VM读取→b9c60f8新探针并重读 |
| 同批数据重复/发送去重 | 云端验证通过 | sent重跑already_sent，阻断HTTP/socket，transport调用0，远端状态不变；superseded拒绝发送 |
| 邮件失败不丢内容 | 真实失败已验证 | 首次400保留正文和状态；后按严格比对标superseded，历史保留 |
| 并发冲突 | 测试通过 | 两个独立clone竞争提交，旧分支头更新被拒绝 |
| 部分采集失败准确标注 | 已验证 | 本地/云端S2 429、DBLP202；不是零结果 |
| 每周来源覆盖 | 未完成 | 作者ID、会议论文列表、期刊官方接口待配置，台账有明确状态 |
| 完整日报真实发送 | 测试报告已投递至收件服务器 | Brevo HTTPS向固定Gmail地址一次POST 201，事件delivered；非今日新增日报，收件箱位置及已读未验证；旧SMTP诊断仅为历史 |
| 原生云定时启动编程环境 | 待验证 | Scheduled云任务存在；表单无直接绑定，支持工具衔接尚未实测 |
| 正式日报/周报 | 未启用 | schedule.enabled=false；未创建定时任务 |
| 电脑关闭后执行 | 待用户配合 | 没有实验，不宣称通过 |

大致成本：本轮新增付费服务0；没有额外模型API。Codex云任务消耗现有计划额度。未来邮件服务或外部调度费用需选择后按官方价格核算；没有自行部署任何外部调度器。

剩余顺序：补齐候选审读与来源；邮件测试已获服务器投递，后续发信须另授权；继续原生云调度桥接短期测试→关机配合测试→正式启用。期望Asia/Shanghai每日日报09:00、周一额外周报09:00，尚未启用。
