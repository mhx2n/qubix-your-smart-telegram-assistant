# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 97 — QUBIX PROFESSIONAL POLISH (2026-08-03)
#
#   1. `.help <question>` / `/help <question>` → real AI answer again.
#      (Root cause: the dot-command wrapper raises ApplicationHandlerStop even
#      when an earlier panel router returns silently, so the AI path never ran.)
#   2. Personal (token-added) bots: /mybot, /removebot, /myid removed — command
#      sheet, inline keyboard and command routing all drop them.
#   3. Every user-facing surface says "CSV export" only (no "CSV + JSON"),
#      export filenames are Qubix-branded, and internal disclaimers
#      ("listing শুধু আপনার data", "শুধু আপনার জন্য বরাদ্দ ফিচার") never ship.
#   4. Channel/topic post via the inline button now sends the score reply to the
#      first posted quiz, exactly like the command path.
#   5. Full command sheet: .exo .exf .sp .sx .bc .c and friends registered,
#      un-retired and visible in Telegram's "/" menu.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx97
import contextvars as _cv97
import re as _re97

import telegram as _tg97
from telegram.ext import TypeHandler as _TypeHandler97


# ─────────────────────────────────────────────────────────────────────────────
# 0) Tenant scope flag (per update, set by a non-blocking gate)
# ─────────────────────────────────────────────────────────────────────────────
_QX97_TENANT = _cv97.ContextVar("qx97_tenant", default=False)


def _qx97_tenant(context) -> bool:
    checker = globals().get("_qx95_is_tenant")
    if callable(checker):
        with _cx97.suppress(Exception):
            return bool(checker(context))
    return False


async def qx97_scope_gate(update, context):
    """Never blocks. Records whether this update came from a personal bot."""
    with _cx97.suppress(Exception):
        _QX97_TENANT.set(_qx97_tenant(context))


# ─────────────────────────────────────────────────────────────────────────────
# 1) Outbound text polish (runs on top of the section-96 shield)
# ─────────────────────────────────────────────────────────────────────────────
_QX97_REPLACE = (
    ("CSV + JSON", "CSV"),
    ("CSV+JSON", "CSV"),
    ("CSV ও JSON", "CSV"),
    ("csv + json", "csv"),
    ("csv+json", "csv"),
    ("CSV & JSON", "CSV"),
    ("probaho", "qubix"),
    ("প্রবাহ", "Qubix"),
)

_QX97_DROP_LINE = (
    "শুধু আপনার নিজের data",
    "শুধুমাত্র আপনার নিজের data",
    "বরাদ্দ ফিচার",
    "listing শুধু",
    "Locked:",
    "PDF",
    "/mybot on|off",
    "/mybot on</code>",
)


def _qx97_scrub(text):
    if not isinstance(text, str) or not text:
        return text
    out = text
    for old, new in _QX97_REPLACE:
        if old in out:
            out = out.replace(old, new)
    if any(marker in out for marker in _QX97_DROP_LINE):
        kept = [
            line for line in out.split("\n")
            if not any(marker in line for marker in _QX97_DROP_LINE)
        ]
        out = "\n".join(kept)
        out = _re97.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def _qx97_scrub_slot(args, kwargs, index, name):
    if name in kwargs:
        kwargs[name] = _qx97_scrub(kwargs[name])
        return args, kwargs
    if isinstance(index, int) and len(args) > index and isinstance(args[index], str):
        lst = list(args)
        lst[index] = _qx97_scrub(lst[index])
        return tuple(lst), kwargs
    return args, kwargs


_qx97_prev_send = _tg97.Bot.send_message
_qx97_prev_edit = _tg97.Bot.edit_message_text
_qx97_prev_doc = _tg97.Bot.send_document


async def _qx97_send_message(self, *args, **kwargs):
    with _cx97.suppress(Exception):
        args, kwargs = _qx97_scrub_slot(args, kwargs, 1, "text")
    return await _qx97_prev_send(self, *args, **kwargs)


async def _qx97_edit_message_text(self, *args, **kwargs):
    with _cx97.suppress(Exception):
        args, kwargs = _qx97_scrub_slot(args, kwargs, 0, "text")
    return await _qx97_prev_edit(self, *args, **kwargs)


async def _qx97_send_document(self, *args, **kwargs):
    with _cx97.suppress(Exception):
        args, kwargs = _qx97_scrub_slot(args, kwargs, None, "caption")
        name = kwargs.get("filename")
        if isinstance(name, str) and name:
            kwargs["filename"] = _qx97_scrub(name)
    return await _qx97_prev_doc(self, *args, **kwargs)


