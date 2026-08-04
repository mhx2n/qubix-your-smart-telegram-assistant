# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 114 — QUBIX STUDENT POLISH (2026-08-05)
#
#   1. Expired card: the "Approval পাওয়ার সাথে সাথে…" line is removed.
#   2. "📥 Sending — Quiz গুলো আপনার inbox-এ পাঠানো হচ্ছে…" card is now deleted
#      after delivery instead of lingering.
#   3. Student surface never shows channel/topic publishing info
#      (Channel Directory · .post · .pt · /addchannel) — scrubbed at delivery.
#   4. Student inbox flow: the summary card and the exported CSV both reply to
#      the FIRST quiz of the current batch. After an export the anchor resets so
#      the next batch starts fresh.
#   5. Student CSV: every question starts with "[bot name] " so a leaked file is
#      traceable. Students only.
#   6. Student quizzes always carry explanations (auto-on), and the owner's
#      /studentprefix + /studentexplink are applied.
#
#   Layer-only: no earlier section is rewritten.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx114
import telegram as _tg114

_QX114_ANCHOR = {}        # uid -> (chat_id, message_id)
_QX114_BOTNAME = {}       # uid -> bot display name
_QX114_TIER_CACHE = {}    # uid -> (tier, ts)


# ─────────────────────────────────────────────────────────────────────────────
# 0) helpers
# ─────────────────────────────────────────────────────────────────────────────
def _qx114_tier(uid) -> str:
    try:
        uid = int(uid or 0)
    except Exception:
        return ""
    if uid <= 0:
        return ""
    now = 0.0
    with _cx114.suppress(Exception):
        now = time.time()
    cached = _QX114_TIER_CACHE.get(uid)
    if cached and now and (now - cached[1]) < 20:
        return cached[0]
    tier = ""
    with _cx114.suppress(Exception):
        tier = str(_qx112_tier(uid) or "")
    _QX114_TIER_CACHE[uid] = (tier, now)
    return tier


def _qx114_is_student(uid) -> bool:
    return _qx114_tier(uid) == "student"


def _qx114_bot_name(uid) -> str:
    name = str(_QX114_BOTNAME.get(int(uid or 0)) or "").strip()
    if name:
        return name
    with _cx114.suppress(Exception):
        return str(globals().get("QX_BRAND_NAME") or "Qubix")
    return "Qubix"


# ─────────────────────────────────────────────────────────────────────────────
# 1) Expired card without the "your own bot will restart" promise
# ─────────────────────────────────────────────────────────────────────────────
_qx114_prev_expired = globals().get("_qx_expired_card")


def _qx_expired_card(uid: int, name: str = "") -> str:  # noqa: F811
    text = ""
    if callable(_qx114_prev_expired):
        with _cx114.suppress(Exception):
            text = str(_qx114_prev_expired(uid, name) or "")
    if not text:
        return text
    lines = [
        line for line in text.split("\n")
        if "Approval পাওয়ার সাথে সাথে" not in line
    ]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


globals()["_qx_expired_card"] = _qx_expired_card


# ─────────────────────────────────────────────────────────────────────────────
# 2) Explanations are always ON for student quizzes
# ─────────────────────────────────────────────────────────────────────────────
_qx114_prev_explain_on = globals().get("explain_mode_on")


def explain_mode_on(user_id: int) -> bool:  # noqa: F811
    if _qx114_is_student(user_id):
        return True
    if callable(_qx114_prev_explain_on):
        with _cx114.suppress(Exception):
            return bool(_qx114_prev_explain_on(user_id))
    return False


globals()["explain_mode_on"] = explain_mode_on


# ─────────────────────────────────────────────────────────────────────────────
# 3) Student CSV rows — "[bot name] " in front of every question
# ─────────────────────────────────────────────────────────────────────────────
_qx114_prev_done_rows = globals().get("_done_rows_62")


def _done_rows_62(items, uid, *, repair=False):  # noqa: F811
    rows = []
    if callable(_qx114_prev_done_rows):
        rows = _qx114_prev_done_rows(items, uid, repair=repair) or []
    if not rows or not _qx114_is_student(uid):
        return rows
    tag = "[%s] " % _qx114_bot_name(uid)
    for row in rows:
        with _cx114.suppress(Exception):
            question = str(row.get("questions") or "")
            if question and not question.startswith(tag):
                row["questions"] = tag + question
    return rows


globals()["_done_rows_62"] = _done_rows_62


# ─────────────────────────────────────────────────────────────────────────────
# 4) Master-only publishing hints never reach a student chat
# ─────────────────────────────────────────────────────────────────────────────
_QX114_BLOCK_MARKERS = (
    "Channel Directory", "/addchannel", "Topic publish",
    ".post ", ".post&", ".pt ", ".pt&", "channel#", "group#", "topic#",
)


def _qx114_scrub(text: str) -> str:
    body = str(text or "")
    if not body:
        return body
    if not any(marker in body for marker in _QX114_BLOCK_MARKERS):
        return body
    kept = []
    for line in body.split("\n"):
        if any(marker in line for marker in _QX114_BLOCK_MARKERS):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or body


def _qx114_wrap_text_method(name: str) -> None:
    original = getattr(_tg114.Bot, name, None)
    if not callable(original) or getattr(original, "_qx114", False):
        return

    async def wrapper(self, *args, **kwargs):
        with _cx114.suppress(Exception):
            chat_id = kwargs.get("chat_id")
            body = kwargs.get("text")
            if (
                isinstance(body, str) and body
                and chat_id is not None and int(chat_id) > 0
                and _qx114_is_student(chat_id)
            ):
                kwargs["text"] = _qx114_scrub(body)
        return await original(self, *args, **kwargs)

    wrapper._qx114 = True  # type: ignore[attr-defined]
    setattr(_tg114.Bot, name, wrapper)


