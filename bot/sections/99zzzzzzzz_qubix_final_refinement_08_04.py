# ──────────────────────────────────────────────────────────────────────────────
# Section 106 — final publishing, math generation and named-export refinement.
# Loaded last by bot/__main__.py; do not import directly.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a106
import contextlib as _cx106
import html as _h106
import os as _os106
import re as _re106
import tempfile as _tmp106
import time as _t106

from telegram import BotCommand as _BotCommand106
from telegram.constants import ParseMode as _PM106
from telegram.ext import ApplicationHandlerStop as _AHS106, MessageHandler as _MH106


def _qx106_log(message, level="info"):
    with _cx106.suppress(Exception):
        getattr(logger, level)("[QX106] %s", message)


def _qx106_allowed(uid):
    checker = globals().get("_qx99_may_run")
    if callable(checker):
        with _cx106.suppress(Exception):
            return bool(checker(int(uid)))
    with _cx106.suppress(Exception):
        return bool(is_owner(int(uid)))
    return False


# ═════════════════════════════════════════════════════════════════════════════
# 1) Math sources: bypass prose/script rejection, never mathematical validity.
# ═════════════════════════════════════════════════════════════════════════════
_QX106_MATH = _re106.compile(
    r"\\(?:frac|sqrt|int|sum|prod|lim|sin|cos|tan|log|ln)\b|"
    r"[√∫∑∏πθ∞±≤≥≠×÷∂]|\b(?:integral|derivative|matrix|equation)\b|"
    r"[A-Za-z0-9}\)]\s*\^\s*[{(A-Za-z0-9-]",
    _re106.I,
)


def _qx106_math_source(ctx):
    if isinstance(ctx, dict):
        return str(ctx.get("clean_text") or ctx.get("raw_markdown") or "")
    return str(ctx or "")


def _qx106_answer(value, options):
    with _cx106.suppress(Exception):
        number = int(value)
        if 1 <= number <= len(options):
            return number
        if 0 <= number < len(options):
            return number + 1
    text = str(value or "").strip().lower()
    match = _re106.search(r"\b([a-e])\b", text)
    if match:
        number = ord(match.group(1)) - 96
        if number <= len(options):
            return number
    for index, option in enumerate(options, 1):
        if text and text == str(option).strip().lower():
            return index
    return 1


def _qx106_math_normalise(item):
    if not isinstance(item, dict):
        return None
    question = str(item.get("question") or item.get("questions") or item.get("q") or "").strip()
    raw = item.get("options") or item.get("choices") or []
    if isinstance(raw, dict):
        raw = [raw[key] for key in sorted(raw)]
    options = [str(value or "").strip() for value in raw if str(value or "").strip()] if isinstance(raw, list) else []
    if len(options) < 2:
        options = [str(item.get(f"option{i}") or "").strip() for i in range(1, 6)]
        options = [value for value in options if value]
    options = options[:5]
    if len(question) < 2 or len(options) < 2:
        return None
    answer_value = next((item.get(key) for key in (
        "answer", "correct", "correct_answer", "correctOption", "correct_option"
    ) if item.get(key) is not None), 1)
    return {
        "question": question,
        "options": options,
        "answer": _qx106_answer(answer_value, options),
        "explanation": str(item.get("explanation") or item.get("solution") or item.get("reason") or "")[:500],
    }


_qx106_previous_generate = globals().get("_generate_quizzes_from_ocr_sync")


