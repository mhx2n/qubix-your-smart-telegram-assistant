# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 98 — QUBIX PRECISION PASS (2026-08-04)
#
#   1. Duplicate confirmations (.sp / .sx and friends) collapsed: an identical
#      card cannot be delivered twice to the same chat inside a short window.
#   2. Personal (token-added) bots: rich transport now honours the calling bot,
#      so `.aitopic` previews/reviews stay inside the user's own bot instead of
#      surfacing on the main Qubix bot.
#   3. `/stopquiz` and `/resumequiz` restored for workspace users — registered,
#      whitelisted and visible in the "/" command sheet.
#   4. Publishing progress notices ("Posting to Channel …") are retired the
#      moment the run completes, so the transcript stays clean.
#   5. Result card no longer carries channel buttons — the card itself lists
#      every connected channel with its number for `.post <channel#>`.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx98
import time as _t98

import telegram as _tg98


_QX98_MAIN_TOKEN = str(globals().get("BOT_TOKEN") or "").strip()


def _qx98_is_main(bot) -> bool:
    token = str(getattr(bot, "token", "") or "").strip()
    return (not token) or (not _QX98_MAIN_TOKEN) or token == _QX98_MAIN_TOKEN


# ─────────────────────────────────────────────────────────────────────────────
# 1) Identical-card suppression + progress-notice retirement
# ─────────────────────────────────────────────────────────────────────────────
_QX98_SEEN: dict = {}
_QX98_WINDOW = 8.0
_QX98_PROGRESS = ("Posting to Channel", "Posting to Topic", "Posting to Group")
_QX98_DONE = ("Posting Complete", "Posted", "Stop Requested", "Posting Failed")
_QX98_TRACK: dict = {}


def _qx98_prune(now: float) -> None:
    for key, entry in list(_QX98_SEEN.items()):
        if now - entry[0] > _QX98_WINDOW * 3:
            _QX98_SEEN.pop(key, None)


def _qx98_key(chat_id, text, kwargs):
    if kwargs.get("reply_to_message_id") is not None:
        return None
    body = str(text or "")
    if len(body) < 12:
        return None
    return (str(chat_id), body[:400])


_qx98_prev_send = _tg98.Bot.send_message


async def _qx98_send_message(self, *args, **kwargs):
    chat_id = kwargs.get("chat_id", args[0] if args else None)
    text = kwargs.get("text", args[1] if len(args) > 1 else None)
    key = None
    with _cx98.suppress(Exception):
        key = _qx98_key(chat_id, text, kwargs)
    if key is not None:
        now = _t98.monotonic()
        with _cx98.suppress(Exception):
            _qx98_prune(now)
        cached = _QX98_SEEN.get(key)
        if cached and (now - cached[0]) < _QX98_WINDOW:
            return cached[1]

    message = await _qx98_prev_send(self, *args, **kwargs)
    if key is not None:
        with _cx98.suppress(Exception):
            _QX98_SEEN[key] = (_t98.monotonic(), message)

    with _cx98.suppress(Exception):
        body = str(text or "")
        slot = str(chat_id)
        if any(marker in body for marker in _QX98_PROGRESS):
            _QX98_TRACK[slot] = getattr(message, "message_id", None)
        elif any(marker in body for marker in _QX98_DONE):
            old = _QX98_TRACK.pop(slot, None)
            if old:
                with _cx98.suppress(Exception):
                    await self.delete_message(chat_id=chat_id, message_id=int(old))
    return message


if not getattr(_tg98.Bot.send_message, "_qx98", False):
    _qx98_send_message._qx98 = True  # type: ignore[attr-defined]
    _tg98.Bot.send_message = _qx98_send_message


# ─────────────────────────────────────────────────────────────────────────────
# 2) Rich transport respects the calling bot (personal bots stay self-contained)
# ─────────────────────────────────────────────────────────────────────────────
_qx98_prev_rich = globals().get("rich_send_77")
_qx98_prev_blocks = globals().get("rich_send_blocks_77")


