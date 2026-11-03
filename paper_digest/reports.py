import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .review import review_for
from .collectors import iso

TASK_LABEL = {"multi_repo_coordinated": "① 多仓库协同修改", "external_repo_context": "② 外部仓库辅助单目标修复",
              "single_repo_cross_file": "③ 单仓库跨文件", "multi_repo_dataset_single_target": "④ 多仓库数据集、单目标任务",
              "single_repo_other": "单仓库任务", "unknown": "任务范围待核查"}


def event_key(paper):
    return paper["id"] + ":v" + str(paper.get("version"))


def selected(state, kind, max_papers=10, now=None):
    now = now or datetime.now(timezone.utc)
    sent = {key for message in state["outbox"].values() if message["kind"] != "weekly"
            and message["status"] == "sent" for key in message["event_keys"]}
    items = []
    for paper in state["papers"].values():
        review = review_for(state, paper)
        if not review or review["priority"] == "exclude":
            continue
        if kind == "weekly":
            if datetime.fromisoformat(paper["first_discovered_at"]) < now - timedelta(days=7):
                continue
        elif event_key(paper) in sent:
            continue
        if kind == "daily" and review.get("seed_only"):
            continue
        if kind == "daily" and paper.get("version", 1) > 1 and not review.get("important_update", False):
            continue
        if kind == "history" and paper.get("submitted_at") and not review.get("seed_only"):
            if datetime.fromisoformat(paper["submitted_at"].replace("Z", "+00:00")) < now - timedelta(days=30):
                continue
        items.append((paper, review))
    return sorted(items, key=lambda pr: (pr[1]["priority"], pr[0]["first_discovered_at"], pr[0]["id"]))[:max_papers]


def render(state, kind, coverage=None, max_papers=10, now=None):
    now = now or datetime.now(timezone.utc)
    items = selected(state, kind, max_papers, now)
    if not items:
        return None
    date = now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    title = {"daily": "AI4SE 论文日报", "weekly": "AI4SE 本周阅读回顾", "history": "AI4SE 初始阅读清单 · 历史回顾"}[kind]
    title += " · " + date
    top = items[0][1]["summary_zh"]
    blocks = [(title, "最值得读：" + top)]
    for paper, review in items:
        if review.get("seed_only"):
            freshness = "研究种子／超出近30天窗口，不属于新增"
        elif paper.get("version", 1) > 1:
            freshness = "重要版本更新（不等于新投稿）"
        elif paper.get("submitted_at") and datetime.fromisoformat(paper["submitted_at"].replace("Z", "+00:00")) < now - timedelta(days=2):
            freshness = "历史论文／近期补收，不属于今日新投稿"
        else:
            freshness = "近期投稿；公开批次另列"
        body = [review["summary_zh"], "作者：" + ", ".join(paper.get("authors", [])),
                "收录性质：" + freshness,
                "投稿：" + str(paper.get("submitted_at") or "待核查"),
                "版本更新：" + str(paper.get("updated_at") or "待核查"),
                "公开批次：" + str(paper.get("public_batch_at") or "API未提供／RSS待核查"),
                "首次发现：" + paper["first_discovered_at"],
                "发表状态：" + review["publication_status"],
                "相关等级：" + review["priority"] + "；" + review["relevance_reason"],
                "任务分类：" + TASK_LABEL[review["task_type"]],
                "任务设置：" + review["task_setting"], "作者方法：" + review["method"],
                "作者实验依据：" + review["evidence"], "对本课题的建议：" + review["research_use"],
                "精读／复现建议：" + review["reading_advice"],
                "核查范围：" + ("已核查正文" if review["basis"] == "fulltext" else "仅摘要")]
        links = [("原文", paper["url"])] + [(l["kind"], l["url"]) for l in review["links"]]
        links += [("依据", url) for url in review["evidence_urls"] if url != paper["url"]]
        blocks.append((paper["title"], "\n\n".join(body), links))
    if kind == "weekly":
        types = sorted({TASK_LABEL[r["task_type"]] for _, r in items})
        blocks.append(("本周样本与行动", f"仅总结本周收集且已审读选入本报告的 {len(items)} 篇：" + "、".join(types)
                       + "。这些样本不足以推断整个领域的确定趋势。\n\n复现实验与精读行动见各篇建议；新增基准须核对任务目标仓库数量与所有目标联合成功指标。"))
    if coverage is None:
        runs = state["runs"]
        run = next((r for r in reversed(runs) if r.get("type") == "collect"), runs[-1] if runs else {})
        coverage = run.get("coverage", [])
    blocks.append(("检索覆盖与限制", "\n".join(f"{c['source']}: {c['status']}" for c in coverage)
                   or "本报告为种子预览，未执行全量检索。"))
    reviewed = sum(1 for p in state["papers"].values() if review_for(state, p))
    blocks.append(("审读进度", f"状态中共 {len(state['papers'])} 条论文记录，已有当前版本审核 {reviewed} 条。其余未审核记录不代表不相关。周来源和待配置会议/期刊见来源台账，本次报告不代表全量筛选完成。"))
    md = "\n\n".join("## " + b[0] + "\n\n" + b[1] + ("\n\n" + " · ".join(f"[{label}]({url})" for label, url in b[2]) if len(b) > 2 else "") for b in blocks)
    parts = []
    for b in blocks:
        parts.append('<h2 style="font-size:20px;line-height:1.4">' + html.escape(b[0]) + '</h2>')
        parts.append('<p style="line-height:1.8;white-space:pre-line">' + html.escape(b[1]) + '</p>')
        if len(b) > 2:
            parts.append('<p>' + ' · '.join('<a href="' + html.escape(url, quote=True) + '">' + html.escape(label) + '</a>' for label, url in b[2]) + '</p>')
    rendered = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                '<body style="margin:0;background:#f4f6f8;color:#17212b;font-family:-apple-system,BlinkMacSystemFont,Arial,sans-serif">'
                '<main style="max-width:680px;margin:auto;padding:20px;background:white">' + ''.join(parts) + '</main></body></html>')
    keys = [event_key(p) for p, _ in items]
    digest_id = hashlib.sha256(json.dumps([kind, keys], sort_keys=True).encode()).hexdigest()[:32]
    return {"id": digest_id, "kind": kind, "subject": title, "markdown": md, "html": rendered,
            "event_keys": keys, "created_at": iso(), "status": "pending"}
