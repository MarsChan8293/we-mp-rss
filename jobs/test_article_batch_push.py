import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jobs.article_batch_push import batch_push_articles, validate_batch_push_task


class BatchPushArticlesTests(unittest.TestCase):
    def build_task(self, **overrides):
        data = {
            "id": "task-1",
            "name": "Batch Push",
            "message_type": 1,
            "status": 1,
            "message_template": "{{ feed.mp_name }}",
            "web_hook_url": "https://example.com/webhook",
            "email_to": "",
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def build_feed(self, mp_id, mp_name):
        return SimpleNamespace(id=mp_id, mp_name=mp_name)

    def build_article(self, article_id, mp_id, title):
        return SimpleNamespace(
            id=article_id,
            mp_id=mp_id,
            title=title,
            url=f"https://example.com/{article_id}",
            description=f"{title} desc",
            publish_time="2026-04-06 05:20:00",
            pic_url="",
            content="<p>demo</p>",
        )

    def test_validate_batch_push_task_rejects_non_delivery_type(self):
        task = self.build_task(message_type=0)

        with self.assertRaises(ValueError):
            validate_batch_push_task(task)

    def test_validate_batch_push_task_rejects_missing_task(self):
        with self.assertRaises(ValueError):
            validate_batch_push_task(None)

    def test_validate_batch_push_task_rejects_disabled_task(self):
        task = self.build_task(status=0)

        with self.assertRaises(ValueError):
            validate_batch_push_task(task)

    def test_validate_batch_push_task_rejects_missing_web_hook_url(self):
        task = self.build_task(web_hook_url="")

        with self.assertRaises(ValueError):
            validate_batch_push_task(task)

    def test_validate_batch_push_task_rejects_missing_email_to(self):
        task = self.build_task(message_type=2, web_hook_url="", email_to="")

        with self.assertRaises(ValueError):
            validate_batch_push_task(task)

    def test_batch_push_articles_rejects_empty_article_selection(self):
        task = self.build_task()

        with self.assertRaises(ValueError):
            batch_push_articles(task, {}, [])

    @patch("jobs.article_batch_push.web_hook")
    def test_batch_push_articles_groups_articles_by_mp_id(self, web_hook_mock):
        task = self.build_task()
        feeds_by_id = {
            "mp-a": self.build_feed("mp-a", "公众号A"),
            "mp-b": self.build_feed("mp-b", "公众号B"),
        }
        articles = [
            self.build_article("a-1", "mp-a", "A1"),
            self.build_article("a-2", "mp-a", "A2"),
            self.build_article("b-1", "mp-b", "B1"),
        ]

        result = batch_push_articles(task, feeds_by_id, articles)

        self.assertEqual(result["total_groups"], 2)
        self.assertEqual(web_hook_mock.call_count, 2)
        self.assertEqual(result["success_count"], 2)
        self.assertEqual(result["failure_count"], 0)

    @patch("jobs.article_batch_push.web_hook")
    def test_batch_push_articles_keeps_other_groups_when_one_group_fails(self, web_hook_mock):
        task = self.build_task()
        feeds_by_id = {
            "mp-a": self.build_feed("mp-a", "公众号A"),
            "mp-b": self.build_feed("mp-b", "公众号B"),
        }
        articles = [
            self.build_article("a-1", "mp-a", "A1"),
            self.build_article("b-1", "mp-b", "B1"),
        ]
        web_hook_mock.side_effect = [ValueError("boom"), "ok"]

        result = batch_push_articles(task, feeds_by_id, articles)

        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failure_count"], 1)
        self.assertEqual(result["results"][0]["success"], False)
        self.assertEqual(result["results"][1]["success"], True)

    @patch("jobs.article_batch_push.web_hook")
    def test_batch_push_articles_records_missing_feed_and_continues(self, web_hook_mock):
        task = self.build_task()
        feeds_by_id = {
            "mp-a": self.build_feed("mp-a", "公众号A"),
        }
        articles = [
            self.build_article("a-1", "mp-a", "A1"),
            self.build_article("b-1", "mp-b", "B1"),
        ]

        result = batch_push_articles(task, feeds_by_id, articles)

        self.assertEqual(web_hook_mock.call_count, 1)
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failure_count"], 1)
        self.assertEqual(result["results"][1]["mp_id"], "mp-b")
        self.assertFalse(result["results"][1]["success"])
        self.assertEqual(result["results"][1]["error"], "公众号不存在: mp-b")

    @patch("jobs.article_batch_push.web_hook")
    def test_batch_push_articles_passes_grouped_articles_to_web_hook(self, web_hook_mock):
        task = self.build_task()
        feeds_by_id = {
            "mp-a": self.build_feed("mp-a", "公众号A"),
        }
        articles = [
            self.build_article("a-1", "mp-a", "A1"),
            self.build_article("a-2", "mp-a", "A2"),
        ]

        batch_push_articles(task, feeds_by_id, articles)

        self.assertEqual(web_hook_mock.call_count, 1)
        hook = web_hook_mock.call_args.args[0]
        self.assertEqual(hook.task, task)
        self.assertEqual(hook.feed, feeds_by_id["mp-a"])
        self.assertEqual([article.id for article in hook.articles], ["a-1", "a-2"])
