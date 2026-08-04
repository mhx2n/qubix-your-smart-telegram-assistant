# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 102 — QUBIX ERROR ROOM + PROFESSIONAL TOPIC "FIRST QUIZ LINK"
#
#   1. Owner sets ONE private group (optionally a forum topic) as the error
#      room:  /errgroup   inside that group.  Every runtime error of the main
#      bot AND of every tenant (token-added) bot is instantly reported there
#      as a rich diagnostic card: where, what, why, fix, who, user id, chat id.
#   2. When a quiz batch finishes publishing as a reply to a topic anchor, the
#      anchor message itself is edited and a stylish, AI-written invitation
#      line with an embedded deep-link to the FIRST quiz is appended.
#
# DO NOT import this file directly — exec'd in shared namespace by bot/__main__.py
# ══════════════════════════════════════════════════════════════════════════════

import asyncio as _a102
import contextlib as _cx102
import html as _h102
import json as _j102
import logging as _lg102
import os as _os102
import random as _rd102
import re as _re102
import time as _t102
import traceback as _tb102

import telegram as _tg102


def _log102(msg: str) -> None:
    with _cx102.suppress(Exception):
        _qx_log.info("[QUBIX-102] %s", msg)


def _esc102(value) -> str:
    return _h102.escape(str(value if value is not None else ""), quote=False)


# ─────────────────────────────────────────────────────────────────────────────
# 1) Error room storage
# ─────────────────────────────────────────────────────────────────────────────
def _qx102_db():
    return db_connect()  # type: ignore[name-defined]


def _qx102_init_tables() -> None:
    with _cx102.suppress(Exception):
        conn = _qx102_db()
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS qx_err_room ("
                "id INTEGER PRIMARY KEY, chat_id INTEGER, thread_id INTEGER, "
                "set_by INTEGER, set_at REAL)"
            )


_qx102_init_tables()


def _qx102_env_room():
    raw = (_os102.getenv("QX_ERROR_GROUP_ID") or _os102.getenv("ERROR_GROUP_ID") or "").strip()
    thread = (_os102.getenv("QX_ERROR_TOPIC_ID") or "").strip()
    try:
        chat_id = int(raw)
    except (TypeError, ValueError):
        return None, None
    try:
        thread_id = int(thread) if thread else None
    except (TypeError, ValueError):
        thread_id = None
    return chat_id, thread_id


def _qx102_room():
    """Return (chat_id, thread_id) of the error room, or (None, None)."""
    with _cx102.suppress(Exception):
        conn = _qx102_db()
        cur = conn.execute("SELECT chat_id, thread_id FROM qx_err_room WHERE id=1")
        row = cur.fetchone()
        if row and row[0]:
            return int(row[0]), (int(row[1]) if row[1] else None)
    return _qx102_env_room()


