#!/usr/bin/env python3
"""
agente_telegram_dam.py — Integración Telegram ↔ DAM
Envía autorizaciones pendientes ALFA/OMEGA con botones Aprobar/Rechazar.
Cuando el usuario pulsa desde el móvil, valida o deniega en motor_autorizacion_dual.
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import contextlib
import json
import os

import telebot
from motor_autorizacion_dual import get_dam
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from core.payment_guardian import autorizar_pago_remoto, consultar_pago_pendiente

    PAYMENT_GUARDIAN_OK = True
except Exception:
    PAYMENT_GUARDIAN_OK = False

# ─── CONFIG ────────────────────────────────────────────────────────────
# Token y CHAT_ID confirmados: bot @ia_ura_bot, chat del owner
# Usar variable de entorno para seguridad
TOKEN = os.environ.get("TELEGRAM_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8621907530")
CHECK_INTERVAL = 30  # segundos entre comprobaciones de DAM

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# Importar DAM fuera del hilo para detectar errores al arrancar
try:
    dam = get_dam()
except Exception as _e:
    print(f"[TG-DAM] ❌ Error cargando DAM: {_e}", flush=True)
    raise

_notificados: set = set()  # tokens ya enviados para evitar duplicados
_lock = threading.Lock()


# ─── KEYBOARD ──────────────────────────────────────────────────────────
def _teclado(token: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Aprobar", callback_data=f"dam_ok_{token}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"dam_no_{token}"),
    )
    kb.row(
        InlineKeyboardButton("⏸ Pausar 24h", callback_data=f"dam_pausar_{token}"),
    )
    return kb


# ─── FORMATO DE MENSAJE ────────────────────────────────────────────────
def _esc(txt: str) -> str:
    """Escapa caracteres especiales HTML."""
    return str(txt).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _formatear_mensaje(p: dict) -> str:
    nivel = p.get("nivel", "ALFA")
    riesgo = p.get("riesgo_nivel", "DESCONOCIDO")
    accion = p.get("accion", "")
    descripcion = p.get("descripcion", "")
    archivo = p.get("archivo_objetivo", "") or "no especificado"
    origen = p.get("origen_proceso", "") or "orchestrator_v2"
    permisos = p.get("permisos_requeridos", "") or "sin permisos especiales"
    analisis = p.get("riesgo_analisis", "") or "sin análisis"
    analizado = p.get("analizado_por", "") or "motor_dam"
    justif = p.get("justificacion", "") or "ninguna"
    solicitante = p.get("solicitante", "URA")
    fecha = p.get("fecha", "")[:19].replace("T", " ")
    tok = p.get("token", "")
    bio_txt = " | ⚠️ <b>requiere biometría</b>" if p.get("requiere_biometrico") else ""

    nivel_ico = "🔴" if nivel == "OMEGA" else "🔐"
    riesgo_ico = {"ALTO": "🔴", "MEDIO": "🟡", "BAJO": "🟢"}.get(riesgo, "⚪")

    return (
        f"{nivel_ico} <b>Autorización DAM — {nivel}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Resumen:</b> {riesgo_ico} <code>{_esc(accion)}</code> — riesgo <b>{riesgo}</b>{bio_txt}\n\n"
        f"📦 <b>Objetivo:</b> <code>{_esc(archivo)}</code>\n"
        f"📝 <b>Descripción:</b> {_esc(descripcion)}\n"
        f"🔍 <b>Origen:</b> <code>{_esc(origen)}</code> · solicitado por <code>{_esc(solicitante)}</code>\n"
        f"🔑 <b>Permisos necesarios:</b>\n"
        f"   {_esc(permisos)}\n\n"
        f"🛡 <b>Análisis de seguridad</b> [{_esc(analizado)}]:\n"
        f"   {_esc(analisis)}\n\n"
        f"📌 <b>Justificación:</b> {_esc(justif)}\n"
        f"🕐 <b>Fecha:</b> {fecha}\n"
        f"🔖 <b>Token:</b> <code>{tok}</code>"
    )


# ─── ENVIAR PENDIENTES ─────────────────────────────────────────────────
def enviar_pendientes():
    """Envía mensaje Telegram por cada autorización DAM nueva."""
    try:
        pendientes = dam.obtener_pendientes()
    except Exception as e:
        print(f"[TG-DAM] Error consultando DAM: {e}", flush=True)
        return

    for p in pendientes:
        tok = p["token"]
        with _lock:
            if tok in _notificados:
                continue

        try:
            bot.send_message(
                CHAT_ID, _formatear_mensaje(p), parse_mode="HTML", reply_markup=_teclado(tok)
            )
            with _lock:
                _notificados.add(tok)
            print(f"[TG-DAM] ✉️  Enviado: {tok}", flush=True)
        except Exception as e:
            print(f"[TG-DAM] Error enviando {tok}: {e}", flush=True)


# ─── CALLBACKS ─────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data.startswith("dam_ok_"))
def handle_aprobar(call):
    token = call.data[len("dam_ok_") :]
    usuario = call.from_user.first_name or "usuario"
    nivel = _nivel_de_token(token)

    try:
        if nivel == "OMEGA":
            result = dam.validar_omega(token)
        else:
            result = dam.validar_alfa(token, validado_por=f"telegram:{usuario}")

        if result.get("estado") == "aprobado":
            bot.answer_callback_query(call.id, "✅ Autorización aprobada")
            _borrar_botones(call)
            bot.send_message(
                CHAT_ID, f"✅ *Aprobado* por {usuario}\n`{token}`", parse_mode="Markdown"
            )
            with _lock:
                _notificados.discard(token)
            print(f"[TG-DAM] ✅ Aprobado: {token} por {usuario}", flush=True)
        else:
            bot.answer_callback_query(
                call.id, f"⚠️ {result.get('error', result.get('mensaje', 'Error'))}"
            )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {str(e)[:60]}")
        print(f"[TG-DAM] Error aprobando {token}: {e}", flush=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("dam_pausar_"))
def handle_pausar(call):
    token = call.data[len("dam_pausar_") :]
    usuario = call.from_user.first_name or "usuario"
    try:
        result = dam.pausar(token, horas=24)
        if result.get("estado") == "pausado":
            bot.answer_callback_query(call.id, "⏸ Pausado 24h — se recordará mañana")
            _borrar_botones(call)
            bot.send_message(
                CHAT_ID,
                f"⏸ <b>Pausado 24h</b> por {_esc(usuario)}\n"
                f"Se renotificará el <b>{result['hasta'][:16]}</b>\n"
                f"<code>{token}</code>",
                parse_mode="HTML",
            )
            with _lock:
                _notificados.discard(token)
            print(f"[TG-DAM] ⏸ Pausado: {token} por {usuario}", flush=True)
        else:
            bot.answer_callback_query(call.id, result.get("error", "Error al pausar"))
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {str(e)[:60]}")
        print(f"[TG-DAM] Error pausando {token}: {e}", flush=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("dam_no_"))
def handle_rechazar(call):
    token = call.data[len("dam_no_") :]
    usuario = call.from_user.first_name or "usuario"

    try:
        dam.denegar(token, motivo=f"Rechazado vía Telegram por {usuario}")
        bot.answer_callback_query(call.id, "❌ Autorización rechazada")
        _borrar_botones(call)
        bot.send_message(CHAT_ID, f"❌ *Rechazado* por {usuario}\n`{token}`", parse_mode="Markdown")
        with _lock:
            _notificados.discard(token)
        print(f"[TG-DAM] ❌ Rechazado: {token} por {usuario}", flush=True)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {str(e)[:60]}")
        print(f"[TG-DAM] Error rechazando {token}: {e}", flush=True)


# ─── CALLBACK DE PAGOS ──────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data.startswith("pago_ok_"))
def handle_pago_aprobar(call):
    token = call.data[len("pago_ok_") :]
    usuario = call.from_user.first_name or "usuario"

    try:
        if not PAYMENT_GUARDIAN_OK:
            bot.answer_callback_query(call.id, "Payment guardian no disponible")
            return

        pendiente = consultar_pago_pendiente(token)
        if not pendiente:
            bot.answer_callback_query(call.id, "Pago no encontrado o ya procesado")
            return

        resultado = autorizar_pago_remoto(token, True, usuario)
        if resultado == "ok":
            bot.answer_callback_query(call.id, f"✅ Pago de {pendiente['importe']:.2f}€ aprobado")
            _borrar_botones(call)
            bot.send_message(
                call.message.chat.id,
                f"✅ <b>Pago de {pendiente['importe']:.2f}€ APROBADO</b>\n"
                f"Concepto: {pendiente['concepto']}\n"
                f"Autorizado por {_esc(usuario)}\n"
                f"<code>{token}</code>",
                parse_mode="HTML",
            )
            print(
                f"[TG-DAM] PAGO Aprobado: {pendiente['importe']:.2f}€ token={token} por {usuario}",
                flush=True,
            )
        else:
            bot.answer_callback_query(call.id, f"Estado: {resultado}")

    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {str(e)[:60]}")
        print(f"[TG-DAM] Error pago_ok {token}: {e}", flush=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("pago_no_"))
def handle_pago_rechazar(call):
    token = call.data[len("pago_no_") :]
    usuario = call.from_user.first_name or "usuario"

    try:
        if not PAYMENT_GUARDIAN_OK:
            bot.answer_callback_query(call.id, "Payment guardian no disponible")
            return

        pendiente = consultar_pago_pendiente(token)
        if not pendiente:
            bot.answer_callback_query(call.id, "Pago no encontrado o ya procesado")
            return

        resultado = autorizar_pago_remoto(token, False, usuario)
        if resultado == "ok":
            bot.answer_callback_query(call.id, f"❌ Pago de {pendiente['importe']:.2f}€ rechazado")
            _borrar_botones(call)
            bot.send_message(
                call.message.chat.id,
                f"❌ <b>Pago de {pendiente['importe']:.2f}€ RECHAZADO</b>\n"
                f"Concepto: {pendiente['concepto']}\n"
                f"Rechazado por {_esc(usuario)}\n"
                f"<code>{token}</code>",
                parse_mode="HTML",
            )
            print(
                f"[TG-DAM] PAGO Rechazado: {pendiente['importe']:.2f}€ token={token} por {usuario}",
                flush=True,
            )
        else:
            bot.answer_callback_query(call.id, f"Estado: {resultado}")

    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {str(e)[:60]}")
        print(f"[TG-DAM] Error pago_no {token}: {e}", flush=True)


@bot.message_handler(commands=["pagos"])
def cmd_pagos(message):
    """Lista pagos pendientes de autorización."""
    try:
        pendientes_path = Path(__file__).parent.parent / "data" / "pending_payments.jsonl"
        if not pendientes_path.exists():
            bot.reply_to(message, "No hay pagos pendientes.")
            return

        pendientes = []
        for line in pendientes_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("estado") == "pendiente":
                    pendientes.append(entry)
            except Exception:
                continue

        if not pendientes:
            bot.reply_to(message, "No hay pagos pendientes.")
            return

        for p in pendientes:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("✅ Aprobar", callback_data=f"pago_ok_{p['token']}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"pago_no_{p['token']}"),
            )
            txt = (
                f"🚨 <b>PAGO PENDIENTE — {p['importe']:.2f} €</b>\n"
                f"<b>Concepto:</b> {p['concepto']}\n"
                f"<b>Fuente:</b> {p['fuente']}\n"
                f"<b>Desde:</b> {p['timestamp'][:19]}\n"
                f"<code>{p['token']}</code>"
            )
            bot.send_message(message.chat.id, txt, parse_mode="HTML", reply_markup=kb)

    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)[:100]}")


# ─── COMANDOS ──────────────────────────────────────────────────────────
@bot.message_handler(commands=["pendientes"])
def cmd_pendientes(message):
    pendientes = dam.obtener_pendientes()
    if not pendientes:
        bot.reply_to(message, "✅ No hay autorizaciones pendientes.")
        return
    for p in pendientes:
        tok = p["token"]
        try:
            bot.send_message(
                message.chat.id,
                _formatear_mensaje(p),
                parse_mode="HTML",
                reply_markup=_teclado(tok),
            )
        except Exception as e:
            print(f"[TG-DAM] Error cmd_pendientes {tok}: {e}", flush=True)
        with _lock:
            _notificados.add(tok)


@bot.message_handler(commands=["estado"])
def cmd_estado(message):
    s = dam.obtener_estado()
    txt = (
        f"🔐 *DAM — Estado*\n"
        f"Pendientes: {s['pendientes']}\n"
        f"ALFA aprobadas: {s['alfa_aprobadas']}\n"
        f"OMEGA aprobadas: {s['omega_aprobadas']}\n"
        f"Sistema: {s['sistema']}"
    )
    bot.reply_to(message, txt, parse_mode="Markdown")


# ─── HELPERS ───────────────────────────────────────────────────────────
def _nivel_de_token(token: str) -> str:
    """Consulta el nivel de una autorización por su token."""
    try:
        import sqlite3

        conn = sqlite3.connect(dam.db_path, timeout=10)
        row = conn.execute(
            "SELECT nivel FROM autorizaciones_dam WHERE token=?", (token,)
        ).fetchone()
        conn.close()
        return row[0] if row else "ALFA"
    except Exception:
        return "ALFA"


def _borrar_botones(call):
    with contextlib.suppress(Exception):
        bot.edit_message_reply_markup(
            call.message.chat.id, call.message.message_id, reply_markup=None
        )


# ─── LOOP DE COMPROBACIÓN DAM ──────────────────────────────────────────
def _loop_check_dam():
    while True:
        try:
            enviar_pendientes()
        except Exception as e:
            print(f"[TG-DAM] Error en loop: {e}", flush=True)
        time.sleep(CHECK_INTERVAL)


# ─── PUNTO DE ENTRADA ──────────────────────────────────────────────────
def run():
    print(f"[TG-DAM] Iniciando — check cada {CHECK_INTERVAL}s", flush=True)
    # Enviar pendientes existentes al arrancar
    enviar_pendientes()
    # Thread de comprobación periódica
    t = threading.Thread(target=_loop_check_dam, daemon=True, name="tg-dam-check")
    t.start()
    print("[TG-DAM] Long polling activo...", flush=True)
    bot.infinity_polling(timeout=20, long_polling_timeout=15)


if __name__ == "__main__":
    run()
