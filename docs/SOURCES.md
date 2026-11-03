# 来源接入台账

“本地已验证”不代表“云端已验证”；报告只描述本次实际覆盖。每次 `collect` 将来源状态写入运行记录和报告。

| 来源 | 实现 | 准备阶段状态 |
|---|---|---|
| arXiv 官方 API | 元数据、分类、版本、DOI、分页，3.1秒间隔，退避/超时 | 已接入并验证（云端）：原始CLI近30天14页查询成功，数据已持久化；见cloud-original-cli-validation.json |
| arXiv RSS cs.SE/cs.AI/cs.CL/cs.LG | 公告批次、announce type、交叉分类观测；仅RSS ID待API补齐 | 已接入并验证（云端）：4个有效空channel，保留批次时间；不能据此声称当天无论文 |
| Semantic Scholar 新引用 | seed citations 分页 | 暂不可用：本地实测请求失败；seed探针返回HTTP429，不把它当作零引用 |
| Semantic Scholar 作者新作 | author ID/papers 分页 | 待配置作者 ID，未猜重名作者 |
| Semantic Scholar 推荐 | recommendations API，最多100候选 | 暂不可用：本地实测请求失败；不等于没有相关推荐 |
| DBLP | 官方 search API，f/h分页 | 暂不可用：本地HTTP202返回反机器人HTML，未取得JSON；不绕过验证 |
| GitHub 官方代码发布 | WideSWE releases，超过30条标截断 | 本地已接入并验证，官方API返回空release列表；这不等于没有代码提交 |
| ICSE/FSE/ASE/ISSTA | 需要具体年份、track论文列表及适配器 | 待配置，不能把会议首页当作已采集 |
| TSE/TOSEM/EMSE | 需要官方最新/early access目录接口 | 待配置，DBLP辅助不等于官方期刊接入 |
| NeurIPS/ICML/ICLR/ACL等 | 相关论文列入范围 | 待配置具体论文列表 |
| Google Scholar | 用户官方订阅补充 | 待用户配置；不抓取搜索页 |

运行状态：ok=本次指定查询/页范围完成；partial=截断或部分失败；failed=请求失败；unconfigured=缺配置。ok不能解释为整个领域全量检索。

官方依据：
- https://info.arxiv.org/help/api/user-manual.html
- https://info.arxiv.org/help/api/tou.html
- https://dblp.org/faq/13501473.html
- https://api.semanticscholar.org/api-docs/

具体会议论文列表将由云端阶段核实并填写 `venue_lists`，适配器未实现前状态始终待配置；不得用填入 URL 冒充接入。
