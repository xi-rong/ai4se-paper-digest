# 网络排查（2026-11-03）

**最新结果：发布后新VM已成功运行，arXiv200，网络白名单enforced。** 第一阶段旧VM拒绝和容器HTTP400均保留为历史故障，不代表现在不可用。云端S2仍429、DBLP仍202，故失败并非只发生在本机Clash。详见evidence/cloud-postpublish-validation.json。

## 云端与本地的独立证据

Codex Cloud设置任务 `01a1a07d-21f2-714f-be53-194b9ba6c02c`：已保存草稿revision 2包含arXiv，但运行VM spec/observed仍为1，额外allowed_hosts为空。`proxy:8080`对arXiv HTTPS CONNECT返回403，尚未到目标TLS握手。不能归因为本机Clash出口。后续发布并从新任务核验策略；保留代理与证书验证，不绕过网络限制。

本地Clash面板只读检查：TUN启用、系统代理关闭、规则模式、混合端口7897；面板显示美国DigitalOcean AS14061出口。没有改节点/规则/TUN设置，也不记录原始公网IP。

当前路线与显式HTTP代理`127.0.0.1:7897`请求同一公网IP回显服务，得到相同出口哈希；少量对照结果：

| 目的地 | 当前路线 | 显式Clash | 解释 |
|---|---|---|---|
| arXiv API | HTTP200 Atom | HTTP200 Atom | 本地可用 |
| Semantic Scholar | HTTP429 | HTTP429 | 限流；不是网络连不上，也不证明IP封禁 |
| DBLP API | HTTP202 HTML挑战 | HTTP202 HTML挑战 | 未取得API JSON，不能算接入成功 |

因为两条路线经TUN使用相同出口，这不是不同IP的因果对照。缺少不同出口实测，不能认定美国机房IP导致失败；也没有证据证明换住宅IP/付费节点一定解决。未来系统的真正云端出口由Codex管理，本机换节点不能替代云端验证。

## 官方支持的处理

1. Codex官方要求保存网络配置，发布/重新发布后在新任务验证：https://learn.chatgpt.com/docs/environments/cloud-environments#connect-to-services 。本项目按此路径继续。
2. Semantic Scholar官方说明未认证用户共享限额，建议个人API key、批量接口、减少字段：https://webflow.development.semanticscholar.org/product/api/tutorial 。后续可申请官方key并放云端网络保险库；这不是模型API，也不意味着需要购买服务。当前不申请账号、不在聊天收密钥。
3. DBLP只使用官方API/允许的数据导出和订阅，不解挑战、不伪装浏览器、不轮换IP规避限制。暂时标为不可用，保留其他来源工作。
4. Clash官方区分系统代理与TUN：https://www.clashverge.dev/guide/term.html 。系统代理关闭不代表TUN没有接管请求。

检索到相同CONNECT403症状的公开问题：https://github.com/openai/codex/issues/20928 。它仅是用户问题报告，不是本次根因证明或官方修复承诺；不照搬关闭代理、禁用TLS等做法。

本地请求时间和状态在 `evidence/local-network-routes.json`；云端探针写入和测试在 `evidence/cloud-prepublish-proof.json`。后续真实新任务结果优先于本文件的准备期状态。
