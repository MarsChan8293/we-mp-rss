import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.notice.welink import send_welink_message
from jobs.webhook import MessageWebHook, call_webhook


class TestWebhookDebug(unittest.TestCase):
    def _build_hook(self, url: str):
        task = SimpleNamespace(
            id="task-1",
            name="welink",
            message_type=1,
            message_template='{"title":"{{ task.name }}"}',
            web_hook_url=url,
            headers="",
            cookies="",
        )
        feed = SimpleNamespace(id="feed-1", mp_name="GiantPandaLLM")
        article = {
            "id": "article-1",
            "mp_id": "feed-1",
            "title": "Test title",
            "pic_url": "https://example.com/pic.png",
            "url": "https://example.com/article",
            "description": "desc",
            "publish_time": "2026-04-05 19:00:00",
            "content": "<p>hello</p>",
        }
        return MessageWebHook(task=task, feed=feed, articles=[article])

    @patch("requests.post")
    def test_standard_webhook_test_mode_returns_debug_result(self, post_mock):
        response = Mock()
        response.status_code = 200
        response.text = '{"ok":true}'
        response.json.return_value = {"ok": True}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        result = call_webhook(self._build_hook("https://example.com/webhook"), is_test=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["request"]["url"], "https://example.com/webhook")
        self.assertIn('"title":"welink"', result["request"]["payload"])
        self.assertEqual(result["response"]["status_code"], 200)
        self.assertEqual(result["response"]["body"], {"ok": True})
        self.assertIsNone(result["error"])

    @patch("core.notice.welink.requests.post")
    def test_welink_debug_details_stay_transport_level(self, post_mock):
        response = Mock()
        response.status_code = 200
        response.text = '{"code":"0","message":"ok."}'
        response.json.return_value = {"code": "0", "message": "ok."}
        response.raise_for_status.return_value = None
        post_mock.return_value = response

        result = send_welink_message(
            "https://open.welink.huaweicloud.com/api/werobot/v1/webhook/send?token=1",
            "welink",
            '{"title":"welink"}',
            return_debug=True,
        )

        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["body"]["code"], "0")
        self.assertIn('"messageType": "text"', result["payload"])
        self.assertIn('"uuid":', result["payload"])
        self.assertNotIn("summary", result)
        self.assertNotIn("request", result)

    @patch("jobs.webhook.send_welink_message")
    def test_welink_test_mode_returns_wrapped_payload(self, send_mock):
        send_mock.return_value = {
            "status_code": 200,
            "body": {"code": "0", "message": "ok."},
            "raw_text": '{"code":"0","message":"ok."}',
            "headers": {
                "Content-Type": "application/json",
                "Accept-Charset": "UTF-8",
            },
            "payload": '{"messageType": "text", "uuid": "abc"}',
            "error": None,
        }

        result = call_webhook(
            self._build_hook("https://open.welink.huaweicloud.com/api/werobot/v1/webhook/send?token=1"),
            is_test=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["response"]["body"]["code"], "0")
        self.assertIn('"messageType": "text"', result["request"]["payload"])
        self.assertIn('"uuid":', result["request"]["payload"])
        self.assertEqual(result["summary"], "Webhook调用成功(WeLink)")

    @patch("requests.post")
    def test_standard_webhook_test_mode_returns_failure_debug_result(self, post_mock):
        response = Mock()
        response.status_code = 500
        response.text = "upstream error"
        response.json.side_effect = ValueError("not json")
        response.raise_for_status.side_effect = Exception("500 Server Error")
        post_mock.return_value = response

        result = call_webhook(self._build_hook("https://example.com/webhook"), is_test=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["response"]["status_code"], 500)
        self.assertEqual(result["response"]["raw_text"], "upstream error")
        self.assertIn("500 Server Error", result["error"])

    @patch("requests.post")
    def test_standard_webhook_non_test_failure_keeps_prefixed_error(self, post_mock):
        response = Mock()
        response.status_code = 500
        response.text = "upstream error"
        response.json.side_effect = ValueError("not json")
        response.raise_for_status.side_effect = Exception("500 Server Error")
        post_mock.return_value = response

        with self.assertRaisesRegex(ValueError, "Webhook调用失败: 500 Server Error"):
            call_webhook(self._build_hook("https://example.com/webhook"), is_test=False)

    @patch("jobs.webhook.send_welink_message")
    def test_welink_non_test_mode_uses_welink_sender_and_returns_summary(self, send_mock):
        send_mock.return_value = "Webhook调用成功(WeLink)"

        result = call_webhook(
            self._build_hook("https://open.welink.huaweicloud.com/api/werobot/v1/webhook/send?token=1"),
            is_test=False,
        )

        send_mock.assert_called_once()
        self.assertEqual(result, "Webhook调用成功(WeLink)")

    @patch("jobs.webhook.send_welink_message")
    def test_welink_non_test_mode_raises_prefixed_error_on_sender_failure(self, send_mock):
        send_mock.return_value = None

        with self.assertRaisesRegex(ValueError, r"Webhook调用失败\(WeLink\):"):
            call_webhook(
                self._build_hook("https://open.welink.huaweicloud.com/api/werobot/v1/webhook/send?token=1"),
                is_test=False,
            )

        send_mock.assert_called_once()