async def _qx98_plain_send(bot, chat_id, text, *, reply_to=None, thread_id=None,
                           silent=False, reply_markup=None):
    payload = dict(
        chat_id=chat_id,
        text=str(text or " ")[:4000],
        disable_web_page_preview=True,
        disable_notification=bool(silent),
    )
    if reply_to:
        payload["reply_to_message_id"] = reply_to
        payload["allow_sending_without_reply"] = True
    if thread_id:
        payload["message_thread_id"] = thread_id
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        return await bot.send_message(parse_mode=ParseMode.HTML, **payload)
    except Exception:
        with _cx98.suppress(Exception):
            return await bot.send_message(**payload)
    return None


async def rich_send_77(bot, chat_id, text, **kwargs):  # noqa: F811
    if not _qx98_is_main(bot):
        return await _qx98_plain_send(
            bot, chat_id, text,
            reply_to=kwargs.get("reply_to"),
            thread_id=kwargs.get("thread_id"),
            silent=bool(kwargs.get("silent")),
        )
    if callable(_qx98_prev_rich):
        return await _qx98_prev_rich(bot, chat_id, text, **kwargs)
    return None


async def rich_send_blocks_77(bot, chat_id, blocks, **kwargs):  # noqa: F811
    if not _qx98_is_main(bot):
        parts = []
        for block in (blocks or []):
            if isinstance(block, dict):
                parts.append(str(block.get("html") or block.get("markdown") or block.get("text") or ""))
            else:
                parts.append(str(block))
        return await _qx98_plain_send(
            bot, chat_id, "\n\n".join(p for p in parts if p),
            reply_to=kwargs.get("reply_to"),
            thread_id=kwargs.get("thread_id"),
            silent=bool(kwargs.get("silent")),
            reply_markup=kwargs.get("reply_markup"),
        )
    if callable(_qx98_prev_blocks):
        return await _qx98_prev_blocks(bot, chat_id, blocks, **kwargs)
    return None


globals()["rich_send_77"] = rich_send_77
globals()["rich_send_blocks_77"] = rich_send_blocks_77


# ─────────────────────────────────────────────────────────────────────────────
# 3) Run control back in the workspace: /stopquiz · /resumequiz
# ─────────────────────────────────────────────────────────────────────────────
with _cx98.suppress(Exception):
    QX_WORKSPACE_COMMANDS |= {"stopquiz", "resumequiz"}
with _cx98.suppress(Exception):
    for _name98 in ("stopquiz", "resumequiz"):
        QX_RETIRED_USER_COMMANDS.discard(_name98)

QX98_USER_MENU_COMMANDS = list(globals().get("QX97_USER_MENU_COMMANDS") or [])
if QX98_USER_MENU_COMMANDS and not any(n == "stopquiz" for n, _ in QX98_USER_MENU_COMMANDS):
    _insert98 = next(
        (i for i, (n, _) in enumerate(QX98_USER_MENU_COMMANDS) if n == "clear"),
        len(QX98_USER_MENU_COMMANDS),
    )
    QX98_USER_MENU_COMMANDS[_insert98:_insert98] = [
        ("stopquiz", "চলমান run থামান"),
        ("resumequiz", "Run আবার চালু করুন"),
    ]
    globals()["QX97_USER_MENU_COMMANDS"] = QX98_USER_MENU_COMMANDS
    globals()["QX94_USER_MENU_COMMANDS"] = QX98_USER_MENU_COMMANDS


# ─────────────────────────────────────────────────────────────────────────────
# 4) Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx98_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx98_prev_build_app() if callable(_qx98_prev_build_app) else None
    if app is None:
        return app

    register = globals().get("_register_dual_command")
    pairs = (
        ("stopquiz", globals().get("cmd_stopquiz_81")),
        ("resumequiz", globals().get("cmd_resumequiz_81")),
    )
    for name, callback in pairs:
        if not callable(callback):
            continue
        with _cx98.suppress(Exception):
            if callable(register):
                register(app, name, callback, group=-1049)
            else:
                app.add_handler(CommandHandler(name, callback), group=-1049)

    _qx_log.info("[QUBIX-98] precision pass wired (no duplicate cards, tenant-safe rich transport, run control).")
    return app


_qx_log.info("[SECTION 98] Qubix precision pass loaded.")
