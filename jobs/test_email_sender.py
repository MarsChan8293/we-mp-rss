import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jobs.email_sender import parse_email_recipients, send_email_message


def smtp_get_side_effect(overrides=None):
    values = {
        "smtp.host": "smtp.example.com",
        "smtp.port": 465,
        "smtp.username": "sender@example.com",
        "smtp.password": "secret",
        "smtp.from_email": "sender@example.com",
        "smtp.from_name": "WeRSS",
        "smtp.use_tls": False,
        "smtp.use_ssl": True,
        "smtp.timeout": 30,
    }
    if overrides:
        values.update(overrides)

    def _get(key, default=None):
        return values.get(key, default)

    return _get


def build_hook(**task_overrides):
    task_data = {
        "id": "task-email-1",
        "name": "邮件通知任务",
        "message_type": 2,
        "message_template": "文章：{{ feed.mp_name }}",
        "email_to": "to1@example.com,to2@example.com",
        "email_cc": "cc@example.com",
        "email_subject_template": "{{ feed.mp_name }} 更新通知",
        "email_content_type": "text",
    }
    task_data.update(task_overrides)
    task = SimpleNamespace(**task_data)
    feed = SimpleNamespace(id="feed-1", mp_name="测试公众号")
    articles = [
        {
            "id": "article-1",
            "title": "测试文章",
            "url": "https://example.com/article-1",
            "publish_time": "2026-04-06 10:00:00",
            "description": "测试描述",
            "content": "<p>测试正文</p>",
        }
    ]
    return SimpleNamespace(task=task, feed=feed, articles=articles)


class TestEmailSender(unittest.TestCase):
    def test_parse_email_recipients_ignores_empty_values(self):
        self.assertEqual(
            parse_email_recipients(" one@example.com, ,two@example.com ,, "),
            ["one@example.com", "two@example.com"],
        )

    @patch("jobs.email_sender.smtplib.SMTP_SSL")
    @patch("jobs.email_sender.cfg.get")
    def test_send_email_message_sends_text_email(self, get_mock, smtp_ssl_mock):
        get_mock.side_effect = smtp_get_side_effect()
        smtp_client = MagicMock()
        smtp_client.sendmail.return_value = {}
        smtp_ssl_mock.return_value.__enter__.return_value = smtp_client

        result = send_email_message(build_hook(), is_test=True)

        smtp_client.login.assert_called_once_with("sender@example.com", "secret")
        smtp_client.sendmail.assert_called_once()
        sendmail_args = smtp_client.sendmail.call_args[0]
        self.assertEqual(sendmail_args[0], "sender@example.com")
        self.assertEqual(
            sendmail_args[1],
            ["to1@example.com", "to2@example.com", "cc@example.com"],
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["response"]["status_code"], 250)
        self.assertEqual(result["request"]["url"], "smtp://smtp.example.com:465")
        self.assertEqual(
            result["request"]["headers"]["Content-Type"],
            "text/plain; charset=utf-8",
        )
        self.assertEqual(result["request"]["headers"]["Subject"], "测试公众号 更新通知")
        self.assertEqual(result["request"]["payload"], "文章：测试公众号")

    @patch("jobs.email_sender.smtplib.SMTP")
    @patch("jobs.email_sender.cfg.get")
    def test_send_email_message_sends_html_email(self, get_mock, smtp_mock):
        get_mock.side_effect = smtp_get_side_effect(
            {
                "smtp.port": 587,
                "smtp.use_tls": True,
                "smtp.use_ssl": False,
            }
        )
        smtp_client = MagicMock()
        smtp_client.sendmail.return_value = {}
        smtp_mock.return_value.__enter__.return_value = smtp_client

        result = send_email_message(
            build_hook(
                message_template="<h1>{{ feed.mp_name }}</h1>",
                email_content_type="html",
            ),
            is_test=True,
        )

        smtp_client.starttls.assert_called_once()
        sendmail_args = smtp_client.sendmail.call_args[0]
        self.assertIn("Content-Type: text/html", sendmail_args[2])
        self.assertEqual(
            result["request"]["headers"]["Content-Type"],
            "text/html; charset=utf-8",
        )
        self.assertEqual(result["request"]["url"], "smtp://smtp.example.com:587")

    @patch("jobs.email_sender.cfg.get")
    def test_send_email_message_fails_without_smtp_config(self, get_mock):
        get_mock.side_effect = smtp_get_side_effect({"smtp.host": ""})

        result = send_email_message(build_hook(), is_test=True)

        self.assertFalse(result["success"])
        self.assertIsNone(result["response"]["status_code"])
        self.assertEqual(result["error"], "SMTP 配置缺失: host")

    @patch("jobs.email_sender.cfg.get")
    def test_send_email_message_fails_without_recipients(self, get_mock):
        get_mock.side_effect = smtp_get_side_effect()

        result = send_email_message(
            build_hook(email_to="", email_cc=""),
            is_test=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "email_to 不能为空")

    @patch("jobs.email_sender.cfg.get")
    def test_send_email_message_falls_back_to_task_name_for_subject(self, get_mock):
        get_mock.side_effect = smtp_get_side_effect()
        with patch("jobs.email_sender.smtplib.SMTP_SSL") as smtp_ssl_mock:
            smtp_client = MagicMock()
            smtp_client.sendmail.return_value = {}
            smtp_ssl_mock.return_value.__enter__.return_value = smtp_client

            result = send_email_message(
                build_hook(name="任务默认主题", email_subject_template=""),
                is_test=True,
            )

        self.assertEqual(result["request"]["headers"]["Subject"], "任务默认主题")

    @patch("jobs.email_sender.smtplib.SMTP_SSL")
    @patch("jobs.email_sender.cfg.get")
    def test_send_email_message_reports_partial_recipient_failure(self, get_mock, smtp_ssl_mock):
        get_mock.side_effect = smtp_get_side_effect()
        smtp_client = MagicMock()
        smtp_client.sendmail.return_value = {"cc@example.com": (550, b"rejected")}
        smtp_ssl_mock.return_value.__enter__.return_value = smtp_client

        result = send_email_message(build_hook(), is_test=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "SMTP 部分收件人发送失败: cc@example.com")
