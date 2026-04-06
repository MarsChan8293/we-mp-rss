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

    def test_build_test_task_prefers_unsaved_email_fields(self):
        persisted = SimpleNamespace(
            id="task-3",
            name="saved-email-task",
            message_type=2,
            message_template="saved-body",
            web_hook_url="",
            headers="",
            cookies="",
            mps_id='[{"id":"feed-1"}]',
            email_to="saved@example.com",
            email_cc="saved-cc@example.com",
            email_subject_template="saved-subject",
            email_content_type="text",
            status=1,
            cron_exp="*/5 * * * *",
        )
        request_data = {
            "email_to": "draft@example.com,other@example.com",
            "email_cc": "draft-cc@example.com",
            "email_subject_template": "{{ feed.mp_name }} 更新通知",
            "email_content_type": "html",
        }

        test_task = build_test_task_from_request(persisted, request_data)

        self.assertEqual(test_task.email_to, "draft@example.com,other@example.com")
        self.assertEqual(test_task.email_cc, "draft-cc@example.com")
        self.assertEqual(test_task.email_subject_template, "{{ feed.mp_name }} 更新通知")
        self.assertEqual(test_task.email_content_type, "html")

    def test_build_test_task_preserves_blank_email_fields(self):
        persisted = SimpleNamespace(
            id="task-4",
            name="saved-email-task",
            message_type=2,
            message_template="saved-body",
            web_hook_url="",
            headers="",
            cookies="",
            mps_id='[{"id":"feed-1"}]',
            email_to="saved@example.com",
            email_cc="saved-cc@example.com",
            email_subject_template="saved-subject",
            email_content_type="html",
            status=1,
            cron_exp="*/5 * * * *",
        )
        request_data = {
            "email_to": "",
            "email_cc": "",
            "email_subject_template": "",
            "email_content_type": "",
        }

        test_task = build_test_task_from_request(persisted, request_data)

        self.assertEqual(test_task.email_to, "")
        self.assertEqual(test_task.email_cc, "")
        self.assertEqual(test_task.email_subject_template, "")
        self.assertEqual(test_task.email_content_type, "")


class TestMessageTaskEndpoint(unittest.TestCase):
    @patch("apis.message_task.DB.get_session")
    def test_test_message_task_rejects_unsupported_message_type(self, get_session_mock):
        session = get_session_mock.return_value
        session.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="task-2",
            name="saved-name",
            message_type=3,
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
        self.assertEqual(result["message"], "当前仅支持 WebHook 或 Email 类型测试")

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

    @patch("jobs.webhook.web_hook")
    @patch("jobs.webhook.MessageWebHook", side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    @patch("jobs.mps.get_feeds")
    @patch("apis.message_task.DB.get_session")
    def test_test_message_task_allows_email_message_type(
        self,
        get_session_mock,
        get_feeds_mock,
        _message_webhook_mock,
        web_hook_mock,
    ):
        session = get_session_mock.return_value
        session.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="task-email-1",
            name="saved-email-task",
            message_type=2,
            message_template="邮件正文",
            web_hook_url="",
            headers="",
            cookies="",
            mps_id='[{"id":"feed-1"}]',
            email_to="saved@example.com",
            email_cc="",
            email_subject_template="saved-subject",
            email_content_type="text",
            status=1,
            cron_exp="*/5 * * * *",
        )
        get_feeds_mock.return_value = [SimpleNamespace(id="feed-1", mp_name="Email Feed")]
        web_hook_mock.return_value = {"success": True, "summary": "邮箱发送成功"}

        result = run(
            message_task.test_message_task(
                "task-email-1",
                request_data=None,
                current_user={},
            )
        )

        self.assertEqual(result["data"]["message_type"], 2)
        self.assertEqual(result["data"]["feed_name"], "Email Feed")
        self.assertEqual(result["data"]["result"]["summary"], "邮箱发送成功")

    @patch("jobs.webhook.web_hook")
    @patch("jobs.webhook.MessageWebHook", side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    @patch("jobs.mps.get_feeds")
    @patch("apis.message_task.DB.get_session")
    def test_test_message_task_uses_unsaved_email_form_values(
        self,
        get_session_mock,
        get_feeds_mock,
        _message_webhook_mock,
        web_hook_mock,
    ):
        session = get_session_mock.return_value
        session.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="task-email-2",
            name="saved-email-task",
            message_type=2,
            message_template="saved-body",
            web_hook_url="",
            headers="",
            cookies="",
            mps_id='[{"id":"feed-1"}]',
            email_to="saved@example.com",
            email_cc="saved-cc@example.com",
            email_subject_template="saved-subject",
            email_content_type="text",
            status=1,
            cron_exp="*/5 * * * *",
        )
        captured = {}

        def capture_task(task):
            captured["task"] = task
            return [SimpleNamespace(id="feed-2", mp_name="Draft Feed")]

        get_feeds_mock.side_effect = capture_task
        web_hook_mock.return_value = {"success": True}

        run(
            message_task.test_message_task(
                "task-email-2",
                request_data=message_task.MessageTaskTestRequest(
                    name="draft-email-task",
                    message_type=2,
                    message_template="draft-body",
                    email_to="draft@example.com,other@example.com",
                    email_cc="draft-cc@example.com",
                    email_subject_template="{{ feed.mp_name }} 更新通知",
                    email_content_type="html",
                    mps_id='[{"id":"feed-2"}]',
                ),
                current_user={},
            )
        )

        self.assertEqual(captured["task"].name, "draft-email-task")
        self.assertEqual(captured["task"].email_to, "draft@example.com,other@example.com")
        self.assertEqual(captured["task"].email_cc, "draft-cc@example.com")
        self.assertEqual(captured["task"].email_subject_template, "{{ feed.mp_name }} 更新通知")
        self.assertEqual(captured["task"].email_content_type, "html")


class TestMessageTaskValidation(unittest.TestCase):
    @patch("apis.message_task.DB.get_session")
    def test_create_message_task_rejects_email_without_recipient(self, get_session_mock):
        session = get_session_mock.return_value

        result = run(
            message_task.create_message_task(
                message_task.MessageTaskCreate(
                    name="email-task",
                    message_type=2,
                    message_template="body",
                    web_hook_url="",
                    email_to="",
                    email_content_type="text",
                    mps_id='[]',
                ),
                current_user={},
            )
        )

        self.assertEqual(result["code"], 400)
        self.assertEqual(result["message"], "Email 类型必须填写 email_to")
        session.add.assert_not_called()

    @patch("apis.message_task.DB.get_session")
    def test_update_message_task_rejects_webhook_without_url(self, get_session_mock):
        session = get_session_mock.return_value
        session.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="task-webhook-1",
            name="webhook-task",
            message_type=1,
            message_template="{}",
            web_hook_url="https://saved.example.com",
            headers="",
            cookies="",
            mps_id='[]',
            status=1,
            cron_exp="*/5 * * * *",
        )

        result = run(
            message_task.update_message_task(
                "task-webhook-1",
                message_task.MessageTaskCreate(
                    name="webhook-task",
                    message_type=1,
                    message_template="{}",
                    web_hook_url="",
                    mps_id='[]',
                ),
                current_user={},
            )
        )

        self.assertEqual(result["code"], 400)
        self.assertEqual(result["message"], "WebHook 类型必须填写 web_hook_url")
        session.commit.assert_not_called()
