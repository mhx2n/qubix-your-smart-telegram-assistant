# ──────────────────────────────────────────────────────────────────────────────
# Section: 101_qubix_score_group_intro_08_04
# Purpose:
#   1. /score (+ scoreon/scoreoff aliases) now works inside a user's inbox and
#      inside their own bot — no staff-only gate, single clean card, no dupes.
#   2. Group add-notice no longer advertises group AI (/pro, .sh). Instead it
#      explains, step by step, how to pull the group / topic info that the
#      workspace needs.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx101

from telegram import InlineKeyboardButton as _IKB101, InlineKeyboardMarkup as _IKM101
from telegram.constants import ParseMode as _PM101
from telegram.ext import (
    ApplicationHandlerStop as _AHS101,
    CallbackQueryHandler as _CQH101,
    CommandHandler as _CH101,
)


def _qx101_log(msg):
    with _cx101.suppress(Exception):
        logger.info("[QX101] %s", msg)


# ═════════════════════════════════════════════════════════════════════════════
# 1) Score reply toggle for every workspace user
# ═════════════════════════════════════════════════════════════════════════════
def _qx101_uid(update) -> int:
    uid = 0
    with _cx101.suppress(Exception):
        uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    return uid


def _qx101_allowed(uid: int) -> bool:
    checker = globals().get("_qx99_may_run")
    if callable(checker):
        with _cx101.suppress(Exception):
            return bool(checker(uid))
    with _cx101.suppress(Exception):
        return bool(int(uid) in set(globals().get("OWNER_IDS_SET") or ()))
    return False


def _qx101_ensure_user(uid: int) -> None:
    for name in ("ensure_user", "_ensure_user", "ensure_user_row", "upsert_user"):
        fn = globals().get(name)
        if callable(fn):
            with _cx101.suppress(Exception):
                fn(uid)
                return
    with _cx101.suppress(Exception):
        conn = db_connect()
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (int(uid),))
        conn.commit()
        conn.close()


def _qx101_state(uid: int) -> bool:
    getter = globals().get("_score_reply_enabled")
    if callable(getter):
        with _cx101.suppress(Exception):
            return bool(getter(uid))
    return True


def _qx101_apply(uid: int, value: bool) -> bool:
    _qx101_ensure_user(uid)
    setter = globals().get("_set_score_reply")
    if callable(setter):
        with _cx101.suppress(Exception):
            setter(uid, bool(value))
    return _qx101_state(uid)


def _qx101_card(active: bool) -> str:
    badge = "🟢 চালু" if active else "🔴 বন্ধ"
    detail = (
        "প্রতিটি প্রকাশ শেষে প্রথম quiz-কে reply করে score কার্ড পাঠানো হবে "
        "(channel এবং topic — দুই জায়গাতেই)।"
        if active else
        "প্রকাশ শেষে আর কোনো score কার্ড পাঠানো হবে না — শুধু quiz-গুলোই যাবে।"
    )
    return (
        "🏆 <b>Score Reply</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"অবস্থা: <b>{badge}</b>\n\n"
        f"{detail}\n\n"
        "নিচের বাটন দিয়ে যেকোনো সময় বদলাতে পারবেন।"
    )


def _qx101_kb(active: bool) -> _IKM101:
    rows = [[
        _IKB101("🟢 চালু করুন" if not active else "✅ চালু আছে", callback_data="qx101:score:on"),
        _IKB101("🔴 বন্ধ করুন" if active else "✅ বন্ধ আছে", callback_data="qx101:score:off"),
    ], [
        _IKB101("🔄 রিফ্রেশ", callback_data="qx101:score:rf"),
        _IKB101("✖️ বন্ধ", callback_data="qx101:score:cl"),
    ]]
    return _IKM101(rows)


async def _qx101_show(update, context, active: bool):
    clean = globals().get("_qx94_clean_send")
    text = _qx101_card(active)
    kb = _qx101_kb(active)
    if callable(clean):
        with _cx101.suppress(Exception):
            return await clean(update, context, text, kb)
    message = getattr(update, "effective_message", None)
    if message is None:
        return None
    with _cx101.suppress(Exception):
        return await message.reply_text(
            text, parse_mode=_PM101.HTML, reply_markup=kb,
            disable_web_page_preview=True,
        )
    return None


