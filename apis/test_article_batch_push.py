import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis.article import ArticleBatchPushRequest, batch_push_selected_articles, router
from core.auth import get_current_user_or_ak


def build_session(task=None, articles=None, feeds=None):
    session = MagicMock()
    query = session.query.return_value
    query.filter.return_value.first.return_value = task
    query.filter.return_value.all.side_effect = [articles or [], feeds or []]
    return session


def build_test_client():
    app = FastAPI()
    app.include_router(router, prefix="/wx")
    app.dependency_overrides[get_current_user_or_ak] = lambda: {"id": "u-1"}
    return TestClient(app)


class BatchPushArticleHttpApiTests(unittest.TestCase):
    def setUp(self):
        self.client = build_test_client()
        self.addCleanup(self.client.close)

    def test_post_batch_push_rejects_invalid_request_body(self):
        response = self.client.post(
            "/wx/articles/batch_push",
            json={"task_id": "task-1"},
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertTrue(any(item["loc"][-1] == "article_ids" for item in detail))

    @patch("apis.article.batch_push_articles")
    @patch("apis.article.DB.get_session")
    def test_post_batch_push_returns_success_response_shape(self, get_session_mock, batch_push_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        articles = [SimpleNamespace(id="a-1", mp_id="mp-a")]
        feeds = [SimpleNamespace(id="mp-a", mp_name="公众号A")]
        get_session_mock.return_value = build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.return_value = {
            "summary": "批量推送完成，成功 1 个公众号，失败 0 个公众号",
            "success_count": 1,
            "failure_count": 0,
            "results": [{"mp_id": "mp-a", "success": True}],
        }

        response = self.client.post(
            "/wx/articles/batch_push",
            json={"task_id": "task-1", "article_ids": ["a-1"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "code": 0,
                "message": "批量推送完成，成功 1 个公众号，失败 0 个公众号",
                "data": {
                    "summary": "批量推送完成，成功 1 个公众号，失败 0 个公众号",
                    "success_count": 1,
                    "failure_count": 0,
                    "results": [{"mp_id": "mp-a", "success": True}],
                },
            },
        )
        batch_push_mock.assert_called_once()

    @patch("apis.article.DB.get_session")
    def test_post_batch_push_returns_error_response_when_task_missing(self, get_session_mock):
        get_session_mock.return_value = build_session(task=None)

        response = self.client.post(
            "/wx/articles/batch_push",
            json={"task_id": "task-1", "article_ids": ["a-1"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "消息任务不存在", "data": None},
        )

    @patch("apis.article.batch_push_articles")
    @patch("apis.article.DB.get_session")
    def test_post_batch_push_returns_error_response_when_service_raises_value_error(self, get_session_mock, batch_push_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        articles = [SimpleNamespace(id="a-1", mp_id="mp-a")]
        feeds = [SimpleNamespace(id="mp-a", mp_name="公众号A")]
        get_session_mock.return_value = build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.side_effect = ValueError("只能选择启用中的消息任务")

        response = self.client.post(
            "/wx/articles/batch_push",
            json={"task_id": "task-1", "article_ids": ["a-1"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"code": 400, "message": "只能选择启用中的消息任务", "data": None},
        )

    @patch("apis.article.batch_push_articles")
    @patch("apis.article.DB.get_session")
    def test_post_batch_push_returns_error_response_when_service_raises_unexpected_error(self, get_session_mock, batch_push_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        articles = [SimpleNamespace(id="a-1", mp_id="mp-a")]
        feeds = [SimpleNamespace(id="mp-a", mp_name="公众号A")]
        get_session_mock.return_value = build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.side_effect = RuntimeError("推送服务异常")

        response = self.client.post(
            "/wx/articles/batch_push",
            json={"task_id": "task-1", "article_ids": ["a-1"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"code": 500, "message": "推送服务异常", "data": None},
        )


class BatchPushArticleApiTests(unittest.IsolatedAsyncioTestCase):
    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_rejects_empty_article_ids(self, get_session_mock):
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=[])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 400)
        self.assertIn("至少选择一篇文章", result["message"])

    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_rejects_missing_task(self, get_session_mock):
        get_session_mock.return_value = build_session(task=None)
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["a-1"])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 404)
        self.assertIn("消息任务不存在", result["message"])

    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_rejects_missing_articles(self, get_session_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        get_session_mock.return_value = build_session(task=task, articles=[], feeds=[])
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
        get_session_mock.return_value = build_session(task=task, articles=articles, feeds=feeds)
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
        get_session_mock.return_value = build_session(task=task, articles=articles, feeds=feeds)
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
        get_session_mock.return_value = build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.side_effect = ValueError("只能选择启用中的消息任务")
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["a-1"])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 400)
        self.assertEqual(result["message"], "只能选择启用中的消息任务")

    @patch("apis.article.batch_push_articles")
    @patch("apis.article.DB.get_session")
    async def test_batch_push_selected_articles_maps_unexpected_error_to_server_error(self, get_session_mock, batch_push_mock):
        task = SimpleNamespace(id="task-1", name="Webhook Push", message_type=1, status=1)
        articles = [SimpleNamespace(id="a-1", mp_id="mp-a")]
        feeds = [SimpleNamespace(id="mp-a", mp_name="公众号A")]
        get_session_mock.return_value = build_session(task=task, articles=articles, feeds=feeds)
        batch_push_mock.side_effect = RuntimeError("推送服务异常")
        request = ArticleBatchPushRequest(task_id="task-1", article_ids=["a-1"])

        result = await batch_push_selected_articles(request, current_user={"id": "u-1"})

        self.assertEqual(result["code"], 500)
        self.assertEqual(result["message"], "推送服务异常")
