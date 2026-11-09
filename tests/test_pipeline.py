import copy
import io
import json
import os
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from paper_digest import cli
from paper_digest.collectors import Arxiv, parse_atom, parse_rss, upsert, iso, review_queue
from paper_digest.http import RequestError
from paper_digest.mailer import send
from paper_digest.reports import render, selected
from paper_digest.review import add_reviews, add_translations
from paper_digest.storage import empty, LocalStore, Conflict


def fixture():
    state = empty()
    p = {"id": "arxiv:2609.33382", "arxiv_id": "2609.33382", "version": 1,
         "title": "A <script> benchmark", "abstract": "software repair agent", "authors": ["A"],
         "submitted_at": iso(), "updated_at": iso(), "url": "https://arxiv.org/abs/2609.33382",
         "sources": ["arxiv-api"]}
    upsert(state, [p])
    r = {"paper_id": p["id"], "version": 1, "priority": "P1", "task_type": "multi_repo_coordinated",
         "summary_zh": "测试", "relevance_reason": "test", "task_setting": "2 targets", "method": "test",
         "evidence": "test", "research_use": "test", "reading_advice": "test", "basis": "abstract",
         "evidence_urls": [p["url"]], "publication_status": "preprint", "links": []}
    add_reviews(state, [r])
    return state, p, r


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "state.json"
        self.store = LocalStore(self.path)
        self.cfg = json.loads(Path("config.json").read_text())
        self.cfg["mail"].update(provider="resend", api_url="https://api.resend.com/emails", recipient="reader@example.org", sender="sender@example.org")

    def persist(self, state):
        self.store.save(state, None)

    def test_new_store_reads_previous_process_state(self):
        state, _, _ = fixture()
        self.persist(state)
        other = LocalStore(self.path)
        self.assertEqual(other.load()[0]["papers"], state["papers"])

    def test_stale_writer_rejected(self):
        a, rev = self.store.load()
        b = copy.deepcopy(a)
        self.store.save(a, rev)
        with self.assertRaises(Conflict):
            self.store.save(b, rev)

    def test_dry_run_byte_identical_state(self):
        state, _, _ = fixture()
        self.persist(state)
        before = self.path.read_bytes()
        with redirect_stdout(io.StringIO()):
            cli.main(["--state", str(self.path), "preview", "--out", str(self.path.parent / "preview")])
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse(self.store.load()[0]["outbox"])

    def test_ingest_same_batch_not_new(self):
        state, paper, _ = fixture()
        discovered = state["papers"][paper["id"]]["first_discovered_at"]
        self.assertEqual(upsert(state, [paper]), 0)
        self.assertEqual(state["papers"][paper["id"]]["first_discovered_at"], discovered)
        self.assertEqual(len(state["papers"]), 1)

    def test_review_queue_prioritizes_cross_repository_repair_without_classifying(self):
        items = [
            {"id": "ordinary", "title": "Software bug repair", "abstract": "", "processing_status": "unreviewed"},
            {"id": "cross", "title": "Cross-repository software bug repair", "abstract": "", "processing_status": "unreviewed"},
            {"id": "reviewed", "title": "Cross-repository software bug repair", "abstract": "", "processing_status": "reviewed"},
        ]
        self.assertEqual([p["id"] for p in review_queue(items)], ["cross", "ordinary"])
        self.assertNotIn("task_type", items[1])

    def test_invalid_review_batch_does_not_partially_mutate_state(self):
        state, _, review = fixture()
        original = copy.deepcopy(state)
        valid = dict(review, summary_zh="新的审读")
        invalid = dict(review, task_setting=" ")
        with self.assertRaises(ValueError):
            add_reviews(state, [valid, invalid])
        self.assertEqual(state, original)

    def test_bilingual_report_and_safe_translation_workflow(self):
        state, paper, review = fixture()
        self.persist(state)
        with self.assertRaisesRegex(ValueError, "translation or original abstract missing"):
            cli.main(["--state", str(self.path), "preview", "--enqueue", "--out", str(self.path.parent / "preview")])
        state, rev = self.store.load()
        translation = {"paper_id": paper["id"], "version": 1, "title_zh": "中文标题", "abstract_zh": "中文摘要全文"}
        add_translations(state, [translation])
        add_reviews(state, [review])  # re-review does not erase translations
        self.store.save(state, rev)
        state, _ = self.store.load()
        for kind in ("daily", "weekly"):
            doc = render(state, kind, coverage=[])
            for content in (doc["html"], doc["markdown"]):
                self.assertIn("中文标题", content)
                self.assertIn("中文摘要全文", content)
                self.assertIn("software repair agent", content)
                self.assertNotIn("相关理由", content)
                self.assertNotIn("精读与复现建议", content)
        with redirect_stdout(io.StringIO()):
            cli.main(["--state", str(self.path), "preview", "--enqueue", "--out", str(self.path.parent / "preview")])
        self.assertEqual(len(self.store.load()[0]["outbox"]), 1)

    def test_translation_batch_is_atomic_and_version_checked(self):
        state, paper, _ = fixture()
        before = copy.deepcopy(state)
        good = {"paper_id": paper["id"], "version": 1, "title_zh": "标题", "abstract_zh": "摘要"}
        bad = dict(good, version=2)
        with self.assertRaises(ValueError):
            add_translations(state, [good, bad])
        self.assertEqual(state, before)

    def test_collect_defers_while_other_cloud_job_holds_arxiv_lease(self):
        state = empty()
        state["cursors"]["arxiv"] = "2026-11-01T00:00:00+00:00"
        state["arxiv_collection_lease"] = {"owner": "other", "until": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
        self.persist(state)
        with patch.object(Arxiv, "collect") as collect, redirect_stdout(io.StringIO()):
            result = cli.main(["--state", str(self.path), "collect", "--out", str(self.path.parent / "candidates.json")])
        self.assertEqual(result, 2)
        collect.assert_not_called()
        saved, _ = self.store.load()
        self.assertEqual(saved["cursors"]["arxiv"], "2026-11-01T00:00:00+00:00")
        self.assertEqual(saved["arxiv_collection_lease"]["owner"], "other")
        self.assertEqual(saved["runs"][-1]["coverage"][0]["status"], "deferred")

    def test_collect_defers_after_recent_arxiv_rate_limit(self):
        state = empty()
        state["runs"] = [{"type": "collect", "at": iso(), "coverage": [{"source": "arxiv-api", "status": "failed", "http_status": 429}]}]
        self.persist(state)
        with patch.object(Arxiv, "collect") as collect, redirect_stdout(io.StringIO()):
            result = cli.main(["--state", str(self.path), "collect", "--out", str(self.path.parent / "candidates.json")])
        self.assertEqual(result, 2)
        collect.assert_not_called()
        self.assertEqual(self.store.load()[0]["runs"][-1]["coverage"][0]["error"], "rate-limit cooldown")

    def test_arxiv_failure_records_safe_http_status(self):
        collector = Arxiv(self.cfg)
        with patch.object(collector, "fetch", side_effect=RequestError(429)):
            _, coverage = collector.collect(datetime.now(timezone.utc), datetime.now(timezone.utc))
        self.assertTrue(all(c["status"] == "failed" and c["http_status"] == 429 for c in coverage))

    def test_new_version_requires_new_review(self):
        state, paper, _ = fixture()
        paper["version"] = 2
        upsert(state, [paper])
        self.assertIsNone(render(state, "daily"))

    def test_doi_merges_formal_record(self):
        state, paper, _ = fixture()
        paper["doi"] = "10.1000/test"
        upsert(state, [paper])
        upsert(state, [{"id": "doi:10.1000/test", "doi": "10.1000/test", "sources": ["dblp"]}])
        self.assertEqual(len(state["papers"]), 1)

    def test_html_escapes_paper_content(self):
        state, _, _ = fixture()
        doc = render(state, "daily")
        self.assertNotIn("<script>", doc["html"])
        self.assertIn("&lt;script&gt;", doc["html"])

    def test_report_omits_normal_coverage_and_review_progress(self):
        state, _, _ = fixture()
        doc = render(state, "daily", coverage=[{"source": "arxiv", "status": "ok"}])
        for output in (doc["html"], doc["markdown"]):
            self.assertNotIn("审读进度", output)
            self.assertNotIn("arxiv: ok", output)
            self.assertNotIn("来源异常与限制", output)
            self.assertIn("最值得读", output)

    def test_report_shows_only_sources_with_coverage_issues(self):
        state, _, _ = fixture()
        doc = render(state, "daily", coverage=[
            {"source": "arxiv", "status": "ok"},
            {"source": "dblp", "status": "partial"},
            {"source": "s2", "status": "failed"},
        ])
        for output in (doc["html"], doc["markdown"]):
            self.assertIn("来源异常与限制", output)
            self.assertIn("dblp: partial", output)
            self.assertIn("s2: failed", output)
            self.assertNotIn("arxiv: ok", output)

    def test_report_does_not_hide_missing_coverage(self):
        state, _, _ = fixture()
        self.assertIn("未取得来源覆盖记录", render(state, "daily", coverage=[])["html"])

    def test_partial_source_retains_rows(self):
        arxiv = Arxiv(self.cfg)
        with patch.object(arxiv, "fetch", side_effect=[b"<broken>", b"<broken>"]):
            rows, coverage = arxiv.collect(datetime.now(timezone.utc), datetime.now(timezone.utc))
        self.assertEqual(rows, [])
        self.assertTrue(all(c["status"] == "failed" for c in coverage))

    def test_failed_source_keeps_cursor(self):
        with patch("paper_digest.collectors.Arxiv.fetch", side_effect=RequestError(503)), redirect_stdout(io.StringIO()):
            code = cli.main(["--state", str(self.path), "collect", "--out", str(self.path.parent / "c.json")])
        state, _ = self.store.load()
        self.assertEqual(code, 2)
        self.assertNotIn("arxiv", state["cursors"])
        self.assertEqual(state["runs"][-1]["status"], "partial")

    def test_pagination_uses_total_and_offset(self):
        arxiv = Arxiv(self.cfg)
        self.cfg["arxiv"]["queries"] = ["cat:cs.SE"]
        with patch.object(arxiv, "fetch", return_value=b"data") as fetch, patch("paper_digest.collectors.parse_atom", side_effect=[([{"id": "1"}], 2), ([{"id": "2"}], 2)]):
            rows, coverage = arxiv.collect(datetime.now(timezone.utc), datetime.now(timezone.utc))
        self.assertEqual(len(rows), 2)
        self.assertEqual(fetch.call_args_list[1].args[0]["start"], 1)
        self.assertEqual(coverage[0]["status"], "ok")

    def queued(self):
        state, _, _ = fixture()
        message = render(state, "daily")
        state["outbox"][message["id"]] = message
        self.persist(state)
        return message["id"]

    def test_send_failure_preserves_pending_content(self):
        mid = self.queued()
        before = self.store.load()[0]["outbox"][mid]["html"]
        with patch.dict(os.environ, {"DIGEST_MAIL_TOKEN": "test-placeholder"}), patch("paper_digest.mailer.request", side_effect=RequestError(503, True)):
            self.assertEqual(send(self.store, self.cfg, mid, recipient="reader@example.org"), "retry")
        state, _ = self.store.load()
        self.assertEqual(state["outbox"][mid]["html"], before)
        self.assertNotEqual(state["papers"]["arxiv:2609.33382"]["send_status"], "sent")

    def test_brevo_delivery_and_replay(self):
        mid = self.queued()
        self.cfg['mail'].update(provider='brevo', api_url='https://api.brevo.com/v3/smtp/email')
        with patch.dict(os.environ, {'DIGEST_MAIL_TOKEN': 'placeholder'}), patch('paper_digest.mailer.request', return_value=(b'{"messageId":"accepted"}', {})) as req:
            self.assertEqual(send(self.store, self.cfg, mid, recipient='reader@example.org'), 'sent')
            self.assertEqual(send(self.store, self.cfg, mid, recipient='reader@example.org'), 'already_sent')
            payload = json.loads(req.call_args.kwargs['body'])
            self.assertEqual(payload['to'], [{'email': 'reader@example.org'}])
            self.assertEqual(uuid.UUID(payload['headers']['idempotencyKey']).version, 4)
            self.assertEqual(req.call_count, 1)

    def test_brevo_uncertain_failure_expires_before_provider_window(self):
        mid = self.queued()
        self.cfg['mail'].update(provider='brevo', api_url='https://api.brevo.com/v3/smtp/email')
        with patch.dict(os.environ, {'DIGEST_MAIL_TOKEN': 'placeholder'}), patch('paper_digest.mailer.request', side_effect=RequestError(503, True)):
            self.assertEqual(send(self.store, self.cfg, mid, recipient='reader@example.org'), 'retry')
            state, rev = self.store.load()
            state['outbox'][mid]['first_attempt_at'] = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
            self.store.save(state, rev)
            with self.assertRaises(ValueError):
                send(self.store, self.cfg, mid, recipient='reader@example.org')
        self.assertEqual(self.store.load()[0]['outbox'][mid]['status'], 'retry')

    def test_sent_replay_does_not_call_provider_or_reselect(self):
        mid = self.queued()
        with patch.dict(os.environ, {"DIGEST_MAIL_TOKEN": "test-placeholder"}), patch("paper_digest.mailer.request", return_value=(b'{"id":"provider-1"}', {})) as request:
            self.assertEqual(send(self.store, self.cfg, mid, recipient="reader@example.org"), "sent")
            self.assertEqual(send(self.store, self.cfg, mid, recipient="reader@example.org"), "already_sent")
            self.assertEqual(request.call_count, 1)
        self.assertIsNone(render(self.store.load()[0], "daily"))

    def test_recipient_cannot_be_overridden(self):
        mid = self.queued()
        with self.assertRaises(ValueError):
            send(self.store, self.cfg, mid, recipient="someone-else@example.org")

    def test_inflight_lease_blocks_second_sender(self):
        mid = self.queued()
        state, rev = self.store.load()
        state["outbox"][mid].update(status="sending", lease_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
        self.store.save(state, rev)
        with patch.dict(os.environ, {"DIGEST_MAIL_TOKEN": "test-placeholder"}), self.assertRaises(ValueError):
            send(self.store, self.cfg, mid, recipient="reader@example.org")

    def test_expired_idempotency_requires_reconciliation(self):
        mid = self.queued()
        state, rev = self.store.load()
        state["outbox"][mid]["first_attempt_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        self.store.save(state, rev)
        with patch.dict(os.environ, {"DIGEST_MAIL_TOKEN": "test-placeholder"}), self.assertRaises(ValueError):
            send(self.store, self.cfg, mid, recipient="reader@example.org")

    def test_empty_digest_no_message(self):
        self.assertIsNone(render(empty(), "daily"))

    def test_seed_enrichment_does_not_hide_partial_collection(self):
        state, _, _ = fixture()
        state['runs'] = [
            {'type': 'collect', 'coverage': [{'source': 's2-citations', 'status': 'failed'}]},
            {'type': 'seed', 'coverage': [{'source': 'arxiv-id-lookup', 'status': 'ok'}]}]
        self.assertIn('s2-citations: failed', render(state, 'daily')['markdown'])

    def test_rss_empty_channel_valid_but_error_page_rejected(self):
        self.assertEqual(parse_rss(b'<rss><channel><pubDate>today</pubDate></channel></rss>', 'cs.SE'), [])
        with self.assertRaises(ValueError):
            parse_rss(b'<html><body>temporarily blocked</body></html>', 'cs.SE')

    def test_cross_listing_preserves_primary_and_secondary_categories(self):
        data = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:x="http://arxiv.org/schemas/atom"><entry>
        <id>https://arxiv.org/abs/2609.33382v1</id><title>test</title><summary>test</summary>
        <category term="cs.AI"/><category term="cs.SE"/><x:primary_category term="cs.AI"/>
        </entry></feed>'''
        rows, _ = parse_atom(data)
        self.assertEqual(rows[0]['primary_category'], 'cs.AI')
        self.assertIn('cs.SE', rows[0]['categories'])


if __name__ == "__main__":
    unittest.main()