def _qx102_room_set(chat_id, thread_id, by_uid: int) -> None:
    conn = _qx102_db()
    with conn:
        conn.execute(
            "INSERT INTO qx_err_room (id, chat_id, thread_id, set_by, set_at) "
            "VALUES (1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "chat_id=excluded.chat_id, thread_id=excluded.thread_id, "
            "set_by=excluded.set_by, set_at=excluded.set_at",
            (int(chat_id) if chat_id else None,
             int(thread_id) if thread_id else None,
             int(by_uid or 0), _t102.time()),
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2) Diagnosis engine — "why" + "how to fix", in Bangla, owner-friendly
# ─────────────────────────────────────────────────────────────────────────────
_QX102_RULES = (
    (r"bot was blocked by the user",
     "ইউজার বটটি block করে রেখেছেন।",
     "ইউজারকে বট আবার unblock করে /start দিতে বলুন।"),
    (r"chat not found",
     "টার্গেট chat/channel id ভুল, বা বট সেখানে নেই।",
     "সঠিক id দিয়ে আবার add করুন — group/channel-এ বটকে admin করে /info দিয়ে id যাচাই করুন।"),
    (r"not enough rights|CHAT_ADMIN_REQUIRED|need administrator",
     "বটের প্রয়োজনীয় admin permission নেই।",
     "ওই channel/group-এ বটকে admin করুন (Post messages + Pin messages অন)।"),
    (r"message to edit not found|message can't be edited|MESSAGE_ID_INVALID",
     "যে message edit করতে চাওয়া হয়েছে তা মুছে গেছে বা অন্য বটের।",
     "নতুন করে topic set করুন (.topic / .aitopic / .linktopic)।"),
    (r"message is not modified",
     "একই কনটেন্ট দিয়ে edit করা হয়েছে — ক্ষতিকর নয়।",
     "কোনো কাজ দরকার নেই; উপেক্ষা করা যায়।"),
    (r"Flood control|Too Many Requests|RetryAfter|429",
     "Telegram rate-limit — খুব দ্রুত অনেক message গেছে।",
     "/postdelay দিয়ে delay কিছুটা বাড়িয়ে দিন, তারপর আবার post করুন।"),
    (r"Unauthorized|token.*(invalid|rejected)|invalid token",
     "Bot token ভুল বা বাতিল করা হয়েছে।",
     "BotFather থেকে নতুন token নিয়ে /addbot দিয়ে আবার সেট করুন।"),
    (r"Timed out|timeout|ReadTimeout|ConnectTimeout",
     "Network/API সাড়া দিতে দেরি করেছে।",
     "কিছুক্ষণ পর আবার চেষ্টা করুন; বারবার হলে Render service restart দিন।"),
    (r"quota|RESOURCE_EXHAUSTED|API key not valid|PERMISSION_DENIED",
     "AI provider key-এর quota শেষ বা key অচল।",
     "/keys দিয়ে key তালিকা দেখে নতুন key যোগ করুন এবং অচল key সরান।"),
    (r"database is locked|sqlite3",
     "Database একই সময়ে অনেক write পাচ্ছে।",
     "কিছুক্ষণ পর আবার দিন; বারবার হলে /qbackup নিয়ে service restart দিন।"),
    (r"ServerSelectionTimeout|pymongo|Mongo",
     "MongoDB backup সার্ভারে পৌঁছাতে পারছে না।",
     "Render-এ MONGODB_URI ঠিক আছে কি না দেখুন এবং Atlas-এ 0.0.0.0/0 whitelist করুন।"),
    (r"can't parse entities|Unsupported start tag|unsupported parse",
     "Message-এর HTML/Markdown ফরম্যাট ভাঙা ছিল।",
     "একই কনটেন্ট আবার generate করুন; সমস্যা থাকলে topic text সরল করে দিন।"),
    (r"poll can't be sent|question.*too long|MESSAGE_TOO_LONG|too long",
     "Quiz question/option Telegram-এর length limit ছাড়িয়ে গেছে।",
     "ছোট prefix ব্যবহার করুন (.sp) অথবা কম count-এ generate করুন।"),
)


def _qx102_diagnose(error: BaseException):
    text = f"{type(error).__name__}: {error}"
    for pattern, why, fix in _QX102_RULES:
        if _re102.search(pattern, text, _re102.IGNORECASE):
            return why, fix
    return (
        "অপ্রত্যাশিত runtime error — নিচের traceback-এ আসল কারণ আছে।",
        "একই কাজ আবার চেষ্টা করুন; আবার হলে traceback-এর শেষ লাইন ধরে ওই অংশ ঠিক করুন।",
    )


def _qx102_where(error: BaseException) -> str:
    frames = []
    with _cx102.suppress(Exception):
        frames = _tb102.extract_tb(error.__traceback__)
    if not frames:
        return "—"
    last = frames[-1]
    name = str(getattr(last, "filename", "") or "").split("/")[-1]
    return f"{name}:{getattr(last, 'lineno', '?')} → {getattr(last, 'name', '?')}()"


