# 126 自发自收验证（2026-11-07）

用户固定收件地址已确认：`syb38324@126.com`。期望 Asia/Shanghai 每日09:00日报、周一09:00额外周报；周一日报照常。config.json已保存意图，enabled仍为false，修改配置不会创建平台调度。

用户要求暂停新服务注册，优先检查现有126邮箱自发自收。没有创建Brevo等新账号，没有购买服务，没有设置邮件凭证，没有实际发送邮件。当前生产邮件provider仍为unconfigured；现有代码只有可选Resend HTTPS适配器，尚无SMTP适配器。

## 实测与限制

- 本地macOS：smtp.126.com:465，TLS证书验证通过，TLSv1.3，EHLO返回250，服务器公告LOGIN/PLAIN/XOAUTH2。未执行AUTH、MAIL FROM、RCPT TO或DATA。证据：`evidence/smtp126-local-probe.json`。这只证明本机匿名连接可达，不证明账号已启用SMTP、认证成功、投递成功或云端可达。
- 126客户端需要在网页邮箱“设置→POP3/SMTP/IMAP”开启服务并生成客户端授权密码；授权码独立于网页登录密码。目前先不用生成或提交。
- 当前Cloud官方文档：公开HTTP/HTTPS与VPN网络分开；普通TCP服务须IPv4地址通过Tailscale路由，客户端使用proxy:8088 HTTP CONNECT。TCP不注入网络密钥；HTTPS网络密钥只在443替换。因此仅添加smtp.126.com到HTTPS允许域名不能视作SMTP配置完成。
- 本地聊天读取先前云端复验聊天失败（durable host unavailable）；环境列表仍ready/runnable。未重新执行云端SMTP探针，未据此声称SMTP服务或环境已失效。
- 需要额外、持续在线的VPN路由或邮件中继时，先解释成本、维护要求并由用户选择；不得借用户本机中继满足“关机后执行”，不得绕过平台网络限制。

## 云端续验提示

> 先阅读AGENTS.md、docs/CLOUD_HANDOFF.md及本文。确认当前真正处于已发布的ai4se-paper-digest Cloud环境，调用environment_status并读取当前network-policy。用户已要求暂停新邮件服务注册，先评估syb38324@126.com自发自收。先检查是否有受支持的smtp.126.com:465 TCP路径；若没有，不绕过HTTP代理或平台限制，不要求填写授权码，记录具体缺口。若有，在保持TLS证书验证情况下，仅测试匿名SMTP欢迎/EHLO/QUIT，不认证、不发送；记录环境ID、时间、路径、状态码。匿名连接通过后，再按实际平台机制请用户在Personal vault填写程序可直接读取的独立凭证变量；不可把HTTPS网络密钥占位符当作SMTP密码。随后实现并测试SMTP发送适配器，保留完整待发内容和并发租约；SMTP没有通用服务端幂等保证，DATA后断线等结果不明必须进入对账状态，不能盲目自动重发。真实测试仅发送至上述固定地址。每天09:00、周一09:00额外周报；定时链路与关机运行仍待验收，先不启用。

## 依据

- [126新增授权码说明](https://help.mail.126.com/faqDetail.do?code=d7a5dc8471cd0c0e8b4b8f4f8e49998b374173cfe9171305fa1ce630d7f67ac286624f309a1a7089)
- [Codex Cloud网络与凭证](https://learn.chatgpt.com/docs/environments/cloud-environments#connect-to-tcp-services)

## 用户提供的视频参考

[AI科研工作流（第7期）：科研日报邮件](https://www.bilibili.com/video/BV1ZMTu6VEUE/)，作者“耳总不是总UP”，页面日期2026-06-28，时长06:04。已通过浏览器读取简介、置顶评论，并抽查关键视频画面和中文字幕；不是完整逐句转录。

- 约03:32—04:01：扣子（Coze）工作流使用sendMail邮件插件，输入account、password、subject、text、to，另有attachments/html选项。插件画面标注支持QQ、163、Gmail，未证实126支持。
- 约03:45—03:53：演示QQ邮箱客户端协议页面与生成授权码。说明现有邮箱可作为发件账号；不是购买独立发件域名的教程。
- 约05:25：展示QQ邮箱内收到的论文报告；约05:33字幕提到让Coze每天定时执行。这里展示的是另一平台的工作流与发件插件，不是Codex Cloud SMTP或调度证据，也没有本项目电脑关机验收。
- 可借鉴：已有邮箱+客户端授权码、HTML邮件、可点击原文引用。仍须分别验证：126兼容性、本Cloud允许的网络路径、凭证交付、定时启动、历史去重和真实入箱。
- 若未来考虑调用托管邮件插件的HTTPS接口，需要另行确认平台账号、API可用性、免费额度与凭证托管；当前用户要求先不注册，未创建账号或工作流，未把授权码交给第三方插件。

作者置顶手册地址：https://my.feishu.cn/wiki/space/7618088038282841047?ccm_open_type=lark_wiki_spaceLink&open_tab_from=wiki_home 。本次两次页面导航超时，尚未读到手册或节点源码，不能声称已审查其实现。
