"""Select reviewed papers and render the same report as Markdown and email HTML."""
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from .review import review_for
from .collectors import iso

TASK_LABEL = {"multi_repo_coordinated": "① 多仓库协同修改", "external_repo_context": "② 外部仓库辅助单目标修复",
              "single_repo_cross_file": "③ 单仓库跨文件", "multi_repo_dataset_single_target": "④ 多仓库数据集、单目标任务",
              "single_repo_other": "单仓库任务", "unknown": "任务范围待核查"}


ALERT_LABELS = {"P0": "P0 必读", "P1": "P1 重点"}


def event_key(paper):
    return paper["id"] + ":v" + str(paper.get("version"))


def new_daily_paper(paper, now):
    try:
        submitted = datetime.fromisoformat(paper.get("submitted_at", "").replace("Z", "+00:00"))
        if submitted.tzinfo is None or submitted > now:
            return False
        tz = ZoneInfo("Asia/Shanghai")
        day, today = submitted.astimezone(tz).date(), now.astimezone(tz).date()
        return today - timedelta(days=2) <= day <= today
    except (ValueError, TypeError, AttributeError):
        return False


def selected(state, kind, max_papers=10, now=None, *, recap_days=12):
    now = now or datetime.now(timezone.utc)
    sent = {key for message in state["outbox"].values() if message["kind"] != "weekly"
            and message["status"] == "sent" for key in message["event_keys"]}
    sent_papers = {key.rsplit(":v", 1)[0] for key in sent}
    items = []
    for paper in state["papers"].values():
        review = review_for(state, paper)
        if not review or review["priority"] == "exclude":
            continue
        if kind == "weekly":
            discovered = datetime.fromisoformat(paper["first_discovered_at"])
            if not now - timedelta(days=recap_days) <= discovered <= now:
                continue
        elif event_key(paper) in sent:
            continue
        if kind == "daily" and review.get("seed_only"):
            continue
        if kind == "daily":
            # A newly discovered old paper or a new version is not a new submission.
            # Count today and the prior two calendar days in Beijing time; never repeat a sent paper.
            if paper["id"] in sent_papers:
                continue
            if not new_daily_paper(paper, now):
                continue
        if kind == "daily" and (paper.get("version") or 1) > 1 and not review.get("important_update", False):
            continue
        if kind == "history" and paper.get("submitted_at") and not review.get("seed_only"):
            if datetime.fromisoformat(paper["submitted_at"].replace("Z", "+00:00")) < now - timedelta(days=30):
                continue
        items.append((paper, review))
    return sorted(items, key=lambda pr: (pr[1]["priority"], pr[0]["first_discovered_at"], pr[0]["id"]))[:max_papers]


def _freshness(paper, review, now):
    if review.get("seed_only"):
        return "研究种子／超出近30天窗口，不属于新增"
    if (paper.get("version") or 1) > 1:
        return "重要版本更新（经审读确认）" if review.get("important_update") else "版本更新／重要性待核查"
    if new_daily_paper(paper, now):
        return "近期投稿；公开批次另列"
    if paper.get("submitted_at"):
        return "三天投稿窗口外／补收或回顾"
    return "首次投稿日期待核查"


def _report_paper(paper, review, now):
    """Build one presentation model shared by both output formats."""
    metadata = [
        ("作者", ", ".join(paper.get("authors", [])) or "待核查"),
        ("收录性质", _freshness(paper, review, now)),
        ("投稿", paper.get("submitted_at") or "待核查"),
        ("版本更新", paper.get("updated_at") or "待核查"),
        ("公开批次", paper.get("public_batch_at") or "API未提供／RSS待核查"),
        ("首次发现", paper["first_discovered_at"]),
        ("发表状态", review["publication_status"]),
    ]
    sections = [("中文摘要", review.get("abstract_zh") or "中文摘要待翻译"),
                ("英文摘要", paper.get("abstract") or "英文摘要暂不可用")]
    links = [("原文", paper["url"])] + [(link["kind"], link["url"]) for link in review["links"]]
    links += [("依据", url) for url in review["evidence_urls"] if url != paper["url"]]
    return {"title": paper["title"], "title_zh": review.get("title_zh") or "中文标题待翻译", "summary": review["summary_zh"], "priority": ALERT_LABELS.get(review["priority"], review["priority"]),
            "metadata": metadata, "sections": sections, "links": links}


def _arxiv_issue(row):
    status = row.get("status")
    code = row.get("http_status")
    if status == "deferred":
        return "限流冷却中，已推迟查询" if row.get("error") == "rate-limit cooldown" else "采集已推迟"
    if code == 429:
        cause = "请求受限（HTTP 429）"
    elif code:
        cause = f"请求失败（HTTP {code}）"
    elif row.get("error") == "RequestError":
        cause = "请求失败，未取得 HTTP 状态码"
    elif row.get("error") in ("ParseError", "ValueError"):
        cause = "返回数据格式或分页异常"
    else:
        cause = "未完成检索"
    if status == "partial":
        return f"{cause}，已保留 {row.get('count', 0)} 条记录"
    return cause