if not getattr(_tg97.Bot.send_message, "_qx97", False):
    _qx97_send_message._qx97 = True          # type: ignore[attr-defined]
    _qx97_edit_message_text._qx97 = True     # type: ignore[attr-defined]
    _qx97_send_document._qx97 = True         # type: ignore[attr-defined]
    _tg97.Bot.send_message = _qx97_send_message
    _tg97.Bot.edit_message_text = _qx97_edit_message_text
    _tg97.Bot.send_document = _qx97_send_document


# ─────────────────────────────────────────────────────────────────────────────
# 2) Command inventory — full user sheet, tenant-aware
# ─────────────────────────────────────────────────────────────────────────────
QX97_TENANT_HIDDEN = {"mybot", "removebot", "delbot", "myid", "wake"}

QX97_USER_MENU_COMMANDS = [
    ("start", "Workspace menu"),
    ("menu", "Workspace menu"),
    ("commands", "আমার সব command"),
    ("gen", "Quiz generate (reply দিয়ে)"),
    ("buffer", "Buffer দেখুন"),
    ("buffercount", "Buffer কতটি"),
    ("bc", "Buffer count (short)"),
    ("done", "CSV export"),
    ("clear", "Buffer খালি করুন"),
    ("c", "Buffer clear (short)"),
    ("exo", "Explanation ON"),
    ("exf", "Explanation OFF"),
    ("sp", "Channel prefix সেট"),
    ("sx", "Explanation link সেট"),
    ("addchannel", "Channel যোগ করুন"),
    ("listchannels", "Channel list"),
    ("removechannel", "Channel সরান"),
    ("post", "Channel-এ post"),
    ("adg", "Group যোগ করুন"),
    ("listgroups", "Group list"),
    ("info", "Group/Topic info"),
    ("adtc", "Topic যোগ করুন"),
    ("listtopics", "Topic list"),
    ("pt", "Topic-এ post"),
    ("topic", "Topic card"),
    ("aitopic", "AI topic card"),
    ("topicpin", "Topic card pin"),
    ("topicunpin", "Topic card unpin"),
    ("mytopics", "আমার topic anchor"),
    ("usetopic", "Topic anchor নির্বাচন"),
    ("cleartopic", "Topic anchor মুছুন"),
    ("addbot", "নিজের bot token যোগ"),
    ("mybot", "নিজের bot on/off"),
    ("removebot", "নিজের bot সরান"),
    ("myid", "আমার User ID"),
    ("help", "সহায়তা / প্রশ্ন করুন"),
]

globals()["QX94_USER_MENU_COMMANDS"] = QX97_USER_MENU_COMMANDS

# Everything above is a legitimate user command now.
with _cx97.suppress(Exception):
    QX_WORKSPACE_COMMANDS |= {name for name, _ in QX97_USER_MENU_COMMANDS}
    QX_WORKSPACE_COMMANDS |= {
        "setprefix", "setexplink", "sp", "sx", "exo", "exf", "exp",
        "explainon", "explainoff", "bc", "b", "c", "clear", "buffercount",
    }
with _cx97.suppress(Exception):
    for _name97 in (
        "exo", "exf", "exp", "explain", "explainon", "explainoff",
        "setprefix", "setexplink", "sp", "sx", "buffercount", "bc", "b",
        "clear", "c",
    ):
        QX_RETIRED_USER_COMMANDS.discard(_name97)


def _qx94_bot_commands(owner: bool):  # noqa: F811
    if owner:
        source = globals().get("QX94_OWNER_MENU_COMMANDS") or []
    else:
        source = QX97_USER_MENU_COMMANDS
        if _QX97_TENANT.get():
            source = [(n, d) for n, d in source if n not in QX97_TENANT_HIDDEN]
    out = []
    for name, desc in source:
        with _cx97.suppress(Exception):
            out.append(_tg97.BotCommand(name, str(desc)[:256]))
    return out


globals()["_qx94_bot_commands"] = _qx94_bot_commands


# ─────────────────────────────────────────────────────────────────────────────
# 3) Tenant keyboards: no "My Bot" button
# ─────────────────────────────────────────────────────────────────────────────
_qx97_prev_menu_kb = globals().get("_qx93_menu_kb")