def _qx102_tb_tail(error: BaseException, limit: int = 900) -> str:
    raw = ""
    with _cx102.suppress(Exception):
        raw = "".join(
            _tb102.format_exception(type(error), error, error.__traceback__)
        ).strip()
    if not raw:
        raw = f"{type(error).__name__}: {error}"
    return raw[-limit:]


# ─────────────────────────────────────────────────────────────────────────────
# 3) Reporter
# ─────────────────────────────────────────────────────────────────────────────
_QX102_SEEN: dict = {}
_QX102_MUTE_WINDOW = 90.0


def _qx102_bot():
    app = globals().get("_QX_MAIN_APP")
    bot = getattr(app, "bot", None)
    if bot is not None:
        return bot
    with _cx102.suppress(Exception):
        token = str(globals().get("BOT_TOKEN") or "").strip()
        if token:
            return _tg102.Bot(token)
    return None


def _qx102_actor(update):
    user = getattr(update, "effective_user", None)
    chat = getattr(update, "effective_chat", None)
    message = getattr(update, "effective_message", None)
    name = str(getattr(user, "full_name", "") or "—")
    username = str(getattr(user, "username", "") or "")
    if username:
        name = f"{name} (@{username})"
    return {
        "who": name,
        "uid": int(getattr(user, "id", 0) or 0),
        "chat": getattr(chat, "id", None),
        "chat_type": str(getattr(chat, "type", "") or "—"),
        "action": str(
            getattr(message, "text", None)
            or getattr(getattr(update, "callback_query", None), "data", None)
            or "—"
        )[:120],
    }


def _qx102_card(error: BaseException, *, source: str, actor: dict, bot_label: str) -> str:
    why, fix = _qx102_diagnose(error)
    return (
        "🚨 <b>Qubix — Error Alert</b>\n"
        "<code>─────────────────────────</code>\n"
        f"🧩 <b>কী হয়েছে</b>\n<code>{_esc102(f'{type(error).__name__}: {error}')[:400]}</code>\n\n"
        f"📍 <b>কোথায়</b>\n<code>{_esc102(_qx102_where(error))}</code>\n"
        f"🛰 <b>উৎস</b> — <code>{_esc102(source)}</code>\n"
        f"🤖 <b>Bot</b> — <code>{_esc102(bot_label or '—')}</code>\n\n"
        f"❓ <b>কেন হয়েছে</b>\n{_esc102(why)}\n\n"
        f"🛠 <b>সমাধান</b>\n{_esc102(fix)}\n\n"
        f"👤 <b>কার জন্য</b> — {_esc102(actor.get('who'))}\n"
        f"🆔 <b>User ID</b> — <code>{actor.get('uid') or '—'}</code>\n"
        f"💬 <b>Chat</b> — <code>{actor.get('chat') if actor.get('chat') is not None else '—'}</code>"
        f" ({_esc102(actor.get('chat_type'))})\n"
        f"⌨️ <b>Action</b> — <code>{_esc102(actor.get('action'))}</code>\n"
        f"🕒 <code>{_t102.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        "<code>─────────────────────────</code>\n"
        f"<pre>{_esc102(_qx102_tb_tail(error))}</pre>"
    )


