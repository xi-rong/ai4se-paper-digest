# 阿里云邮件通路检查与待审设计

> 当前方向（2026-11-07）：优先简化为Codex Cloud通过HTTPS邮件API向126收件箱发送报告。阿里云服务器和Tailscale仅是保留126 SMTP发件时的可选网络方案，不是日报系统的必要条件。未实施VPN、转发服务或服务器安装；暂不要求用户注册Tailscale。原生Cloud定时启动仍单独待验收。

用户已在阿里云服务器执行匿名检查，返回北京时间15:25:50、Linux x86_64、Tailscale未安装、TLSv1.3与EHLO250。证据来源是用户提供的终端输出，见evidence/aliyun-smtp-user-probe.json；不等于Cloud端到端发信成功。

## 当前授权与事实（2026-11-07）

用户指定服务器`39.105.143.134`，允许先检查。截图显示本人通过root密码登录Ubuntu24.04.2；这不是本项目已完成远程系统核验的证据。本地独立SSH批处理连接返回`Permission denied (publickey,password)`，未运行远程命令；工具安全策略拒绝控制已登录的iTerm2。未索取服务器密码、未读取邮箱凭证，未安装软件、开放端口、修改防火墙或创建服务。

`scripts/check_mail_bridge.py`是只读检查程序，默认只输出JSON：系统、Tailscale是否存在及自身状态、socat是否存在、到smtp.126.com:465的验证证书TLS连接及匿名EHLO。不会执行AUTH或发送邮件，不会输出Tailscale其他设备/用户/密钥。已在本地macOS运行通过；用户另已在阿里云运行简化版检查，结果记录如上。

## 已验证的Cloud缺口

真实Cloud任务在北京时间15:15:42连接受支持的proxy:8088时返回ECONNREFUSED，未到达网易。VPN未配置，TCP授权为空，见`evidence/cloud-smtp126-diagnosis.json`。随后在当前账号设置→Codex云端→环境编辑→高级实际看到了“VPN Tailscale / 未设置密钥 / 编辑Tailscale认证密钥”，因此账号具备配置入口，尚未配置或测试VPN。编辑入口自动创建了设置草稿聊天`01a1b4de-1069-7346-b48d-5befe1c5903b`；没有改变网络/凭证，没有发布新版本。

## 候选最小设计（未部署，需用户选择）

Codex Cloud继续负责采集、研究审读、报告与GitStore状态。发信连接使用：

`Cloud SMTP client → 平台TCP CONNECT → Tailscale私网 → 阿里云固定目的地TCP转发 → smtp.126.com:465`

服务器只转发到固定的网易SMTP465，不提供任意目的地代理，不监听公网地址。目标为私网专用端口（拟2465，实际先查占用），Tailscale权限仅允许日报任务身份访问该端口。SMTP的TLS从Cloud客户端一直到网易；必须仍用smtp.126.com进行证书和主机名验证，不能把私网转发地址误作TLS服务器身份。服务器不保存126授权码，不解析或记录SMTP内容。后续实现必须验证这些边界，而不是仅有监听端口就算成功。

原始SMTP授权码由用户填Cloud Personal vault的独立Environment variable，通过环境请求键交付程序；不是HTTPS Network secret。先验证Cloud到转发端的匿名TLS/EHLO，再配置授权码和真实发送适配器。SMTP没有通用服务端幂等保证；DATA后连接断开等不明结果必须持久化为待对账，不能盲目重发。

仅网络转发服务在阿里云常驻，不在该服务器安装日报调度器。原生云调度链路仍单独验收；本设计不会自动解决调度缺口，也不使用GitHub Actions。

## 成本与操作边界

如复用现有服务器，不需要为这一步购买新服务器；现有服务器账单、带宽与维护仍存在。Tailscale当前Personal计划有免费额度，并列出临时资源1000分钟/月；Codex要求Reusable+Ephemeral认证键，实际在线计量和账号适用性必须核实，不能承诺无限免费或自动购买超额额度。

下一步依次为：用户返回阿里云只读检查结果→确认服务器到126可达→准备具体服务、权限和回滚配置供审阅→取得用户对安装/接入VPN的选择→安全填写Tailscale凭证→Cloud匿名端到端测试→网易授权码与真实邮件测试。当前只授权第一阶段检查，不自动安装或拓宽访问。

参考：[Cloud TCP/VPN文档](https://learn.chatgpt.com/docs/environments/cloud-environments#connect-to-tcp-services)、[Tailscale官方价格](https://tailscale.com/pricing)。
