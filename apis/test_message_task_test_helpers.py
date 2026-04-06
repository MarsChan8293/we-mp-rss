import unittest
from asyncio import run
from types import SimpleNamespace
from unittest.mock import patch

from apis import message_task
from apis.message_task_test_helpers import build_test_task_from_request


class TestMessageTaskTestHelpers(unittest.TestCase):
    def test_build_test_task_prefers_unsaved_form_values(self):
        persisted = SimpleNamespace(
            id="task-1",
            name="saved-name",
            message_type=1,
            message_template='{"saved":true}',
            web_hook_url="https://saved.example.com",
            headers="",
            cookies="",
            mps_id='[{"id":"feed-1"}]',
            status=1,
            cron_exp="*/5 * * * *",
        )
        request_data = {
            "name": "draft-name",
            "message_type": 1,
            "message_template": '{"draft":true}',
            "web_hook_url": "https://draft.example.com",
            "headers": '{"Authorization":"Bearer 1"}',
            "cookies": "sid=abc",
            "mps_id": '[{"id":"feed-2"}]',
        }

        test_task = build_test_task_from_request(persisted, request_data)

        self.assertEqual(test_task.id, "task-1")
        self.assertEqual(test_task.name, "draft-name")
        self.assertEqual(test_task.web_hook_url, "https://draft.example.com")
        self.assertEqual(test_task.mps_id, '[{"id":"feed-2"}]')
        self.assertEqual(test_task.cron_exp, "*/5 * * * *")

    def test_build_test_task_preserves_explicit_blank_values(self):
        persisted = SimpleNamespace(
            id="task-1",
            name="saved-name",
            message_type=1,
            message_template='{"saved":true}',
            web_hook_url="https://saved.example.com",
            headers='{"Authorization":"saved"}',
            cookies="saved-cookie=1",
            mps_id='[{"id":"feed-1"}]',
            status=1,
            cron_exp="*/5 * * * *",
        )
        request_data = {
            "name": "",
            "message_template": "",
            "web_hook_url": "",
            "headers": "",
            "cookies": "",
            "mps_id": "",
        }

        test_task = build_test_task_from_request(persisted, request_data)

        self.assertEqual(test_task.name, "")
        self.assertEqual(test_task.message_template, "")
        self.assertEqual(test_task.web_hook_url, "")
        self.assertEqual(test_task.headers, "")
        self.assertEqual(test_task.cookies, "")
        self.assertEqual(test_task.mps_id, "")


class TestMessageTaskEndpoint(unittest.TestCase):
    @patch("apis.message_task.DB.get_session")
    def test_test_message_task_rejects_non_webhook_message_type(self, get_session_mock):
        session = get_session_mock.return_value
        session.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="task-2",
            name="saved-name",
            message_type=2,
            message_template="{}",
            web_hook_url="https://saved.example.com",
            headers="",
            cookies="",
            mps_id='[{"id":"feed-1"}]',
            status=1,
            cron_exp="*/5 * * * *",
        )

        result = run(
            message_task.test_message_task(
                "task-2",
                request_data=None,
                current_user={},
            )
        )

        self.assertEqual(result["code"], 400)
        self.assertEqual(result["message"], "当前仅支持 WebHook 类型测试")

    @patch("jobs.webhook.web_hook")
    @patch("jobs.webhook.MessageWebHook", side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    @patch("jobs.mps.get_feeds")
    @patch("apis.message_task.DB.get_session")
    def test_test_message_task_uses_unsaved_form_values_when_present(
        self,
        get_session_mock,
        get_feeds_mock,
        _message_webhook_mock,
        web_hook_mock,
    ):
        session = get_session_mock.return_value
        session.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="task-1",
            name="saved-name",
            message_type=1,
            message_template='{"saved":true}',
            web_hook_url="https://saved.example.com",
            headers="",
            cookies="",
            mps_id='[{"id":"feed-1"}]',
            status=1,
            cron_exp="*/5 * * * *",
        )
        captured = {}

        def capture_task(task):
            captured["task"] = task
            return [SimpleNamespace(id="feed-2", mp_name="Draft Feed")]

        get_feeds_mock.side_effect = capture_task
        web_hook_mock.return_value = {"success": True}

        result = run(
            message_task.test_message_task(
                "task-1",
                request_data=message_task.MessageTaskTestRequest(
                    name="draft-name",
                    message_type=1,
                    message_template='{"draft":true}',
                    web_hook_url="https://draft.example.com",
                    headers='{"Authorization":"Bearer 1"}',
                    cookies="sid=abc",
                    mps_id='[{"id":"feed-2"}]',
                ),
                current_user={},
            )
        )

        self.assertEqual(captured["task"].name, "draft-name")
        self.assertEqual(captured["task"].web_hook_url, "https://draft.example.com")
        self.assertEqual(captured["task"].mps_id, '[{"id":"feed-2"}]')
        self.assertEqual(
            result["data"],
            {
                "task_id": "task-1",
                "task_name": "draft-name",
                "message_type": 1,
                "feed_name": "Draft Feed",
                "result": {"success": True},
            },
        )
