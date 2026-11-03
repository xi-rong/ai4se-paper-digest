## AI4SE 论文日报 · 2026-11-03

最值得读：优先精读 CrossSWE：它用混合版本组合验证，检查各仓库修改是否确实缺一不可。

## CrossSWE: Benchmarking Cross-Repository Joint Development for Coding Agents

优先精读 CrossSWE：它用混合版本组合验证，检查各仓库修改是否确实缺一不可。

作者：Silin Chen, Yuling Shi, Heng Lian, Zihan Zhang, Xiaodong Gu, Haotian Lin, Zhensu Sun

收录性质：历史论文／近期补收，不属于今日新投稿

投稿：2026-11-01T03:16:52Z

版本更新：2026-11-01T03:16:52Z

公开批次：API未提供／RSS待核查

首次发现：2026-11-03T08:16:43.088849+00:00

发表状态：arXiv预印本；正式录用未核实

相关等级：P1；直接涉及多仓库联合修改与接口一致性；其缺陷修复子集与本课题高度相关。

任务分类：① 多仓库协同修改

任务设置：多目标仓库一起修改，联合测试通过才算成功。参与仓库已给定；不能用它直接验证从生态中发现目标仓库的能力。

作者方法：枚举各仓库原始/修复版本组合：部分修复应失败，全部修复应通过，以验证联合必要性。

作者实验依据：正文报告171个实例，附录A.2将22个标为Bug fixing；§5.4的44.2%指GPT失败轨迹中的跨仓库不一致，不能解释为所有任务或所有模型的比例。

对本课题的建议：建议先核对22个bugfix任务，再与WideSWE比较测试协议、泄漏控制和任务重叠；借鉴混合版本验证来建立跨仓库契约测试。以上为研究建议。

精读／复现建议：精读§3.1–3.2、§5.2、§5.4、Limitations和附录A.2。先复现两仓库实例；不同基准分数不直接比较。

核查范围：已核查正文

[原文](https://arxiv.org/abs/2611.01484) · [数据/评测发布页（独立代码仓库待核查）](https://huggingface.co/datasets/CrossSWE/CrossSWE-Bench) · [依据](https://arxiv.org/html/2611.01484v1)

## 检索覆盖与限制

arxiv-api: ok
arxiv-api: ok
arxiv-rss:cs.SE: ok
arxiv-rss:cs.AI: ok
arxiv-rss:cs.CL: ok
arxiv-rss:cs.LG: ok

## 审读进度

状态中共 973 条论文记录，已有当前版本审核 4 条。其余未审核记录不代表不相关。周来源和待配置会议/期刊见来源台账，本次报告不代表全量筛选完成。