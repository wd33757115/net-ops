"""结构化日志初始化测试。"""

from src.core.logging import bind_context, configure_logging, get_logger, reset_context


def test_configure_logging_idempotent():
    configure_logging(log_level="INFO", log_format="console")
    configure_logging(log_level="INFO", log_format="console")
    logger = get_logger("test")
    logger.info("logging_test_event", ok=True)


def test_bind_and_reset_context():
    configure_logging(log_level="INFO", log_format="console", force=True)
    pairs = bind_context(request_id="req-1", run_id="run-1")
    try:
        get_logger("test").info("context_bound")
    finally:
        reset_context(pairs)
