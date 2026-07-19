"""CLI: notify — test de notificaciones."""

from knowledge.engine.notify import (
    SlackNotifier,
    WebhookNotifier,
    format_compile_event,
    get_notifier,
)


def cmd_notify_test(args) -> int:
    """Envía una notificación de prueba para verificar la configuración."""
    service = get_notifier()

    webhook_url = getattr(args, "webhook", None) or ""
    slack_url = getattr(args, "slack", None) or ""

    if webhook_url:
        service.add_notifier(WebhookNotifier(webhook_url))

    if slack_url:
        service.add_notifier(SlackNotifier(slack_url))

    if not webhook_url and not slack_url and service.notifier_count == 0:
        return 0

    notification = format_compile_event(reason="test", docs_changed=5, docs_total=100, errors=0)
    n = service.send(notification)
    return 0 if n > 0 else 1
