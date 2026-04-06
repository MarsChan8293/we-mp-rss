import smtplib
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from core.config import cfg
from core.lax import TemplateParser


def build_email_debug_result(success, summary, url, message_type, headers, payload, response=None, error=None):
    return {
        "success": success,
        "summary": summary,
        "request": {
            "url": url,
            "message_type": message_type,
            "headers": headers,
            "cookies": None,
            "payload": payload,
        },
        "response": response or {"status_code": None, "body": None, "raw_text": None},
        "error": error,
    }


def parse_email_recipients(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def render_email_subject(task, feed, articles) -> str:
    template = task.email_subject_template or task.name or "{{ feed.mp_name }} 更新通知"
    parser = TemplateParser(template)
    return parser.render(
        {
            "feed": feed,
            "articles": articles,
            "task": task,
            "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    ).strip()


def render_email_body(task, feed, articles) -> str:
    parser = TemplateParser(task.message_template or "")
    return parser.render(
        {
            "feed": feed,
            "articles": articles,
            "task": task,
            "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


def _load_smtp_config():
    smtp_config = {
        "host": cfg.get("smtp.host", ""),
        "port": cfg.get("smtp.port", 465),
        "username": cfg.get("smtp.username", ""),
        "password": cfg.get("smtp.password", ""),
        "from_email": cfg.get("smtp.from_email", ""),
        "from_name": cfg.get("smtp.from_name", ""),
        "use_tls": cfg.get("smtp.use_tls", False),
        "use_ssl": cfg.get("smtp.use_ssl", True),
        "timeout": cfg.get("smtp.timeout", 30),
    }
    missing = [key for key in ("host", "from_email") if not smtp_config[key]]
    if missing:
        raise ValueError(f"SMTP 配置缺失: {', '.join(missing)}")
    if smtp_config["use_tls"] and smtp_config["use_ssl"]:
        raise ValueError("SMTP 配置错误: use_tls 与 use_ssl 不能同时启用")
    return smtp_config


def send_email_message(hook, is_test: bool = False):
    payload = ""
    headers = {}
    smtp_url = ""
    try:
        smtp_config = _load_smtp_config()
        smtp_url = f"smtp://{smtp_config['host']}:{smtp_config['port']}"

        recipients = parse_email_recipients(getattr(hook.task, "email_to", ""))
        cc_recipients = parse_email_recipients(getattr(hook.task, "email_cc", ""))
        if not recipients:
            raise ValueError("email_to 不能为空")

        all_recipients = recipients + cc_recipients
        subject = render_email_subject(hook.task, hook.feed, hook.articles)
        payload = render_email_body(hook.task, hook.feed, hook.articles)

        content_type = (getattr(hook.task, "email_content_type", "text") or "text").strip().lower()
        if content_type not in ("text", "html"):
            raise ValueError("email_content_type 仅支持 text 或 html")

        mime_subtype = "html" if content_type == "html" else "plain"
        message = MIMEText(payload, mime_subtype, "utf-8")
        from_header = formataddr((str(Header(smtp_config["from_name"], "utf-8")), smtp_config["from_email"]))
        message["From"] = from_header
        message["To"] = ", ".join(recipients)
        if cc_recipients:
            message["Cc"] = ", ".join(cc_recipients)
        message["Subject"] = str(Header(subject, "utf-8"))

        headers = {
            "From": from_header,
            "To": ", ".join(recipients),
            "Cc": ", ".join(cc_recipients),
            "Subject": subject,
            "Content-Type": f"text/{mime_subtype}; charset=utf-8",
        }

        smtp_class = smtplib.SMTP_SSL if smtp_config["use_ssl"] else smtplib.SMTP
        with smtp_class(smtp_config["host"], int(smtp_config["port"]), timeout=int(smtp_config["timeout"])) as smtp:
            if smtp_config["use_tls"]:
                smtp.starttls()
            if smtp_config["username"] or smtp_config["password"]:
                smtp.login(smtp_config["username"], smtp_config["password"])
            send_result = smtp.sendmail(smtp_config["from_email"], all_recipients, message.as_string())
            if send_result:
                refused_recipients = ", ".join(send_result.keys())
                raise ValueError(f"SMTP 部分收件人发送失败: {refused_recipients}")

        debug_result = build_email_debug_result(
            True,
            "邮箱发送成功",
            smtp_url,
            getattr(hook.task, "message_type", 2),
            headers,
            payload,
            {
                "status_code": 250,
                "body": {"accepted": all_recipients},
                "raw_text": "SMTP sendmail accepted by server",
            },
            None,
        )
    except Exception as exc:
        debug_result = build_email_debug_result(
            False,
            "邮箱发送失败",
            smtp_url,
            getattr(hook.task, "message_type", 2),
            headers,
            payload,
            None,
            str(exc),
        )
        if not is_test:
            raise ValueError(str(exc))

    if is_test:
        return debug_result
    return debug_result["summary"]