async def _qx102_deliver(text: str) -> None:
    chat_id, thread_id = _qx102_room()
    if not chat_id:
        return
    bot = _qx102_bot()
    if bot is None:
        return
    payload = dict(
        chat_id=chat_id,
        text=text[:4000],
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
    if thread_id:
        payload["message_thread_id"] = thread_id
    try:
        await bot.send_message(**payload)
    except Exception:
        payload.pop("parse_mode", None)
        payload["text"] = _re102.sub(r"<[^>]+>", "", text)[:4000]
        with _cx102.suppress(Exception):
            await bot.send_message(**payload)


async def qx102_report(error: BaseException, *, source: str = "runtime",
                       update=None, bot_label: str = "") -> None:
    signature = f"{source}|{type(error).__name__}|{str(error)[:120]}|{_qx102_where(error)}"
    now = _t102.time()
    last = _QX102_SEEN.get(signature, 0.0)
    if now - last < _QX102_MUTE_WINDOW:
        return
    _QX102_SEEN[signature] = now
    if len(_QX102_SEEN) > 400:
        for key in [k for k, v in _QX102_SEEN.items() if now - v > 900]:
            _QX102_SEEN.pop(key, None)
    actor = _qx102_actor(update) if update is not None else {
        "who": "—", "uid": 0, "chat": None, "chat_type": "—", "action": "—"
    }
    with _cx102.suppress(Exception):
        await _qx102_deliver(_qx102_card(error, source=source, actor=actor, bot_label=bot_label))


globals()["qx102_report"] = qx102_report


async def qx102_error_handler(update, context) -> None:
    error = getattr(context, "error", None)
    if not isinstance(error, BaseException):
        return
    label = ""
    with _cx102.suppress(Exception):
        tenant = context.application.bot_data.get("qx_tenant_uid")
        label = f"tenant #{tenant}" if tenant else "Qubix main"
    with _cx102.suppress(Exception):
        await qx102_report(error, source="update handler", update=update, bot_label=label)


# Any ERROR/CRITICAL log with an exception also lands in the error room.
class _QX102LogHandler(_lg102.Handler):
    def emit(self, record) -> None:  # noqa: D401
        try:
            if record.levelno < _lg102.ERROR:
                return
            if str(record.name or "").startswith("qubix.err"):
                return
            error = None
            if record.exc_info and record.exc_info[1] is not None:
                error = record.exc_info[1]
            else:
                error = RuntimeError(str(record.getMessage())[:300])
            source = f"log · {record.name}"
            loop = _a102.get_running_loop()
            loop.create_task(qx102_report(error, source=source, bot_label="Qubix runtime"))
        except RuntimeError:
            return
        except Exception:
            return


def _qx102_attach_log_bridge() -> None:
    root = _lg102.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing, _QX102LogHandler):
            return
    handler = _QX102LogHandler()
    handler.setLevel(_lg102.ERROR)
    root.addHandler(handler)


# ─────────────────────────────────────────────────────────────────────────────
# 4) Owner commands: /errgroup · /errgroupoff · /errtest
# ─────────────────────────────────────────────────────────────────────────────
def _qx102_is_owner(uid: int) -> bool:
    checker = globals().get("_qx_real_owner")
    if callable(checker):
        with _cx102.suppress(Exception):
            return bool(checker(int(uid)))
    with _cx102.suppress(Exception):
        return bool(is_owner(int(uid)))  # type: ignore[name-defined]
    return False


async def qx102_cmd_errgroup(update, context):
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        raise ApplicationHandlerStop
    if not _qx102_is_owner(int(getattr(user, "id", 0) or 0)):
        raise ApplicationHandlerStop

    chat = update.effective_chat
    thread_id = getattr(message, "message_thread_id", None)
    if getattr(chat, "type", "") not in ("group", "supergroup"):
        with _cx102.suppress(Exception):
            await message.reply_text(
                "🛡 <b>Error Room</b>\n<code>─────────────────────────</code>\n"
                "আপনার private group-এ Qubix-কে add করে সেখানে <code>/errgroup</code> দিন।\n"
                "Forum topic-এর ভিতরে দিলে ঠিক ওই topic-এ error card যাবে।",
                parse_mode=ParseMode.HTML,
            )
        raise ApplicationHandlerStop

    _qx102_room_set(chat.id, thread_id, int(user.id))
    with _cx102.suppress(Exception):
        await message.reply_text(
            "✅ <b>Error Room সেট হয়েছে</b>\n<code>─────────────────────────</code>\n"
            f"💬 Chat — <code>{_esc102(chat.id)}</code>\n"
            f"🧵 Topic — <code>{thread_id if thread_id else 'main'}</code>\n\n"
            "এখন থেকে main bot ও প্রতিটি user-bot-এর যেকোনো error সাথে সাথে এখানে আসবে — "
            "কোথায়, কেন, কার জন্য, কোন ID-তে, এবং সমাধান সহ।\n"
            "পরীক্ষা করতে <code>/errtest</code> দিন · বন্ধ করতে <code>/errgroupoff</code>।",
            parse_mode=ParseMode.HTML,
        )
    raise ApplicationHandlerStop