async def qx101_cmd_score(update, context):
    message = getattr(update, "effective_message", None)
    chat = getattr(update, "effective_chat", None)
    uid = _qx101_uid(update)
    if message is None or chat is None or getattr(chat, "type", "") != "private":
        raise _AHS101
    if not _qx101_allowed(uid):
        raise _AHS101

    raw = (getattr(message, "text", "") or "").strip()
    word = raw.split()[0].lstrip("/.").split("@")[0].lower() if raw else ""
    args = [a.lower() for a in raw.split()[1:]]

    if word in ("scoreon", "scon") or (args and args[0] in ("on", "চালু", "1", "yes")):
        active = _qx101_apply(uid, True)
    elif word in ("scoreoff", "scoff") or (args and args[0] in ("off", "বন্ধ", "0", "no")):
        active = _qx101_apply(uid, False)
    elif word == "score" and not args:
        active = _qx101_state(uid)
    else:
        active = _qx101_state(uid)

    await _qx101_show(update, context, active)
    raise _AHS101


async def qx101_cb_score(update, context):
    query = getattr(update, "callback_query", None)
    if query is None:
        raise _AHS101
    uid = 0
    with _cx101.suppress(Exception):
        uid = int(query.from_user.id)
    if not _qx101_allowed(uid):
        with _cx101.suppress(Exception):
            await query.answer("এই সুবিধাটি আপনার জন্য এখন সক্রিয় নয়।", show_alert=True)
        raise _AHS101

    action = (query.data or "").split(":")[-1]
    if action == "cl":
        with _cx101.suppress(Exception):
            await query.answer("বন্ধ করা হলো")
        with _cx101.suppress(Exception):
            await query.message.delete()
        raise _AHS101

    if action == "on":
        active = _qx101_apply(uid, True)
        note = "Score reply চালু"
    elif action == "off":
        active = _qx101_apply(uid, False)
        note = "Score reply বন্ধ"
    else:
        active = _qx101_state(uid)
        note = "রিফ্রেশ হলো"

    with _cx101.suppress(Exception):
        await query.answer(note)
    with _cx101.suppress(Exception):
        await query.edit_message_text(
            _qx101_card(active), parse_mode=_PM101.HTML,
            reply_markup=_qx101_kb(active), disable_web_page_preview=True,
        )
    raise _AHS101


# ═════════════════════════════════════════════════════════════════════════════
# 2) Group add-notice → how to pull group / topic info
# ═════════════════════════════════════════════════════════════════════════════
QX101_GROUP_INTRO = (
    "✅ <b>{brand} সংযুক্ত হয়েছে</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "এই গ্রুপে কুইজ পাঠাতে শুধু group/topic-এর <b>info</b> লাগবে। "
    "খুব সহজে বের করতে পারবেন:\n\n"
    "<b>১.</b> এই গ্রুপে (Topic থাকলে ঠিক ঐ Topic-এর ভিতরে) "
    "<code>/info</code> লিখুন।\n"
    "<b>২.</b> বট সাথে সাথে <b>Chat ID</b> ও <b>Topic ID</b> দেখাবে — "
    "সাথে কপি করার মতো কমান্ডও দেবে।\n"
    "<b>৩.</b> ঐ কমান্ডটি নিজের বট-ইনবক্সে পাঠিয়ে group/topic সেভ করুন "
    "(<code>/adg</code> → group, <code>/adtc</code> → topic)।\n"
    "<b>৪.</b> এরপর ইনবক্স থেকেই <code>/pt</code> দিয়ে ঐ topic-এ প্রকাশ করুন।\n\n"
    "💡 <i>বিকল্প:</i> topic-এর যেকোনো message-এর link কপি করে ইনবক্সে "
    "<code>/linktopic &lt;link&gt;</code> দিলেই topic সেভ হয়ে যাবে।"
)

