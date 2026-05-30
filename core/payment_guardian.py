#!/usr/bin/env python3
"""
core/payment_guardian.py - Control de pagos con autorización por umbrales
Registra TODOS los intentos en audit log inmutable (append-only).

Umbrales:
  < 10 €   → permitir automáticamente (log)
  10-49 €  → notificación + confirmación del usuario
  50-99 €  → diálogo con justificación obligatoria
  ≥ 100 €  → bloquear + alerta Telegram + esperar autorización manual
"""

import json
import logging
import os
import uuid
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
AUDIT_FILE = ROOT / "data" / "payment_audit.jsonl"  # append-only, nunca sobreescribir

UMBRAL_NOTIFICAR = 10.0
UMBRAL_JUSTIFICAR = 50.0
UMBRAL_BLOQUEAR = 100.0
UMBRAL_ACUMULADO = 30.0
VENTANA_ACUMULADO_MINUTOS = 60

_lock = threading.Lock()


def _calcular_acumulado_automatico(ventana_minutos: int = 60) -> float:
    """Suma de pagos autorizados automáticamente en los últimos N minutos."""
    if not AUDIT_FILE.exists():
        return 0.0
    corte = datetime.now()
    total = 0.0
    try:
        for line in AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines():
            entry = json.loads(line)
            if entry.get("decision") != "autorizado_automatico":
                continue
            ts = entry.get("timestamp", "")
            try:
                ts_dt = datetime.fromisoformat(ts)
                if (corte - ts_dt).total_seconds() / 60 <= ventana_minutos:
                    total += float(entry.get("importe", 0))
            except Exception:
                continue
    except Exception:
        pass
    return total


# ── registro inmutable ────────────────────────────────────────────────────────


def _audit(importe: float, concepto: str, fuente: str, decision: str, nota: str = "") -> None:
    """Escribe una línea en el audit log. Nunca sobreescribe."""
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "importe": importe,
        "concepto": concepto,
        "fuente": fuente,
        "decision": decision,
        "nota": nota,
    }
    with _lock:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info("[payment_audit] %.2f€ %s → %s", importe, concepto, decision)


# ── notificaciones ────────────────────────────────────────────────────────────


def _send_telegram_buttons(
    importe: float, concepto: str, fuente: str, token: str, pendientes_path: Path
) -> bool:
    """Envía mensaje de Telegram con botones Aprobar/Rechazar para un pago."""
    try:
        import urllib.request

        token_bot = os.environ.get("TELEGRAM_BOT_TOKEN", os.environ.get("TELEGRAM_TOKEN", ""))
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "8621907530")
        if not token_bot:
            logger.warning("Telegram no configurado")
            return False

        mensaje = (
            f"🚨 <b>PAGO PENDIENTE — {importe:.2f} €</b>\n"
            f"<b>Concepto:</b> {concepto}\n"
            f"<b>Fuente:</b> {fuente}\n"
            f"<b>Token:</b> <code>{token}</code>\n"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Aprobar", "callback_data": f"pago_ok_{token}"},
                    {"text": "❌ Rechazar", "callback_data": f"pago_no_{token}"},
                ]
            ]
        }

        url = f"https://api.telegram.org/bot{token_bot}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": chat_id,
                "text": mensaje,
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            }
        ).encode()

        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)  # nosec B310
        logger.info("Telegram enviado: pago %.2f€ token=%s", importe, token)
        return True
    except Exception as e:
        logger.warning("Error enviando Telegram: %s", e)
        return False


def _queue_pending_payment(
    importe: float, concepto: str, fuente: str, token: str, pendientes_path: Path
) -> None:
    """Guarda el pago pendiente en el archivo de cola."""
    pendientes_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "importe": importe,
        "concepto": concepto,
        "fuente": fuente,
        "token": token,
        "estado": "pendiente",
    }
    with _lock:
        with pendientes_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def consultar_pago_pendiente(token: str) -> dict | None:
    """Consulta un pago pendiente por token. Usado por el callback de Telegram."""
    pendientes_path = ROOT / "data" / "pending_payments.jsonl"
    if not pendientes_path.exists():
        return None
    for line in pendientes_path.read_text(encoding="utf-8").strip().splitlines():
        try:
            entry = json.loads(line)
            if entry.get("token") == token and entry.get("estado") == "pendiente":
                return entry
        except Exception:
            continue
    return None


