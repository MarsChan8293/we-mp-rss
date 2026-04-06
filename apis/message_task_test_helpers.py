from types import SimpleNamespace
from typing import Any, Mapping, Optional


OVERRIDE_FIELDS = (
    "name",
    "message_type",
    "message_template",
    "web_hook_url",
    "headers",
    "cookies",
    "mps_id",
)

BASE_FIELDS = (
    "id",
    "name",
    "message_type",
    "message_template",
    "web_hook_url",
    "headers",
    "cookies",
    "mps_id",
    "status",
    "cron_exp",
)


def build_test_task_from_request(base_task: Any, request_data: Optional[Mapping[str, Any]] = None):
    task_data = {field: getattr(base_task, field, None) for field in BASE_FIELDS}

    if request_data:
        for field in OVERRIDE_FIELDS:
            if field in request_data:
                task_data[field] = request_data[field]

    return SimpleNamespace(**task_data)