def _qx93_menu_kb():  # noqa: F811
    kb = _qx97_prev_menu_kb() if callable(_qx97_prev_menu_kb) else None
    if kb is None or not _QX97_TENANT.get():
        return kb
    rows = []
    for row in getattr(kb, "inline_keyboard", []) or []:
        keep = [
            btn for btn in row
            if str(getattr(btn, "callback_data", "") or "") != "qx93:mybot"
        ]
        if keep:
            rows.append(keep)
    with _cx97.suppress(Exception):
        return _tg97.InlineKeyboardMarkup(rows)
    return kb


globals()["_qx93_menu_kb"] = _qx93_menu_kb


async def qx97_tenant_blocked_cmd(update, context):
    """On a personal bot, retired self-management commands just show the menu."""
    if not _qx97_tenant(context):
        return
    handler = globals().get("qx94_user_menu")
    if callable(handler):
        with _cx97.suppress(Exception):
            await handler(update, context)
    raise ApplicationHandlerStop


def _qx97_hidden_handler():
    names = "|".join(sorted(QX97_TENANT_HIDDEN))
    pattern = rf"^[./]({names})(@\w+)?(\s|$)"
    return MessageHandler(filters.Regex(pattern), qx97_tenant_blocked_cmd)


# ─────────────────────────────────────────────────────────────────────────────
# 4) `.help <question>` → AI answer (professional prompt, no meta talk)
# ─────────────────────────────────────────────────────────────────────────────
def _qx92_help_prompt(question: str) -> str:  # noqa: F811
    return (
        "You are Qubix, a professional Telegram quiz-workspace assistant. "
        "Answer as the product itself — never mention AI models, prompts, "
        "restrictions, owners, admins, logs, keys, databases, or any command "
        "outside the list below.\n\n"
        "Workspace features (private inbox):\n"
        "- Generate quiz: reply to a poll/quiz, a photo, or any text topic with "
        ".gen <count>, .gen medical <count>, .gen engineering <count>, "
        ".gen versity <count> (1-500)\n"
        "- Buffer: /buffer, /buffercount, .bc, clear with .c\n"
        "- Export: .done → CSV file\n"
        "- Explanation: .exo (on), .exf (off)\n"
        "- Channels: /addchannel @channel, /listchannels, /removechannel, "
        ".post <channel#>, .sp (prefix), .sx (explanation link)\n"
        "- Groups & topics: .adg <group_id>, .adtc <group#> <thread_id> <name>, "
        ".pt <group#> <topic#>, .listgroups, .listtopics, .info\n"
        "- Topic card: .topic, .aitopic, .topicpin, .topicunpin, .mytopics, "
        ".usetopic <id>, .cleartopic\n"
        "- Personal bot: /addbot <token>; saved bots stay ready automatically\n\n"
        "Style: reply in the user's language (Bangla/Banglish if they wrote so), "
        "confident and practical, Telegram HTML only (<b>, <i>, <code>), exact "
        "command examples, max 12 lines. No greetings, no disclaimers.\n\n"
        f"User question: {question}"
    )


globals()["_qx92_help_prompt"] = _qx92_help_prompt


def _qx97_question(update) -> str:
    message = getattr(update, "effective_message", None)
    text = str(getattr(message, "text", "") or "").strip()
    if not text or text[0] not in "./":
        return ""
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