async def qx102_cmd_errgroupoff(update, context):
    user = getattr(update, "effective_user", None)
    message = getattr(update, "effective_message", None)
    if message is None or not _qx102_is_owner(int(getattr(user, "id", 0) or 0)):
        raise ApplicationHandlerStop
    _qx102_room_set(None, None, int(getattr(user, "id", 0) or 0))
    with _cx102.suppress(Exception):
        await message.reply_text(
            "🛑 <b>Error Room বন্ধ</b>\nআর কোনো error report পাঠানো হবে না।",
            parse_mode=ParseMode.HTML,
        )
    raise ApplicationHandlerStop


async def qx102_cmd_errtest(update, context):
    user = getattr(update, "effective_user", None)
    message = getattr(update, "effective_message", None)
    if message is None or not _qx102_is_owner(int(getattr(user, "id", 0) or 0)):
        raise ApplicationHandlerStop
    chat_id, _thread = _qx102_room()
    if not chat_id:
        with _cx102.suppress(Exception):
            await message.reply_text(
                "⚠️ আগে আপনার private group-এ <code>/errgroup</code> দিয়ে room সেট করুন।",
                parse_mode=ParseMode.HTML,
            )
        raise ApplicationHandlerStop
    try:
        raise RuntimeError("Qubix error-room self test — everything is wired.")
    except RuntimeError as probe:
        _QX102_SEEN.clear()
        await qx102_report(probe, source="self test", update=update, bot_label="Qubix main")
    with _cx102.suppress(Exception):
        await message.reply_text(
            "📨 Test error card আপনার error room-এ পাঠানো হয়েছে।",
            parse_mode=ParseMode.HTML,
        )
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 5) Topic anchor → "first quiz" invitation link (AI written, never repetitive)
# ─────────────────────────────────────────────────────────────────────────────
_QX102_MARK = "\u2063"          # invisible separator that isolates our tail
_QX102_SESSIONS: dict = {}
_QX102_SETTLE = 7.0             # seconds of silence that means "batch finished"

_QX102_FALLBACK = (
    ("কুইজ শুরু হয়ে গেছে — এখনই অংশ নিন", "প্রথম প্রশ্নে যান"),
    ("আজকের রাউন্ড লাইভ, দেরি করলে সময় শেষ", "শুরু করুন এখান থেকে"),
    ("প্রস্তুত? প্রথম প্রশ্ন আপনার অপেক্ষায়", "প্রথম কুইজ দেখুন"),
    ("নিজের প্রস্তুতি যাচাই করার সময় এখনই", "কুইজে ঢুকুন"),
    ("চ্যালেঞ্জ শুরু — স্কোর নিজেই মিলিয়ে নিন", "প্রথম প্রশ্ন"),
)


