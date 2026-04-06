from core.models.message_task import MessageTask
from core.models.feed import Feed
from core.models.article import Article
from core.print import print_success
from core.notice import notice
from dataclasses import dataclass
from core.lax import TemplateParser
from datetime import datetime
from core.log import logger
from core.config import cfg
from bs4 import BeautifulSoup
from core.content_format import format_content
from core.notice.welink import send_welink_message
import re
@dataclass
class MessageWebHook:
    task: MessageTask
    feed:Feed
    articles: list[Article]
    pass

def send_message(hook: MessageWebHook) -> str:
    """
    发送格式化消息
    
    参数:
        hook: MessageWebHook对象，包含任务、订阅源和文章信息
        
    返回:
        str: 格式化后的消息内容
    """
    template = hook.task.message_template if hook.task.message_template else """
### {{feed.mp_name}} 订阅消息：
{% if articles %}
{% for article in articles %}
- [**{{ article.title }}**]({{article.url}}) ({{ article.publish_time }})\n
{% endfor %}
{% else %}
- 暂无文章\n
{% endif %}
    """
    parser = TemplateParser(template)
    data = {
        "feed": hook.feed,
        "articles": hook.articles,
        "task": hook.task,
        'now': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    message = parser.render(data)
    # 这里可以添加发送消息的具体实现
    print("发送消息:", message)
    try:
        notice(hook.task.web_hook_url, hook.task.name, message)
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise ValueError(f"发送消息失败: {e}")
    return message

def _build_debug_result(success, summary, url, message_type, headers, cookies, payload, response=None, error=None):
    return {
        "success": success,
        "summary": summary,
        "request": {
            "url": url,
            "message_type": message_type,
            "headers": headers,
            "cookies": cookies,
            "payload": payload,
        },
        "response": response or {"status_code": None, "body": None, "raw_text": None},
        "error": error,
    }


def call_webhook(hook: MessageWebHook, is_test: bool = False):
    """
    调用webhook接口发送数据

    参数:
        hook: MessageWebHook对象，包含任务、订阅源和文章信息
        is_test: 是否为测试模式，测试模式下使用模拟数据

    返回:
        str | dict | None: 非测试模式返回调用结果，测试模式返回调试信息

    异常:
        ValueError: 当webhook调用失败时抛出
    """
    template = hook.task.message_template if hook.task.message_template else """{
  "feed": {
    "id": "{{ feed.id }}",
    "name": "{{ feed.mp_name }}"
  },
  "articles": [
    {% if articles %}
     {% for article in articles %}
        {
          "id": "{{ article.id }}",
          "mp_id": "{{ article.mp_id }}",
          "title": "{{ article.title }}",
          "pic_url": "{{ article.pic_url }}",
          "url": "{{ article.url }}",
          "description": "{{ article.description }}",
          "publish_time": "{{ article.publish_time }}"
        }{% if not loop.last %},{% endif %}
      {% endfor %}
    {% endif %}
  ],
  "task": {
    "id": "{{ task.id }}",
    "name": "{{ task.name }}"
  },
  "now": "{{ now }}"
}
"""

    # 检查template是否需要content
    template_needs_content = "content" in template.lower()

    # 根据content_format处理内容
    content_format = cfg.get("webhook.content_format", "html")
    logger.info(f'Content将以{content_format}格式发送')

    # 测试模式下使用模拟数据
    if is_test:
        from datetime import timedelta
        logger.info("使用模拟数据测试webhook")
        mock_article = {
            "id": "test-article-001",
            "mp_id": hook.feed.id if hook.feed else "test-mp-id",
            "title": "测试文章标题",
            "pic_url": "https://via.placeholder.com/300x200",
            "url": "https://example.com/test-article",
            "description": "这是一篇测试文章的描述内容，用于测试webhook功能是否正常。",
            "publish_time": (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            "content": "<p>这是测试文章的正文内容。</p>"
        }
        processed_articles = [mock_article]
    else:
        processed_articles = []
        for article in hook.articles:
            if isinstance(article, dict) and "content" in article and article["content"]:
                processed_article = article.copy()
                # 只有template需要content时才进行格式转换
                if template_needs_content:
                    processed_article["content"] = format_content(processed_article["content"], content_format)
                processed_articles.append(processed_article)
            else:
                processed_articles.append(article)

    data = {
        "feed": hook.feed,
        "articles": processed_articles,
        "task": hook.task,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

   # 预处理content字段
    import json
    def process_content(content):
        if content is None:
            return ""
        # 进行JSON转义处理引号
        json_escaped = json.dumps(content, ensure_ascii=False)
        # 去掉外层引号避免重复
        return json_escaped[1:-1]

    # 处理articles中的content字段，进行JSON转义
    if "articles" in data:
        for i, article in enumerate(data["articles"]):
            if isinstance(article, dict):
                if "content" in article:
                    data["articles"][i]["content"] = process_content(article["content"])
            elif hasattr(article, "content"):
                setattr(data["articles"][i], "content", process_content(getattr(article, "content")))

    parser = TemplateParser(template)

    payload = parser.render(data)
    logger.info(f'Webhook payload: {payload}')

    # 检查web_hook_url是否为空
    if not hook.task.web_hook_url:
        debug_result = _build_debug_result(
            False,
            "Webhook调用失败",
            "",
            hook.task.message_type,
            {"Content-Type": "application/json"},
            None,
            "",
            None,
            "web_hook_url为空",
        )
        if is_test:
            return debug_result
        logger.error("web_hook_url为空")
        return
    # 发送webhook请求
    import requests
    import json

    # 构建请求头
    headers = {"Content-Type": "application/json"}
    if hook.task.headers:
        try:
            custom_headers = json.loads(hook.task.headers)
            headers.update(custom_headers)
        except json.JSONDecodeError as e:
            logger.warning(f"解析headers失败: {e}")

    # 构建cookies
    cookies = None
    if hook.task.cookies:
        cookies = {}
        # 解析cookie字符串 (格式: key1=value1; key2=value2)
        for cookie_pair in hook.task.cookies.split(';'):
            cookie_pair = cookie_pair.strip()
            if '=' in cookie_pair:
                key, value = cookie_pair.split('=', 1)
                cookies[key.strip()] = value.strip()

    if is_test and 'open.welink.huaweicloud.com' in hook.task.web_hook_url:
        welink_debug = send_welink_message(
            hook.task.web_hook_url,
            hook.task.name,
            payload,
            return_debug=True,
        )
        return _build_debug_result(
            welink_debug["error"] is None,
            "Webhook调用成功(WeLink)" if welink_debug["error"] is None else "Webhook调用失败(WeLink)",
            hook.task.web_hook_url,
            hook.task.message_type,
            welink_debug["headers"],
            None,
            welink_debug["payload"],
            {
                "status_code": welink_debug["status_code"],
                "body": welink_debug["body"],
                "raw_text": welink_debug["raw_text"],
            },
            welink_debug["error"],
        )

    if 'open.welink.huaweicloud.com' in hook.task.web_hook_url:
        try:
            welink_result = send_welink_message(
                hook.task.web_hook_url,
                hook.task.name,
                payload,
            )
        except Exception as exc:
            raise ValueError(f"Webhook调用失败(WeLink): {exc}")
        if not welink_result:
            raise ValueError("Webhook调用失败(WeLink): WeLink消息发送失败")
        return welink_result

    response = None
    try:
        response = requests.post(
            hook.task.web_hook_url,
            data=payload,
            headers=headers,
            cookies=cookies,
        )
        try:
            parsed_body = response.json()
        except ValueError:
            parsed_body = None
        response.raise_for_status()
        debug_result = _build_debug_result(
            True,
            "Webhook调用成功",
            hook.task.web_hook_url,
            hook.task.message_type,
            headers,
            cookies,
            payload,
            {
                "status_code": response.status_code,
                "body": parsed_body,
                "raw_text": response.text,
            },
            None,
        )
    except Exception as exc:
        parsed_body = None
        if response is not None:
            try:
                parsed_body = response.json()
            except ValueError:
                parsed_body = None
        debug_result = _build_debug_result(
            False,
            "Webhook调用失败",
            hook.task.web_hook_url,
            hook.task.message_type,
            headers,
            cookies,
            payload,
            {
                "status_code": getattr(response, "status_code", None),
                "body": parsed_body,
                "raw_text": getattr(response, "text", None),
            },
            str(exc),
        )
        if is_test:
            return debug_result
        raise ValueError(f"Webhook调用失败: {debug_result['error']}")
    if is_test:
        return debug_result
    return debug_result["summary"]

def web_hook(hook:MessageWebHook, is_test:bool = False):
    """
    根据消息类型路由到对应的处理函数

    参数:
        hook: MessageWebHook对象，包含任务、订阅源和文章信息
        is_test: 是否为测试模式，测试模式下使用模拟数据
    返回:
        对应处理函数的返回结果

    异常:
        ValueError: 当消息类型未知时抛出
    """
    try:
        # 处理articles参数，兼容Article对象和字典类型
        processed_articles = []
        if len(hook.articles)<=0:
            # raise ValueError("没有更新到文章")
            logger.warning("没有更新到文章")
            return
        for article in hook.articles:
            if isinstance(article, dict):
                # 如果是字典类型，直接使用
                def process_field_value(field_name, article):
                    value = article.get(field_name, "")
                    if field_name == "publish_time" and value:
                        # 如果已经是格式化的字符串，直接返回
                        if isinstance(value, str) and "-" in value and ":" in value:
                            return value
                        # 如果是时间戳整数，转换为字符串
                        try:
                            if isinstance(value, (int, float)):
                                return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError, OSError):
                            pass
                        return value
                    return value

                processed_article = {
                    field.name: process_field_value(field.name, article)
                    for field in Article.__table__.columns
                }
            else:
                # 如果是Article对象，使用getattr获取属性
                def process_field_value_obj(field_name, article):
                    value = getattr(article, field.name, "")
                    if field_name == "publish_time" and value:
                        # 如果已经是格式化的字符串，直接返回
                        if isinstance(value, str) and "-" in value and ":" in value:
                            return value
                        # 如果是时间戳整数，转换为字符串
                        try:
                            if isinstance(value, (int, float)):
                                return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError, OSError):
                            pass
                        return value
                    return value

                processed_article = {
                    field.name: process_field_value_obj(field.name, article)
                    for field in Article.__table__.columns
                }
            processed_articles.append(processed_article)

        hook.articles = processed_articles

        if hook.task.message_type == 0:  # 发送消息
            return send_message(hook)
        elif hook.task.message_type == 1:  # 调用webhook
            return call_webhook(hook, is_test)
        else:
            raise ValueError(f"未知的消息类型: {hook.task.message_type}")
    except Exception as e:
        raise ValueError(f"处理消息时出错: {str(e)}")