def _generate_quizzes_from_ocr_sync(ocr_ctx, desired, user_id):  # noqa: F811
    source = _qx106_math_source(ocr_ctx).strip()
    if not _QX106_MATH.search(source):
        return _qx106_previous_generate(ocr_ctx, desired, user_id)
    desired = max(1, min(int(desired or 1), 200))
    result = []
    with _cx106.suppress(Exception):
        result = _qx106_previous_generate(ocr_ctx, desired, user_id) or []
    if result:
        return result

    batcher = globals().get("_generate_batch_fast_74")
    if not callable(batcher):
        return []
    old_normalise = globals().get("_normalise_mcq_74")
    globals()["_normalise_mcq_74"] = _qx106_math_normalise
    seen = set()
    try:
        rounds = max(2, min(16, (desired + 5) // 6 + 1))
        for _ in range(rounds):
            if len(result) >= desired:
                break
            need = min(6, desired - len(result))
            instruction = (
                "The source is mathematical. Preserve every operator, exponent, radical, "
                "fraction, bracket and variable exactly. Formula-only stems/options are valid. "
                "Recalculate each answer before returning it."
            )
            rows = batcher(source, need, avoid_text=instruction) or []
            for row in rows:
                clean = _qx106_math_normalise(row)
                if not clean:
                    continue
                key = _re106.sub(r"\W+", "", clean["question"].lower())
                if key and key not in seen:
                    seen.add(key)
                    result.append(clean)
        _qx106_log(f"math fallback produced {len(result)} item(s)")
        return result[:desired]
    finally:
        if old_normalise is not None:
            globals()["_normalise_mcq_74"] = old_normalise


if callable(_qx106_previous_generate):
    globals()["_generate_quizzes_from_ocr_sync"] = _generate_quizzes_from_ocr_sync


# ═════════════════════════════════════════════════════════════════════════════
# 2) Reliable manual anchors (text, photo+caption and captionless photo).
# ═════════════════════════════════════════════════════════════════════════════
def _qx106_anchor_snapshot(bot, anchor_chat, anchor_msg, sent_message):
    cache_get = globals().get("_qx103_cache_get")
    cached = cache_get(anchor_chat, anchor_msg) if callable(cache_get) else {}
    if cached and str(cached.get("text") or "").strip():
        text = str(cached.get("text") or "")
        if cached.get("markdown"):
            return {}  # AI topic cards stay untouched.
        return {"html": text, "photo": bool(cached.get("photo"))}

    row_get = globals().get("_qx102_anchor_row")
    if callable(row_get):
        with _cx106.suppress(Exception):
            _uid, stored, photo = row_get(anchor_chat, anchor_msg)
            if str(stored or "").strip():
                return {"html": str(stored), "photo": bool(photo)}

    reply = getattr(sent_message, "reply_to_message", None)
    if reply is not None:
        photo = bool(getattr(reply, "photo", None))
        rich = getattr(reply, "caption_html_urled", "") if photo else getattr(reply, "text_html_urled", "")
        plain = getattr(reply, "caption", "") if photo else getattr(reply, "text", "")
        if rich or plain:
            return {"html": str(rich or _h106.escape(str(plain))), "photo": photo}

    # Telegram permits adding a caption to a bot-owned captionless photo.
    return {"html": "<b>Quiz Topic</b>", "photo": True} if cached and cached.get("photo") else {}


def _qx104_exact_dup(_chat_id, _text):  # noqa: F811
    """Never suppress at transport level; publishing functions own deduplication."""
    return False


globals()["_qx104_exact_dup"] = _qx104_exact_dup
with _cx106.suppress(Exception):
    _QX104_EXACT.clear()


def _qx104_track(bot, kwargs, message):  # noqa: F811
    anchor_msg = kwargs.get("reply_to_message_id")
    anchor_chat = kwargs.get("chat_id")
    params = kwargs.get("reply_parameters")
    if params is not None:
        if isinstance(params, dict):
            anchor_msg = params.get("message_id") or anchor_msg
            anchor_chat = params.get("chat_id") or anchor_chat
        else:
            anchor_msg = getattr(params, "message_id", None) or anchor_msg
            anchor_chat = getattr(params, "chat_id", None) or anchor_chat
    reply = getattr(message, "reply_to_message", None)
    if reply is not None:
        anchor_msg = anchor_msg or getattr(reply, "message_id", None)
        anchor_chat = anchor_chat if anchor_chat is not None else getattr(getattr(reply, "chat", None), "id", None)
    if not anchor_msg or anchor_chat is None:
        return
    linker = globals().get("_qx102_link")
    link = str(linker(message) or "") if callable(linker) else ""
    if not link:
        return
    key = (str(getattr(bot, "token", ""))[:16], str(anchor_chat), int(anchor_msg))
    sessions = globals().get("_QX104_SESSIONS")
    if not isinstance(sessions, dict):
        return
    session = sessions.get(key)
    if session is None:
        session = {
            "bot": bot, "link": link, "anchor_chat": anchor_chat,
            "anchor_msg": int(anchor_msg), "count": 0, "ts": _t106.time(),
            "snapshot": _qx106_anchor_snapshot(bot, anchor_chat, int(anchor_msg), message),
        }
        sessions[key] = session
        settle = globals().get("_qx104_settle")
        if callable(settle):
            with _cx106.suppress(RuntimeError):
                _a106.get_running_loop().create_task(settle(key))
    session["count"] = int(session.get("count") or 0) + 1
    session["ts"] = _t106.time()


globals()["_qx102_track"] = _qx104_track
globals()["_qx104_track"] = _qx104_track


# ═════════════════════════════════════════════════════════════════════════════
# 3) Per-channel rich score templates and guaranteed one-card delivery.
# ═════════════════════════════════════════════════════════════════════════════
with _cx106.suppress(Exception):
    _conn106 = db_connect()
    try:
        _columns106 = {str(row[1]) for row in _conn106.execute("PRAGMA table_info(channels)").fetchall()}
        if "score_template" not in _columns106:
            _conn106.execute("ALTER TABLE channels ADD COLUMN score_template TEXT NOT NULL DEFAULT ''")
        _conn106.commit()
    finally:
        _conn106.close()


def _qx106_channel_for(uid, selector):
    with _cx106.suppress(Exception):
        return channel_get_by_id_for_user(int(uid), int(selector))
    return None


def _qx106_score_template(uid, chat_id):
    with _cx106.suppress(Exception):
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT score_template, title FROM channels WHERE channel_chat_id=? AND added_by=? ORDER BY id DESC LIMIT 1",
                (int(chat_id), int(uid)),
            ).fetchone()
            if row:
                return str(row[0] or ""), str(row[1] or "")
        finally:
            conn.close()
    return "", ""


def _qx106_render_score(template, count, channel_title=""):
    default = "🏆 <b>আপনার স্কোর দেখুন</b>\nএই কুইজ সেটে মোট <b>{count}</b>টি প্রশ্ন রয়েছে।"
    body = str(template or default)
    return body.replace("{count}", str(int(count))).replace("{channel}", _h106.escape(channel_title))[:3900]


async def _send_score_msg(context, admin_id, chat_id, ok_count, first_post_msg_id, thread_id=None):  # noqa: F811
    if not _score_reply_enabled(admin_id):
        return
    template, title = _qx106_score_template(admin_id, chat_id)
    text = _qx106_render_score(template, ok_count, title)
    kwargs = {
        "chat_id": chat_id, "text": text, "parse_mode": _PM106.HTML,
        "allow_sending_without_reply": True,
    }
    if first_post_msg_id:
        kwargs["reply_to_message_id"] = first_post_msg_id
    if thread_id is not None:
        kwargs["message_thread_id"] = thread_id
    try:
        await context.bot.send_message(**kwargs)
    except Exception as exc:
        kwargs.pop("parse_mode", None)
        kwargs["text"] = _re106.sub(r"<[^>]+>", "", text)
        with _cx106.suppress(Exception):
            await context.bot.send_message(**kwargs)
        _qx106_log(f"rich score fallback: {exc}", "warning")


globals()["_send_score_msg"] = _send_score_msg


async def qx106_cmd_scoreformat(update, context):
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None or not _qx106_allowed(user.id):
        raise _AHS106
    args = list(getattr(context, "args", None) or [])
    if not args:
        await message.reply_text(
            "🎨 <b>Channel Score Format</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "একটি rich formatted message-এ reply করে দিন:\n"
            "<code>/scoreformat &lt;channel#&gt;</code>\n\n"
            "Placeholder: <code>{count}</code> · <code>{channel}</code>\n"
            "Default ফেরাতে: <code>/scoreformat &lt;channel#&gt; reset</code>",
            parse_mode=_PM106.HTML,
        )
        raise _AHS106
    channel = _qx106_channel_for(user.id, args[0])
    if channel is None:
        await message.reply_text("⚠️ Channel পাওয়া যায়নি। /listchannels থেকে channel# নিন।")
        raise _AHS106
    reset = len(args) > 1 and str(args[1]).lower() in ("reset", "default", "off")
    reply = getattr(message, "reply_to_message", None)
    rich = ""
    if reply is not None:
        rich = str(getattr(reply, "text_html_urled", "") or getattr(reply, "caption_html_urled", "") or "")
        if not rich:
            rich = _h106.escape(str(getattr(reply, "text", "") or getattr(reply, "caption", "") or ""))
    if not reset and not rich.strip():
        await message.reply_text("⚠️ আগে score message-টিতে reply করে command দিন।")
        raise _AHS106
    with _cx106.suppress(Exception):
        conn = db_connect()
        conn.execute("UPDATE channels SET score_template=? WHERE id=?", ("" if reset else rich[:3900], int(channel.id)))
        conn.commit()
        conn.close()
    preview = _qx106_render_score("" if reset else rich, 15, channel.title)
    await message.reply_text(
        "✅ <b>Score format saved</b>\n━━━━━━━━━━━━━━━━━━━━\n" + preview,
        parse_mode=_PM106.HTML, disable_web_page_preview=True,
    )
    raise _AHS106


# ═════════════════════════════════════════════════════════════════════════════
# 4) .done/.d asks for a clean filename, then exports exactly one CSV.
# ═════════════════════════════════════════════════════════════════════════════
def _qx106_filename(value):
    name = _re106.sub(r"\.csv$", "", str(value or "").strip(), flags=_re106.I)
    name = _re106.sub(r"[^\w\- ()\[\].]+", "_", name, flags=_re106.UNICODE).strip(" ._")
    return (name[:80] or "qubix_export") + ".csv"


async def _qx106_export(context, chat_id, uid, filename):
    items = buffer_list(uid, limit=99999) or []
    if not items:
        return 0
    rows = _done_rows_62(items, uid, repair=True)
    columns = ["questions", "option1", "option2", "option3", "option4", "option5",
               "answer", "explanation", "type", "section"]
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    with _tmp106.NamedTemporaryFile("w+b", suffix=".csv", delete=False) as handle:
        path = handle.name
    try:
        frame[columns].to_csv(path, index=False, encoding="utf-8-sig")
        with open(path, "rb") as stream:
            await context.bot.send_document(
                chat_id=chat_id, document=stream, filename=_qx106_filename(filename),
                caption=f"📂 <b>CSV Export</b>\n{len(rows)} questions",
                parse_mode=_PM106.HTML,
            )
    finally:
        with _cx106.suppress(Exception):
            _os106.remove(path)
    return len(rows)


async def _cmd_done_impl_70(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        raise _AHS106
    if not (buffer_list(user.id, limit=1) or []):
        await message.reply_text("📭 Buffer empty — export করার মতো quiz নেই।")
        raise _AHS106
    old_prompt = context.user_data.pop("qx106_export_prompt", None)
    if old_prompt:
        with _cx106.suppress(Exception):
            await context.bot.delete_message(message.chat_id, int(old_prompt))
    with _cx106.suppress(Exception):
        await message.delete()
    prompt = await context.bot.send_message(
        chat_id=message.chat_id,
        text="📂 <b>CSV File Name</b>\n━━━━━━━━━━━━━━━━━━━━\nফাইলটির নাম লিখুন — <code>.csv</code> নিজে থেকে যোগ হবে।",
        parse_mode=_PM106.HTML,
    )
    context.user_data["qx106_export_prompt"] = int(prompt.message_id)
    context.user_data["qx106_export_wait"] = {"uid": int(user.id), "ts": _t106.time()}
    raise _AHS106


globals()["_cmd_done_impl_70"] = _cmd_done_impl_70
globals()["cmd_done"] = _cmd_done_impl_70


async def _qx106_filename_reply(update, context):
    pending = context.user_data.get("qx106_export_wait")
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if not pending or message is None or user is None:
        return
    if int(pending.get("uid") or 0) != int(user.id):
        return
    if _t106.time() - float(pending.get("ts") or 0) > 300:
        context.user_data.pop("qx106_export_wait", None)
        return
    name = str(getattr(message, "text", "") or "").strip()
    if not name or name.startswith(("/", ".")):
        return
    context.user_data.pop("qx106_export_wait", None)
    prompt_id = context.user_data.pop("qx106_export_prompt", None)
    with _cx106.suppress(Exception):
        await message.delete()
    if prompt_id:
        with _cx106.suppress(Exception):
            await context.bot.delete_message(message.chat_id, int(prompt_id))
    count = await _qx106_export(context, message.chat_id, user.id, name)
    if count:
        buffer_clear(user.id)
    raise _AHS106


# ═════════════════════════════════════════════════════════════════════════════
# 5) Wiring and command menus.
# ═════════════════════════════════════════════════════════════════════════════
for _menu_name106 in ("QX94_USER_MENU_COMMANDS", "QX94_OWNER_MENU_COMMANDS"):
    _menu106 = list(globals().get(_menu_name106) or [])
    if not any(name == "scoreformat" for name, _ in _menu106):
        _menu106.append(("scoreformat", "Channel score format সেট"))
    globals()[_menu_name106] = _menu106[:99]


def _qx94_bot_commands(owner):  # noqa: F811
    source = list(globals().get("QX94_OWNER_MENU_COMMANDS" if owner else "QX94_USER_MENU_COMMANDS") or [])
    tenant = False
    with _cx106.suppress(Exception):
        tenant = bool(globals().get("_QX97_TENANT").get())
    hidden = set(globals().get("QX97_TENANT_HIDDEN") or ()) if tenant else set()
    return [_BotCommand106(name, str(desc)[:256]) for name, desc in source if name not in hidden][:100]


globals()["_qx94_bot_commands"] = _qx94_bot_commands

_qx106_previous_build = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx106_previous_build() if callable(_qx106_previous_build) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    if callable(register):
        with _cx106.suppress(Exception):
            register(app, "done", _cmd_done_impl_70, filters.ChatType.PRIVATE, group=-4000)
            register(app, "d", _cmd_done_impl_70, filters.ChatType.PRIVATE, group=-4000)
            register(app, "scoreformat", qx106_cmd_scoreformat, filters.ChatType.PRIVATE, group=-4000)
    app.add_handler(
        _MH106(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, _qx106_filename_reply),
        group=-4100,
    )
    return app


_qx106_log("final refinement active: math fallback, manual anchors, score formats, named CSV")

# ===== END SECTION 106 =====