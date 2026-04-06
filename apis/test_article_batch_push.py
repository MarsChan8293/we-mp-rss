import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apis.article import ArticleBatchPushRequest, batch_push_selected_articles


class BatchPushArticleApiTests(unittest.IsolatedAsyncioTestCase):
    def build_session(self, task=None, articles=None, feeds=None):
        session = MagicMock()
        query = session.query.return_value
        query.filter.return_value.first.return_value = task
        query.filter.return_value.all.side_effect = [articles or [], feeds or []]
        return session

    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_rejects_empty_article_ids(self, get_session_mock):
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=[])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 400)
        self.assertIn("至少选择一篇文章", result["message"])

    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_rejects_missing_task(self, get_session_mock):
        get_session_mock.return_value = self.build_session(task=None)
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["a-1"])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 404)
        self.assertIn("消息任务不存在", result["message"])

    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_rejects_missing_articles(self, get_session_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        get_session_mock.return_value = self.build_session(task=task, articles=[], feeds=[])
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["a-1"])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 400)
        self.assertIn("部分文章不存在: a-1", result["message"])

    @patch("apis.article.batch_push_articles")
    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_returns_service_result(self, get_session_mock, batch_push_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        articles = [SimpleNamespace(id="a-1", mp_id="mp-a")]
        feeds = [SimpleNamespace(id="mp-a", mp_name="公众号A")]
        get_session_mock.return_value = self.build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.return_value = {
            "summary": "批量推送完成，成功 1 个公众号，失败 0 个公众号",
            "success_count": 1,
            "failure_count": 0,
            "results": [],
        }
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["a-1"])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["data"]["success_count"], 1)
        self.assertIn("批量推送完成", result["message"])
        passed_task, passed_feeds_by_id, passed_articles = batch_push_mock.call_args[0]
        self.assertIs(passed_task, task)
        self.assertEqual(passed_feeds_by_id, {"mp-a": feeds[0]})
        self.assertEqual(passed_articles, articles)

    @patch("apis.article.batch_push_articles")
    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_trims_and_dedupes_article_ids(self, get_session_mock, batch_push_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        articles = [SimpleNamespace(id="a-1", mp_id="mp-a")]
        feeds = [SimpleNamespace(id="mp-a", mp_name="公众号A")]
        get_session_mock.return_value = self.build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.return_value = {
            "summary": "批量推送完成，成功 1 个公众号，失败 0 个公众号",
            "success_count": 1,
            "failure_count": 0,
            "results": [],
        }
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["  a-1  ", "a-1", " "])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 0)
        self.assertEqual(batch_push_mock.call_args[0][2], articles)

    @patch("apis.article.batch_push_articles")
    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_maps_value_error_to_bad_request(self, get_session_mock, batch_push_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        articles = [SimpleNamespace(id="a-1", mp_id="mp-a")]
        feeds = [SimpleNamespace(id="mp-a", mp_name="公众号A")]
        get_session_mock.return_value = self.build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.side_effect = ValueError("只能选择启用中的消息任务")
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["a-1"])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 400)
        self.assertEqual(result["message"], "只能选择启用中的消息任务")