for _qx114_name in ("send_message", "edit_message_text"):
    with _cx114.suppress(Exception):
        _qx114_wrap_text_method(_qx114_name)


# ─────────────────────────────────────────────────────────────────────────────
# 5) Student CSV replies to the first quiz of the batch
# ─────────────────────────────────────────────────────────────────────────────
_qx114_prev_send_document = getattr(_tg114.Bot, "send_document", None)

if callable(_qx114_prev_send_document) and not getattr(_qx114_prev_send_document, "_qx114", False):

    async def _qx114_send_document(self, *args, **kwargs):
        with _cx114.suppress(Exception):
            chat_id = kwargs.get("chat_id")
            if (
                chat_id is not None and int(chat_id) > 0
                and "reply_to_message_id" not in kwargs
                and "reply_parameters" not in kwargs
                and _qx114_is_student(chat_id)
            ):
                anchor = _QX114_ANCHOR.get(int(chat_id))
                if anchor and int(anchor[0]) == int(chat_id):
                    kwargs["reply_to_message_id"] = int(anchor[1])
                    _QX114_ANCHOR.pop(int(chat_id), None)
        return await _qx114_prev_send_document(self, *args, **kwargs)

    _qx114_send_document._qx114 = True  # type: ignore[attr-defined]
    with _cx114.suppress(Exception):
        setattr(_tg114.Bot, "send_document", _qx114_send_document)


# ─────────────────────────────────────────────────────────────────────────────
# 6) Inbox delivery — no leftover "Sending" card, summary replies to quiz #1
# ─────────────────────────────────────────────────────────────────────────────
async def _qx114_deliver(context, uid: int, chat_id: int):
    items = []
    with _cx114.suppress(Exception):
        items = list(buffer_list(int(uid), limit=99999) or [])
    if not items:
        return (0, 0, None)
    poster = globals().get("_post_buffer_to_chat")
    if not callable(poster):
        return (0, 0, None)
    with _cx114.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))
    ok_count = fail_count = 0
    first_id = None
    with _cx114.suppress(Exception):
        ok_count, fail_count, first_id = await poster(
            context, int(uid), int(chat_id), items, None,
            _qx112_student_prefix(), _qx112_student_explink(),
        )
    return (int(ok_count or 0), int(fail_count or 0), first_id)


_qx114_prev_cb112 = globals().get("qx112_on_callback")


async def qx112_on_callback(update, context):  # noqa: F811
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("qx112:inbox"):
        if callable(_qx114_prev_cb112):
            return await _qx114_prev_cb112(update, context)
        return

    uid = 0
    with _cx114.suppress(Exception):
        uid = int(_qx95_scope_uid(update, context) or 0)
    with _cx114.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))
    with _cx114.suppress(Exception):
        _QX114_BOTNAME[int(uid)] = str(
            getattr(context.bot, "first_name", "") or getattr(context.bot, "username", "") or "Qubix"
        )
    chat_id = uid
    with _cx114.suppress(Exception):
        chat_id = int(getattr(getattr(query, "message", None), "chat_id", uid) or uid)

    with _cx114.suppress(Exception):
        await query.answer("পাঠানো হচ্ছে…")
    with _cx114.suppress(Exception):
        await query.message.delete()

    ok_count, fail_count, first_id = await _qx114_deliver(context, uid, chat_id)

    if ok_count and first_id:
        _QX114_ANCHOR[int(chat_id)] = (int(chat_id), int(first_id))
    if ok_count:
        body = (
            f"✅ পাঠানো হয়েছে: <b>{ok_count}</b>\n"
            + (f"⚠️ বাদ পড়েছে: <b>{fail_count}</b>\n" if fail_count else "")
            + "\nউপরের quiz গুলোতে উত্তর দিয়ে প্র্যাকটিস করুন। "
            "ফাইল লাগলে <code>.done</code> দিন।"
        )
    else:
        body = (
            "এখন buffer-এ কোনো quiz নেই।\n\n"
            "একটি <b>ছবি · টেক্সট · poll</b>-এ reply করে <code>.gen 15</code> দিন।"
        )

    kwargs = {
        "chat_id": chat_id,
        "text": "📥 <b>Inbox Practice</b>\n" + QX112_ROW + "\n" + body,
        "parse_mode": ParseMode.HTML,
        "reply_markup": _qx112_student_menu_kb(),
        "disable_web_page_preview": True,
    }
    if ok_count and first_id:
        kwargs["reply_to_message_id"] = int(first_id)
    with _cx114.suppress(Exception):
        await context.bot.send_message(**kwargs)
    raise ApplicationHandlerStop


globals()["qx112_on_callback"] = qx112_on_callback


# ─────────────────────────────────────────────────────────────────────────────
# 7) Remember which bot each user is talking to (for the CSV tag)
# ─────────────────────────────────────────────────────────────────────────────
async def qx114_note_bot(update, context):
    with _cx114.suppress(Exception):
        uid = int(_qx95_scope_uid(update, context) or 0)
        if uid:
            _QX114_BOTNAME[uid] = str(
                getattr(context.bot, "first_name", "") or getattr(context.bot, "username", "") or "Qubix"
            )


_qx114_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx114_prev_build_app() if callable(_qx114_prev_build_app) else None
    if app is None:
        return app
    with _cx114.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx112_on_callback, pattern=r"^qx112:"), group=-30003
        )
    with _cx114.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx114_note_bot), group=-30004)
    with _cx114.suppress(Exception):
        app.add_handler(CallbackQueryHandler(qx114_note_bot), group=-30004)
    _qx_log.info("[QUBIX-114] student polish wired.")
    return app


_qx_log.info("[SECTION 114] Qubix student polish loaded.")