def autorizar_pago_remoto(token: str, aprobado: bool, usuario: str = "telegram") -> str:
    """
    Procesa la respuesta del botón de Telegram.
    Llamado desde el callback del bot.

    Returns: "ok", "ya_procesado", o "no_encontrado"
    """
    pendientes_path = ROOT / "data" / "pending_payments.jsonl"
    if not pendientes_path.exists():
        return "no_encontrado"

    lineas = pendientes_path.read_text(encoding="utf-8").strip().splitlines()
    nuevas = []
    procesado = False
    resultado = "no_encontrado"

    for line in lineas:
        try:
            entry = json.loads(line)
        except Exception:
            nuevas.append(line)
            continue

        if entry.get("token") == token:
            if entry.get("estado") == "pendiente":
                entry["estado"] = (
                    "autorizado_via_telegram" if aprobado else "rechazado_via_telegram"
                )
                entry["autorizado_por"] = usuario
                entry["resuelto"] = datetime.now().isoformat()

                decision = "autorizado_via_telegram" if aprobado else "rechazado_via_telegram"
                _audit(
                    entry["importe"],
                    entry["concepto"],
                    entry["fuente"],
                    decision,
                    f"Autorizado por {usuario} via Telegram",
                )
                procesado = True
                resultado = "ok"
            else:
                resultado = "ya_procesado"

        nuevas.append(json.dumps(entry, ensure_ascii=False))

    if procesado:
        with _lock:
            pendientes_path.write_text("\n".join(nuevas) + "\n", encoding="utf-8")

    return resultado


def _show_qt_dialog(
    importe: float, concepto: str, requiere_justificacion: bool
) -> tuple[bool, str]:
    """
    Muestra diálogo PyQt5 al usuario.
    Returns: (autorizado, justificacion)
    """
    try:
        from PyQt5.QtWidgets import (
            QApplication,
            QDialog,
            QVBoxLayout,
            QLabel,
            QTextEdit,
            QPushButton,
            QHBoxLayout,
            QMessageBox,
        )

        app = QApplication.instance()
        if app is None:
            return False, ""

        if not requiere_justificacion:
            reply = QMessageBox.question(
                None,
                "⚠️ Autorización de Pago",
                f"URA quiere realizar un pago de <b>{importe:.2f} €</b><br><br>"
                f"<b>Concepto:</b> {concepto}<br><br>"
                f"¿Autorizas este pago?",
            )
            autorizado = reply == QMessageBox.Yes
            return autorizado, ""

        # Diálogo con justificación obligatoria
        dialog = QDialog()
        dialog.setWindowTitle("🔐 Autorización de Pago — Justificación requerida")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"<b>Importe:</b> {importe:.2f} €"))
        layout.addWidget(QLabel(f"<b>Concepto:</b> {concepto}"))
        layout.addWidget(QLabel("<b>Escribe una justificación para autorizar:</b>"))

        texto = QTextEdit()
        texto.setPlaceholderText("Explica por qué autorizas este pago...")
        layout.addWidget(texto)

        btns = QHBoxLayout()
        btn_ok = QPushButton("✅ Autorizar")
        btn_no = QPushButton("❌ Rechazar")
        btns.addWidget(btn_no)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

        result = {"ok": False}

        def _accept():
            if len(texto.toPlainText().strip()) < 10:
                QMessageBox.warning(
                    dialog, "Justificación requerida", "Escribe al menos 10 caracteres."
                )
                return
            result["ok"] = True
            dialog.accept()

        btn_ok.clicked.connect(_accept)
        btn_no.clicked.connect(dialog.reject)

        dialog.exec_()
        return result["ok"], texto.toPlainText().strip()

    except Exception as e:
        logger.error("Error en diálogo de pago: %s", e)
        return False, ""


# ── función principal ─────────────────────────────────────────────────────────