def _qx102_ai_line(count: int):
    """Ask the AI for a fresh CTA pair; fall back to a rotating preset."""
    caller = globals().get("call_gemini_text_rest")
    if callable(caller):
        prompt = (
            "তুমি একজন প্রফেশনাল বাংলা কনটেন্ট রাইটার। একটি Telegram কুইজ সেট "
            f"({count}টি প্রশ্ন) মাত্র পোস্ট হয়েছে। এমন একটি ছোট, আকর্ষণীয়, "
            "মানুষের লেখা মনে হয় এমন আহ্বান লেখো যা পড়ে সবাই প্রথম কুইজে ক্লিক করতে চাইবে।\n"
            "কঠোর নিয়ম: কোনো ভূমিকা নয়, কোনো hashtag নয়, কোনো bot/AI উল্লেখ নয়, "
            "emoji সর্বোচ্চ ১টি, line সর্বোচ্চ ৮ শব্দ, cta সর্বোচ্চ ৪ শব্দ।\n"
            'শুধু এই JSON দাও: {"line": "...", "cta": "..."}'
        )
        with _cx102.suppress(Exception):
            raw = str(caller(prompt) or "")
            match = _re102.search(r"\{.*\}", raw, _re102.DOTALL)
            if match:
                data = _j102.loads(match.group(0))
                line = str(data.get("line") or "").strip()
                cta = str(data.get("cta") or "").strip()
                if line and cta and len(line) <= 90 and len(cta) <= 40:
                    return line, cta
    return _rd102.choice(_QX102_FALLBACK)


async def _qx102_tail(link: str, count: int) -> str:
    try:
        line, cta = await _a102.to_thread(_qx102_ai_line, count)
    except Exception:
        line, cta = _rd102.choice(_QX102_FALLBACK)
    return (
        f"\n\n<b>✦ {_esc102(line)}</b>\n"
        f"➤ <a href=\"{_esc102(link)}\">{_esc102(cta)} 🔗</a>"
    )


def _qx102_link(message) -> str:
    chat = getattr(message, "chat", None)
    msg_id = getattr(message, "message_id", None)
    if chat is None or not msg_id:
        return ""
    username = str(getattr(chat, "username", "") or "")
    if username:
        return f"https://t.me/{username}/{msg_id}"
    chat_id = str(getattr(chat, "id", "") or "")
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{msg_id}"
    return ""


def _qx102_anchor_row(anchor_chat, anchor_msg):
    """Return (user_id, text, photo) for the stored topic anchor."""
    with _cx102.suppress(Exception):
        conn = _qx102_db()
        cur = conn.execute(
            "SELECT user_id, topic_anchor_text, topic_anchor_photo FROM users "
            "WHERE topic_anchor_msg=? AND (topic_anchor_chat=? OR topic_anchor_chat IS NULL) "
            "ORDER BY (topic_anchor_chat IS NULL) LIMIT 1",
            (int(anchor_msg), int(anchor_chat) if anchor_chat is not None else None),
        )
        row = cur.fetchone()
        if row:
            return int(row[0]), str(row[1] or ""), str(row[2] or "")
    return 0, "", ""


def _qx102_store_text(uid: int, text: str) -> None:
    if not uid:
        return
    with _cx102.suppress(Exception):
        conn = _qx102_db()
        with conn:
            conn.execute(
                "UPDATE users SET topic_anchor_text=? WHERE user_id=?", (text, int(uid))
            )


async def _qx102_apply_tail(bot, anchor_chat, anchor_msg, link: str, count: int) -> None:
    uid, stored, photo = _qx102_anchor_row(anchor_chat, anchor_msg)
    if not stored.strip():
        return
    base = stored.split(_QX102_MARK)[0].rstrip()
    tail = await _qx102_tail(link, count)
    body = base + _QX102_MARK + tail
    if len(body) > 3800:
        base = base[: 3800 - len(tail) - 1]
        body = base + _QX102_MARK + tail

    async def _try(payload_text: str) -> bool:
        try:
            if photo:
                await bot.edit_message_caption(
                    chat_id=anchor_chat, message_id=anchor_msg,
                    caption=payload_text, parse_mode=ParseMode.HTML,
                )
            else:
                await bot.edit_message_text(
                    chat_id=anchor_chat, message_id=anchor_msg, text=payload_text,
                    parse_mode=ParseMode.HTML, disable_web_page_preview=True,
                )
            return True
        except Exception:
            return False

    done = await _try(body)
    if not done:
        # The stored text may contain raw angle brackets — escape and retry.
        safe = _esc102(base) + _QX102_MARK + tail
        done = await _try(safe)
        if done:
            body = safe
    if not done:
        with _cx102.suppress(Exception):
            if photo:
                done = await _try(body)
    if done:
        _qx102_store_text(uid, body)
        _log102(f"topic anchor {anchor_chat}/{anchor_msg} now links the first quiz")