def _coverage_issues(state, coverage, kind, now):
    if coverage is None:
        tz = ZoneInfo("Asia/Shanghai")
        for run in reversed(state["runs"]):
            if run.get("type") != "collect":
                continue
            if kind != "history":
                at = run.get("at")
                if not at or datetime.fromisoformat(at).astimezone(tz).date() != now.astimezone(tz).date():
                    continue
                # Older runs did not store report_kind. Weekly runs also queried weekly-only sources.
                rows = run.get("coverage", [])
                legacy_weekly = any(not c.get("source", "").startswith("arxiv-") for c in rows)
                if run.get("report_kind", "weekly" if legacy_weekly else "daily") != kind:
                    continue
            coverage = run.get("coverage")
            break
    if not coverage:
        return ["未取得来源覆盖记录，不能视为全量检索。"]
    issues = []
    groups = {}
    for row in coverage:
        if row.get("status") == "ok":
            continue
        source = row.get("source", "未知来源")
        if source != "arxiv-api":
            issues.append(f"{source}: {row.get('status', 'unknown')}")
            continue
        categories = dict.fromkeys(re.findall(r"cat:([A-Za-z0-9.-]+)", row.get("query", "")))
        scope = "、".join(categories) or "API 检索"
        if len(categories) > 1:
            scope += " 补充检索"
        groups.setdefault(_arxiv_issue(row), {})[scope] = None
    for cause, scopes in groups.items():
        issues.append(f"arXiv {'，'.join(scopes)}：{cause}")
    return issues


def _markdown(title, top, papers, issues, weekly_note):
    blocks = ["# " + title, "**最值得读：** " + top]
    for paper in papers:
        body = ["## " + paper["title"], "**" + paper["title_zh"] + "**", "**" + paper["priority"] + "**"]
        body.extend("**" + str(k) + "：** " + str(v) for k, v in paper["metadata"] + paper["sections"])
        body.append(" · ".join(f"[{label}]({url})" for label, url in paper["links"]))
        blocks.append("\n\n".join(body))
    if weekly_note:
        blocks.append("## 本期样本与行动\n\n" + weekly_note)
    if issues:
        blocks.append("## 来源异常与限制\n\n" + "\n".join("- " + issue for issue in issues))
    return "\n\n".join(blocks)


def _html(title, date, top, papers, issues, weekly_note):
    e = lambda value: html.escape(str(value), quote=True)
    # Inline styles and presentation tables survive common mail clients, including mobile apps.
    cards = []
    for index, paper in enumerate(papers, 1):
        badge_color = {"P0 必读": "#a1281e", "P1 重点": "#875315"}.get(paper["priority"], "#2457a6")
        meta = "<br>".join('<span style="color:#68778b">' + e(k) + '：</span>' + e(v) for k, v in paper["metadata"])
        details = "".join('<tr><td style="padding:9px 0;border-top:1px solid #eef1f5"><div style="font-size:12px;font-weight:700;letter-spacing:.03em;color:#48617d;margin-bottom:5px">' + e(k) + '</div><div style="font-size:14px;line-height:1.75;color:#25354a">' + e(v).replace("\n", "<br>") + '</div></td></tr>' for k, v in paper["sections"])
        links = " ".join('<a href="' + e(url) + '" style="display:inline-block;margin:4px 7px 4px 0;padding:7px 12px;background:#edf4ff;border-radius:6px;color:#1d4ed8;font-size:13px;font-weight:700;text-decoration:none">' + e(label) + ' ↗</a>' for label, url in paper["links"] if urlsplit(url).scheme in ("http", "https"))
        cards.append('<tr><td style="padding:0 18px 16px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#ffffff;border:1px solid #e1e8f1;border-radius:12px"><tr><td style="padding:20px 20px 12px"><span style="font-size:12px;font-weight:700;color:' + badge_color + '">' + e(paper["priority"]) + ' · 论文 ' + str(index).zfill(2) + '</span><h2 style="margin:9px 0 12px;color:#10253e;font-size:19px;line-height:1.4">' + e(paper["title"]) + '</h2><div style="padding:12px 14px;border-left:3px solid #5a8de5;background:#f2f6fd;font-size:15px;line-height:1.7;color:#1a3558">' + e(paper["title_zh"]).replace("\n", "<br>") + '</div><p style="margin:14px 0;font-size:12px;line-height:1.85;color:#41536b">' + meta + '</p><table role="presentation" width="100%" cellspacing="0" cellpadding="0">' + details + '</table><div style="padding-top:8px">' + links + '</div></td></tr></table></td></tr>')
    extra = ''
    if weekly_note:
        extra += '<tr><td style="padding:0 18px 16px"><div style="background:#eaf3ff;padding:16px 18px;border-radius:10px;color:#173a68;font-size:14px;line-height:1.75"><strong>本期样本与行动</strong><br>' + e(weekly_note) + '</div></td></tr>'
    if issues:
        extra += '<tr><td style="padding:0 18px 16px"><div style="background:#fff6e6;border:1px solid #f4d9a2;padding:14px 16px;border-radius:10px;color:#79521b;font-size:13px;line-height:1.7"><strong>来源异常与限制</strong><br>' + '<br>'.join(e(issue) for issue in issues) + '</div></td></tr>'
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + e(title) + '</title></head>'
            '<body style="margin:0;padding:0;background:#eef2f7;color:#172b45;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2f7"><tr><td align="center" style="padding:20px 0"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;background:#f7f9fc"><tr><td style="padding:26px 24px 22px;background:#122c4b;color:white"><div style="font-size:11px;letter-spacing:.13em;color:#b8d0ed;font-weight:700">AI4SE · RESEARCH DIGEST</div><h1 style="font-size:24px;line-height:1.3;margin:10px 0 5px">' + e(title) + '</h1><div style="font-size:12px;color:#c8d8ea">' + e(date) + ' · ' + str(len(papers)) + ' 篇精选</div></td></tr><tr><td style="padding:18px"><div style="padding:17px 18px;background:#e7f0ff;border-radius:10px;color:#17375d"><div style="font-size:12px;letter-spacing:.05em;font-weight:700;color:#356ab8">本期最值得读</div><div style="margin-top:7px;font-size:15px;line-height:1.75">' + e(top).replace("\n", "<br>") + '</div></div></td></tr>' + ''.join(cards) + extra + '<tr><td style="padding:4px 24px 22px;color:#8090a3;font-size:12px;line-height:1.6">AI4SE 个人论文追踪 · 按研究相关性筛选</td></tr></table></td></tr></table></body></html>')


