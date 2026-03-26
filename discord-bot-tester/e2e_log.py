import os
import time
import json
from pathlib import Path

# 环境变量配置
LOG_FILE = os.environ.get("BOT_LOG_FILE", "bot_events.log")
TIMEOUT = int(os.environ.get("E2E_LOG_POLL_TIMEOUT", "30"))  # 秒
POLL_INTERVAL = float(os.environ.get("E2E_LOG_POLL_INTERVAL", "1.0"))

def iter_log_json_lines(path):
    """按行读取日志文件（只返回可解析为 JSON 的行）"""
    if not Path(path).exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                yield obj
            except Exception:
                # 忽略非 JSON 行
                continue

def find_test_trigger(path, tc_id, correlation_id):
    """在日志中查找匹配 tc_id & correlation_id 的 test_trigger 事件"""
    for entry in iter_log_json_lines(path):
        if entry.get("event") != "test_trigger":
            continue
        payload = entry.get("payload", {})
        if payload.get("tc_id") == tc_id and payload.get("correlation_id") == correlation_id:
            return entry
    return None

def test_wait_for_test_trigger():
    """
    使用方法：
    1. 启动 bot（它会写入 LOG_FILE）
    2. 在 Discord 里发送： TEST_E2E:TC-FM-02|run-20260326-001
    3. 在运行此测试前设置环境变量：
       - BOT_LOG_FILE=/path/to/bot_events.log
       - E2E_CORR_ID=run-20260326-001
       - optionally E2E_LOG_POLL_TIMEOUT
    """
    tc = os.environ.get("E2E_TC_ID", "TC-FM-02")
    corr = os.environ.get("E2E_CORR_ID", "run-manual-123")
    deadline = time.time() + TIMEOUT
    found = None
    while time.time() < deadline:
        found = find_test_trigger(LOG_FILE, tc, corr)
        if found:
            break
        time.sleep(POLL_INTERVAL)
    assert found is not None, f"Did not find test_trigger for tc={tc} corr={corr} in log {LOG_FILE}"
    # 进一步断言 payload 字段存在
    payload = found.get("payload", {})
    assert payload.get("content", "").startswith("TEST_E2E:"), "unexpected content in payload"
    # 若需要断言附件存在，可检查 payload['attachments']