async def _qx102_settle(key) -> None:
    while True:
        await _a102.sleep(1.5)
        session = _QX102_SESSIONS.get(key)
        if not session:
            return
        if _t102.time() - float(session.get("ts") or 0) < _QX102_SETTLE:
            continue
        _QX102_SESSIONS.pop(key, None)
        bot = session.get("bot")
        link = str(session.get("link") or "")
        anchor_chat = session.get("anchor_chat")
        anchor_msg = session.get("anchor_msg")
        if bot is None or not link or not anchor_msg or anchor_chat is None:
            return
        try:
            await _qx102_apply_tail(
                bot, anchor_chat, anchor_msg, link, int(session.get("count") or 0)
            )
        except Exception as exc:  # never break publishing
            with _cx102.suppress(Exception):
                await qx102_report(exc, source="topic first-quiz link", bot_label="Qubix runtime")
        return


def _qx102_track(bot, kwargs: dict, message) -> None:
    anchor_msg = kwargs.get("reply_to_message_id")
    anchor_chat = kwargs.get("chat_id")
    params = kwargs.get("reply_parameters")
    if params is not None:
        anchor_msg = getattr(params, "message_id", None) or anchor_msg
        anchor_chat = getattr(params, "chat_id", None) or anchor_chat
    if not anchor_msg or anchor_chat is None:
        return
    link = _qx102_link(message)
    if not link:
        return
    key = (str(getattr(bot, "token", ""))[:16], str(anchor_chat), int(anchor_msg))
    session = _QX102_SESSIONS.get(key)
    if session is None:
        session = {
            "bot": bot, "link": link, "anchor_chat": anchor_chat,
            "anchor_msg": int(anchor_msg), "count": 0, "ts": _t102.time(),
        }
        _QX102_SESSIONS[key] = session
        with _cx102.suppress(RuntimeError):
            _a102.get_running_loop().create_task(_qx102_settle(key))
    session["count"] = int(session.get("count") or 0) + 1
    session["ts"] = _t102.time()


_qx102_prev_send_poll = _tg102.Bot.send_poll


async def _qx102_send_poll(self, *args, **kwargs):
    message = await _qx102_prev_send_poll(self, *args, **kwargs)
    with _cx102.suppress(Exception):
        _qx102_track(self, kwargs, message)
    return message


if not getattr(_tg102.Bot.send_poll, "_qx102", False):
    _qx102_send_poll._qx102 = True  # type: ignore[attr-defined]
    _tg102.Bot.send_poll = _qx102_send_poll


# ─────────────────────────────────────────────────────────────────────────────
# 6) Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx102_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx102_prev_build_app() if callable(_qx102_prev_build_app) else None
    if app is None:
        return app

    _qx102_attach_log_bridge()

    main_only = globals().get("_QX_MAIN_ONLY")
    for name, callback in (
        ("errgroup", qx102_cmd_errgroup),
        ("errgroupoff", qx102_cmd_errgroupoff),
        ("errtest", qx102_cmd_errtest),
    ):
        with _cx102.suppress(Exception):
            handler = CommandHandler(name, callback)
            app.add_handler(handler, group=-1250)
            if isinstance(main_only, list):
                main_only.append(handler)

    with _cx102.suppress(Exception):
        app.add_error_handler(qx102_error_handler)

    _log102("error room + professional topic first-quiz link wired.")
    return app


_log102("section loaded (owner error room, AI-written first-quiz topic link).")
