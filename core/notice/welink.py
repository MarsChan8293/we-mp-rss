import json
import time
import uuid

import requests

def _get_welink_business_error(parsed_body):
    if not isinstance(parsed_body, dict):
        return None

    code = parsed_body.get("code")
    if code is not None and str(code) not in {"0", "200"}:
        return parsed_body.get("message") or parsed_body.get("errMsg") or f"WeLink 业务状态异常: code={code}"

    status = parsed_body.get("status")
    if status is not None and str(status) not in {"1", "200", "true", "True"}:
        return parsed_body.get("errMsg") or parsed_body.get("message") or f"WeLink 业务状态异常: status={status}"

    return None

def send_welink_message(webhook_url, title, text, return_debug: bool = False):
    timestamp = int(time.time() * 1000)
    msg_uuid = str(uuid.uuid4()).replace("-", "")
    content = f"{title}\n{text}" if title else text
    payload = {
        "messageType": "text",
        "content": {"text": content},
        "timeStamp": timestamp,
        "uuid": msg_uuid,
        "isAt": False,
        "isAtAll": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept-Charset": "UTF-8",
    }
    raw_payload = json.dumps(payload, ensure_ascii=False)
    response = None
    try:
        response = requests.post(url=webhook_url, headers=headers, data=raw_payload)
        try:
            parsed_body = response.json()
        except ValueError:
            parsed_body = None
        response.raise_for_status()
        business_error = _get_welink_business_error(parsed_body)
        if business_error is not None:
            raise ValueError(business_error)
        debug_result = {
            "status_code": response.status_code,
            "body": parsed_body,
            "raw_text": response.text,
            "headers": headers,
            "payload": raw_payload,
            "error": None,
        }
    except Exception as exc:
        parsed_body = None
        if response is not None:
            try:
                parsed_body = response.json()
            except ValueError:
                parsed_body = None
        debug_result = {
            "status_code": getattr(response, "status_code", None),
            "body": parsed_body,
            "raw_text": getattr(response, "text", None),
            "headers": headers,
            "payload": raw_payload,
            "error": str(exc),
        }
    if return_debug:
        return debug_result
    if debug_result["error"] is not None:
        print(f"WeLink 通知发送失败: {debug_result['error']}")
        return None
    print(response.text)
    return "Webhook调用成功(WeLink)"