def autorizar_pago(importe: float, concepto: str, fuente: str = "sistema") -> bool:
    """
    Pide autorización para un pago según los umbrales configurados.

    Args:
        importe:  Importe en euros
        concepto: Descripción del pago
        fuente:   Módulo/agente que solicita el pago

    Returns:
        True si autorizado, False si rechazado o bloqueado
    """
    logger.info("Solicitud de pago: %.2f€ — %s (fuente: %s)", importe, concepto, fuente)

    # ── < 10€: automático PERO con control de acumulado ───────────────────────
    if importe < UMBRAL_NOTIFICAR:
        acumulado = _calcular_acumulado_automatico(VENTANA_ACUMULADO_MINUTOS)
        if acumulado + importe > UMBRAL_ACUMULADO:
            logger.warning(
                "Pago pequeño (%.2f€) pero acumulado %.2f€ en %dmin supera %.0f€ — requiere autorización",
                importe,
                acumulado,
                VENTANA_ACUMULADO_MINUTOS,
                UMBRAL_ACUMULADO,
            )
            token = uuid.uuid4().hex[:12]
            pendientes_path = ROOT / "data" / "pending_payments.jsonl"
            _queue_pending_payment(importe, concepto, fuente, token, pendientes_path)
            _send_telegram_buttons(importe, concepto, fuente, token, pendientes_path)
            _audit(
                importe,
                concepto,
                fuente,
                "bloqueado_acumulado_excedido",
                f"Acumulado {acumulado:.2f}€ + {importe:.2f}€ > {UMBRAL_ACUMULADO}€. Token={token}",
            )
            return False
        _audit(importe, concepto, fuente, "autorizado_automatico")
        return True

    # ── ≥ 100€: bloquear + Telegram con botones ──────────────────────────────
    if importe >= UMBRAL_BLOQUEAR:
        token = uuid.uuid4().hex[:12]
        pendientes_path = ROOT / "data" / "pending_payments.jsonl"

        _queue_pending_payment(importe, concepto, fuente, token, pendientes_path)
        enviado = _send_telegram_buttons(importe, concepto, fuente, token, pendientes_path)

        _audit(
            importe,
            concepto,
            fuente,
            "bloqueado_pendiente_autorizacion",
            f"Token={token}, Telegram={'enviado' if enviado else 'fallido'}",
        )
        logger.warning("Pago de %.2f€ BLOQUEADO — token=%s esperando Telegram", importe, token)
        return False

    # ── 50-99€: diálogo Qt con justificación, fallback Telegram ──────────────
    if importe >= UMBRAL_JUSTIFICAR:
        if _qt_disponible():
            autorizado, justificacion = _show_qt_dialog(
                importe, concepto, requiere_justificacion=True
            )
            decision = "autorizado_con_justificacion" if autorizado else "rechazado_usuario"
            _audit(importe, concepto, fuente, decision, justificacion)
            return autorizado

        token = uuid.uuid4().hex[:12]
        pendientes_path = ROOT / "data" / "pending_payments.jsonl"
        _queue_pending_payment(importe, concepto, fuente, token, pendientes_path)
        _send_telegram_buttons(importe, concepto, fuente, token, pendientes_path)
        _audit(
            importe,
            concepto,
            fuente,
            "bloqueado_pendiente_autorizacion",
            f"Qt no disponible, Telegram fallback. Token={token}",
        )
        return False

    # ── 10-49€: notificación Qt, fallback Telegram ───────────────────────────
    if _qt_disponible():
        autorizado, _ = _show_qt_dialog(importe, concepto, requiere_justificacion=False)
        decision = "autorizado_usuario" if autorizado else "rechazado_usuario"
        _audit(importe, concepto, fuente, decision)
        return autorizado

    token = uuid.uuid4().hex[:12]
    pendientes_path = ROOT / "data" / "pending_payments.jsonl"
    _queue_pending_payment(importe, concepto, fuente, token, pendientes_path)
    _send_telegram_buttons(importe, concepto, fuente, token, pendientes_path)
    _audit(
        importe,
        concepto,
        fuente,
        "bloqueado_pendiente_autorizacion",
        f"Qt no disponible, Telegram fallback. Token={token}",
    )
    return False


def _qt_disponible() -> bool:
    """Comprueba si PyQt5 está disponible y hay display."""
    try:
        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        return app is not None
    except Exception:
        return False


def obtener_historial(n: int = 50) -> list[dict]:
    """Devuelve las últimas n entradas del audit log."""
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(l) for l in lines[-n:] if l.strip()]


if __name__ == "__main__":
    # test rápido (sin UI)
    print("Test < 10€:", autorizar_pago(5.0, "Prueba automática", "test"))
    print("Historial:", obtener_historial(3))