async def qx97_help(update, context):
    question = _qx97_question(update)
    if not question:
        for name in ("qx94_owner_menu", "qx94_user_menu"):
            handler = globals().get(name)
            if callable(handler):
                with _cx97.suppress(ApplicationHandlerStop):
                    await handler(update, context)
        raise ApplicationHandlerStop

    uid = 0
    with _cx97.suppress(Exception):
        resolver = globals().get("_qx95_scope_uid") or globals().get("_qx93_uid")
        uid = int(resolver(update, context))
    if not uid:
        with _cx97.suppress(Exception):
            uid = int(update.effective_user.id)

    if not _qx_real_owner(uid):
        state = {}
        with _cx97.suppress(Exception):
            state = _qx_access(uid) or {}
        if not state.get("ok"):
            with _cx97.suppress(Exception):
                await update.effective_message.reply_text(
                    _qx_expired_card(uid, getattr(update.effective_user, "full_name", "")),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            raise ApplicationHandlerStop
        with _cx97.suppress(Exception):
            _QX_ACTING_OWNER.set(int(uid))

    thinking = None
    with _cx97.suppress(Exception):
        thinking = await update.effective_message.reply_text(
            "💬 <b>Qubix Assistant</b>\n<code>─────────────────────────</code>\n"
            "উত্তর তৈরি হচ্ছে…",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    answer = ""
    with _cx97.suppress(Exception):
        answer = await _qx92_ai_help(question)
    if not answer:
        answer = (
            "এখন উত্তর তৈরি করা যাচ্ছে না। নিচের menu থেকে সরাসরি কাজ চালিয়ে যান — "
            "quiz বানাতে কোনো poll/photo/text-এ reply করে <code>.gen 15</code> দিন।"
        )
    body = (
        "💬 <b>Qubix Assistant</b>\n<code>─────────────────────────</code>\n" + answer
    )
    if thinking is not None:
        with _cx97.suppress(Exception):
            await thinking.edit_text(
                body,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx93_menu_kb(),
                disable_web_page_preview=True,
            )
    else:
        with _cx97.suppress(Exception):
            await update.effective_message.reply_text(
                body,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx93_menu_kb(),
                disable_web_page_preview=True,
            )
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 5) Inline channel/topic post → score reply on the first quiz
# ─────────────────────────────────────────────────────────────────────────────
_QX97_CAPTURE = _cv97.ContextVar("qx97_capture", default=None)
_qx97_prev_poll = _tg97.Bot.send_poll


async def _qx97_send_poll(self, *args, **kwargs):
    message = await _qx97_prev_poll(self, *args, **kwargs)
    box = _QX97_CAPTURE.get()
    if isinstance(box, dict):
        with _cx97.suppress(Exception):
            box["n"] = int(box.get("n") or 0) + 1
            if box.get("id") is None:
                box["id"] = getattr(message, "message_id", None)
                box["chat"] = getattr(getattr(message, "chat", None), "id", None)
                box["thread"] = kwargs.get("message_thread_id")
    return message


if not getattr(_tg97.Bot.send_poll, "_qx97", False):
    _qx97_send_poll._qx97 = True  # type: ignore[attr-defined]
    _tg97.Bot.send_poll = _qx97_send_poll


async def qx97_cb_post(update, context):
    query = getattr(update, "callback_query", None)
    handler = globals().get("cb_pba")
    if query is None or not callable(handler):
        return
    box = {"id": None, "chat": None, "thread": None, "n": 0}
    _QX97_CAPTURE.set(box)
    try:
        await handler(update, context)
    finally:
        _QX97_CAPTURE.set(None)

    if box.get("id") and box.get("chat") and int(box.get("n") or 0) > 0:
        uid = 0
        with _cx97.suppress(Exception):
            uid = int(query.from_user.id)
        enabled = True
        checker = globals().get("_score_reply_enabled")
        if callable(checker):
            with _cx97.suppress(Exception):
                enabled = bool(checker(uid))
        if enabled:
            text = f"📝 Your score: ____ / {int(box['n'])}"
            maker = globals().get("_score_reply_text")
            if callable(maker):
                with _cx97.suppress(Exception):
                    text = maker(int(box["n"]))
            payload = dict(
                chat_id=box["chat"],
                text=text,
                reply_to_message_id=box["id"],
                allow_sending_without_reply=True,
            )
            if box.get("thread") is not None:
                payload["message_thread_id"] = box["thread"]
            with _cx97.suppress(Exception):
                await context.bot.send_message(**payload)
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 6) Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx97_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx97_prev_build_app() if callable(_qx97_prev_build_app) else None
    if app is None:
        return app

    with _cx97.suppress(Exception):
        app.add_handler(_TypeHandler97(Update, qx97_scope_gate), group=-2100)
    with _cx97.suppress(Exception):
        app.add_handler(_qx97_hidden_handler(), group=-1052)
    with _cx97.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx97_cb_post, pattern=r"^pba:post:"), group=-1051
        )

    register = globals().get("_register_dual_command")
    for name in ("help", "ask", "ai"):
        with _cx97.suppress(Exception):
            if callable(register):
                register(app, name, qx97_help, group=-1050)
            else:
                app.add_handler(CommandHandler(name, qx97_help), group=-1050)

    # .sp/.sx are already registered by the canonical alias registry (section
    # 26). Registering them again here executed the database update twice, so
    # the second confirmation showed the first update as its "old" value.

    _qx_log.info("[QUBIX-97] professional polish wired (AI help, CSV-only, score reply, full command sheet).")
    return app


_qx_log.info("[SECTION 97] Qubix professional polish loaded.")
