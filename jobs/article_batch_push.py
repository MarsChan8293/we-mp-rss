from collections import OrderedDict
from types import SimpleNamespace

SUPPORTED_BATCH_PUSH_MESSAGE_TYPES = (1, 2)


def _has_non_whitespace_text(value):
    return bool(value and str(value).strip())


def validate_batch_push_task(task):
    if task is None:
        raise ValueError("消息任务不存在")
    if getattr(task, "status", 0) != 1:
        raise ValueError("只能选择启用中的消息任务")
    if getattr(task, "message_type", None) not in SUPPORTED_BATCH_PUSH_MESSAGE_TYPES:
        raise ValueError("批量推送仅支持 WebHook 或 Email 类型任务")
    if task.message_type == 1 and not _has_non_whitespace_text(getattr(task, "web_hook_url", "")):
        raise ValueError("WebHook 任务的 web_hook_url 不能为空")
    if task.message_type == 2 and not _has_non_whitespace_text(getattr(task, "email_to", "")):
        raise ValueError("Email 任务的 email_to 不能为空")
    return task


def group_articles_by_mp_id(articles):
    grouped = OrderedDict()
    for article in articles:
        grouped.setdefault(article.mp_id, []).append(article)
    return grouped


def _get_webhook_api():
    from jobs.webhook import MessageWebHook, web_hook

    return SimpleNamespace(MessageWebHook=MessageWebHook, web_hook=web_hook)


def batch_push_articles(task, feeds_by_id, articles):
    """Batch push grouped articles through the task's webhook sender."""
    validate_batch_push_task(task)
    if not articles:
        raise ValueError("请至少选择一篇文章")

    webhook_api = _get_webhook_api()
    grouped_articles = group_articles_by_mp_id(articles)
    results = []
    success_count = 0
    failure_count = 0

    for mp_id, group in grouped_articles.items():
        feed = feeds_by_id.get(mp_id)
        if feed is None:
            results.append(
                {
                    "mp_id": mp_id,
                    "mp_name": None,
                    "article_count": len(group),
                    "article_ids": [article.id for article in group],
                    "success": False,
                    "summary": f"公众号不存在: {mp_id}",
                    "error": f"公众号不存在: {mp_id}",
                }
            )
            failure_count += 1
            continue

        try:
            webhook_api.web_hook(
                webhook_api.MessageWebHook(task=task, feed=feed, articles=group)
            )
            results.append(
                {
                    "mp_id": mp_id,
                    "mp_name": feed.mp_name,
                    "article_count": len(group),
                    "article_ids": [article.id for article in group],
                    "success": True,
                    "summary": f"{feed.mp_name} 推送成功",
                    "error": None,
                }
            )
            success_count += 1
        except Exception as exc:
            results.append(
                {
                    "mp_id": mp_id,
                    "mp_name": feed.mp_name,
                    "article_count": len(group),
                    "article_ids": [article.id for article in group],
                    "success": False,
                    "summary": f"{feed.mp_name} 推送失败",
                    "error": str(exc),
                }
            )
            failure_count += 1

    return {
        "task_id": task.id,
        "task_name": task.name,
        "message_type": task.message_type,
        "total_articles": len(articles),
        "total_groups": len(grouped_articles),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
        "summary": f"批量推送完成，成功 {success_count} 个公众号，失败 {failure_count} 个公众号",
    }