def render(state, kind, coverage=None, max_papers=10, now=None, *, recap_days=12):
    now = now or datetime.now(timezone.utc)
    date = now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    items = selected(state, kind, max_papers, now, recap_days=recap_days)
    if not items and kind != "daily":
        return None
    if kind == "daily" and not items:
        # Never send a second empty report after a daily report for the same date.
        if any(m.get("kind") == "daily" and m.get("status") == "sent" and
               m.get("subject", "").endswith(date) for m in state.get("outbox", {}).values()):
            return None
    title = {"daily": "AI4SE 三天论文速递", "weekly": f"AI4SE 近 {recap_days} 天阅读回顾", "history": "AI4SE 初始阅读清单 · 历史回顾"}[kind] + " · " + date
    if kind in ("daily", "weekly"):
        counts = Counter(review["priority"] for _, review in items)
        alerts = [f"{label} {counts[priority]} 篇" for priority, label in ALERT_LABELS.items() if counts[priority]]
        if alerts:
            title = "【" + " · ".join(alerts) + "】" + title
    papers = [_report_paper(paper, review, now) for paper, review in items]
    issues = _coverage_issues(state, coverage, kind, now)
    if papers:
        top = papers[0]["summary"]
    elif issues:
        top = "本次没有选出符合条件的论文；部分来源采集不完整，不能据此判断没有新论文。"
    else:
        top = "本次已审读结果中没有符合近三天且未推送条件的论文。"
    weekly_note = ""
    if kind == "weekly":
        weekly_note = f"本期列出 {len(items)} 篇近 {recap_days} 天首次发现并已审读的论文，样本不代表整个领域。"
        weekly_note += " 本期进展按下列精确版本回顾；未完成版本差异核查，不能据此声称存在重要更新。"
        weekly_note += " 任务范围与阅读依据：" + "；".join(
            paper["id"] + ":v" + str(paper.get("version")) + "（" +
            TASK_LABEL[review["task_type"]] + "，" + review["basis"] + "）"
            for paper, review in items)
        weekly_note += "。研究建议（Agent建议，非作者实验结论）：" + "；".join(
            paper["id"] + "：" + review["research_use"] for paper, review in items)
        weekly_note += "。关键词队列及未入选发现不等于已审读；来源异常见下方，不据此推断没有新成果。"
    keys = [event_key(p) for p, _ in items]
    digest_id = hashlib.sha256(json.dumps([kind, keys, date] if not keys else [kind, keys], sort_keys=True).encode()).hexdigest()[:32]
    return {"id": digest_id, "kind": kind, "subject": title,
            "markdown": _markdown(title, top, papers, issues, weekly_note),
            "html": _html(title, date, top, papers, issues, weekly_note),
            "event_keys": keys, "created_at": iso(), "status": "pending"}