QX101_GROUP_ALERT = (
    "এই গ্রুপে /info লিখুন → Chat ID ও Topic ID পাবেন। "
    "সেটি বট-ইনবক্সে /adg ও /adtc দিয়ে সেভ করে /pt দিয়ে প্রকাশ করুন।"
)


async def on_my_chat_member(update, context):  # noqa: F811
    cmu = getattr(update, "my_chat_member", None)
    if not cmu:
        return
    try:
        old_status = cmu.old_chat_member.status
        new_status = cmu.new_chat_member.status
        chat = cmu.chat
    except Exception:
        return

    if new_status not in ("member", "administrator"):
        return
    if old_status not in ("left", "kicked"):
        return
    if getattr(chat, "type", "") not in ("group", "supergroup"):
        return

    brand = str(globals().get("BOT_BRAND") or "Qubix")
    kb = _IKM101([[_IKB101("ℹ️ কীভাবে info নেব", callback_data="qx101:ginfo")]])
    with _cx101.suppress(Exception):
        await context.bot.send_message(
            chat_id=chat.id,
            text=QX101_GROUP_INTRO.format(brand=brand),
            parse_mode=_PM101.HTML,
            reply_markup=kb,
            disable_web_page_preview=True,
        )


async def qx101_cb_ginfo(update, context):
    query = getattr(update, "callback_query", None)
    if query is None:
        raise _AHS101
    with _cx101.suppress(Exception):
        await query.answer(QX101_GROUP_ALERT[:190], show_alert=True, cache_time=0)
    raise _AHS101


# ═════════════════════════════════════════════════════════════════════════════
# 3) /info usable by every workspace user, and allowed by the group guard
# ═════════════════════════════════════════════════════════════════════════════
_qx101_prev_info = globals().get("_cmd_info_m")


async def _cmd_info_m(update, context):  # noqa: F811
    uid = _qx101_uid(update)
    if not _qx101_allowed(uid):
        raise _AHS101
    marker = globals().get("_QX_ACTING_OWNER")
    token = None
    if marker is not None:
        with _cx101.suppress(Exception):
            token = marker.set(True)
    try:
        if callable(_qx101_prev_info):
            return await _qx101_prev_info(update, context)
    finally:
        if token is not None and marker is not None:
            with _cx101.suppress(Exception):
                marker.reset(token)


_qx101_prev_guard = globals().get("group_command_guard")


async def group_command_guard(update, context):  # noqa: F811
    message = getattr(update, "message", None)
    chat = getattr(update, "effective_chat", None)
    if not message or not chat or getattr(chat, "type", "") not in ("group", "supergroup"):
        return
    extractor = globals().get("_extract_command_name")
    cmd = ""
    if callable(extractor):
        with _cx101.suppress(Exception):
            cmd = extractor(message.text or "") or ""
    if cmd in ("info", "start", "help"):
        return
    if callable(_qx101_prev_guard):
        result = _qx101_prev_guard(update, context)
        if hasattr(result, "__await__"):
            return await result
        return result


# ═════════════════════════════════════════════════════════════════════════════
# 4) Wiring
# ═════════════════════════════════════════════════════════════════════════════
_qx101_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx101_prev_build_app() if callable(_qx101_prev_build_app) else None
    if app is None:
        return app

    register = globals().get("_register_dual_command")
    for name in ("score", "scoreon", "scon", "scoreoff", "scoff"):
        with _cx101.suppress(Exception):
            if callable(register):
                register(app, name, qx101_cmd_score, group=-1200)
            else:
                app.add_handler(_CH101(name, qx101_cmd_score), group=-1200)

    with _cx101.suppress(Exception):
        app.add_handler(
            _CQH101(qx101_cb_score, pattern=r"^qx101:score:"), group=-1200
        )
    with _cx101.suppress(Exception):
        app.add_handler(
            _CQH101(qx101_cb_ginfo, pattern=r"^qx101:ginfo$"), group=-1200
        )
    return app


_qx101_log("score toggle opened to workspace users; group intro now explains /info flow")
