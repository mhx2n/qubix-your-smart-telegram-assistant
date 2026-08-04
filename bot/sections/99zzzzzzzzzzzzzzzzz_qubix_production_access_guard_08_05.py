# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 115 — QUBIX PRODUCTION ACCESS GUARD (2026-08-05)
#
# Final authority for access expiry and Student help/UI isolation.
# Loaded after every earlier compatibility layer.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx115


QX115_ROW = "<code>─────────────────────────</code>"
QX115_STUDENT_HELP_CARD = (
    "💬 <b>Qubix সহায়তা</b>\n"
    f"{QX115_ROW}\n"
    "আপনার প্রশ্নটি <code>.help</code>-এর পরে লিখুন।\n\n"
    "<code>.help ছবি থেকে quiz কীভাবে তৈরি করব?</code>\n"
    "<code>.help quiz গুলো inbox-এ কীভাবে পাঠাব?</code>\n"
    "<code>.help CSV file কীভাবে নেব?</code>\n\n"
    "Student workspace-এর generation, inbox practice, buffer ও CSV export "
    "সম্পর্কিত সহায়তা এখানে পাওয়া যাবে।"
)
QX112_STUDENT_COMMANDS_CARD = (
    "📜 <b>Student Commands</b>\n"
    f"{QX115_ROW}\n"
    "<b>Quiz তৈরি</b>\n"
    "ছবি, টেক্সট বা quiz/poll-এ reply করে:\n"
    "<code>.gen 15</code> · <code>.gen medical 15</code>\n"
    "<code>.gen engineering 15</code> · <code>.gen versity 15</code>\n\n"
    "<b>Buffer ও Export</b>\n"
    "<code>/buffer</code> — জমা quiz দেখুন\n"
    "<code>/bc</code> — quiz সংখ্যা দেখুন\n"
    "<code>.done</code> — CSV file নিন\n"
    "<code>.clear</code> — buffer খালি করুন\n\n"
    "<b>Inbox Practice</b>\n"
    "📥 <b>Send to Inbox</b> — quiz গুলো inbox-এ পাঠান\n\n"
    "<b>সহায়তা ও Access</b>\n"
    "<code>/help আপনার প্রশ্ন</code> — ব্যবহারবিষয়ক সহায়তা\n"
    "<code>/switchaccess</code> — Master Access-এর তথ্য\n"
    "<code>/myid</code> — আপনার User ID\n"
    f"{QX115_ROW}\n"
    "🔐 Student workspace শুধু আপনার ব্যক্তিগত inbox-এ কাজ করে।"
)
globals()["QX112_STUDENT_COMMANDS_CARD"] = QX112_STUDENT_COMMANDS_CARD


def _qx115_uid(update, context) -> int:
    with _cx115.suppress(Exception):
        return int(_qx95_scope_uid(update, context) or 0)
    with _cx115.suppress(Exception):
        return int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    return 0


def _qx115_owner(update, context) -> bool:
    with _cx115.suppress(Exception):
        return bool(_qx93_privileged(update)) and not bool(_qx95_is_tenant(context))
    return False


def _qx115_student(uid: int) -> bool:
    with _cx115.suppress(Exception):
        return str(_qx112_tier(int(uid)) or "") == "student"
    return False


def _qx115_question(update) -> str:
    text = str(getattr(getattr(update, "effective_message", None), "text", "") or "").strip()
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


def _qx115_student_prompt(question: str) -> str:
    return (
        "You are Qubix Help for the Student workspace. Answer only about the "
        "Student user's private-inbox workflow. Available features: generate "
        "quizzes by replying to a photo, text, or quiz/poll with .gen <count>, "
        ".gen medical <count>, .gen engineering <count>, or .gen versity "
        "<count>; inspect the buffer with /buffer or /bc; clear it with .clear; "
        "send generated quizzes to the private inbox with the Send to Inbox "
        "button; export CSV with .done or Export CSV. Explanations are enabled "
        "automatically. Never mention channels, groups, topics, posting, bots, "
        "tokens, owner tools, unavailable commands, models, prompts, or internal "
        "systems. If asked about something outside Student Access, politely say "
        "that this help desk covers Student practice features and direct them to "
        "/switchaccess for Master Access information. Reply in the user's language, "
        "professional and practical, Telegram HTML only (<b>, <i>, <code>), no "
        "greeting or disclaimer, maximum 10 lines.\n\n"
        f"User question: {question}"
    )


async def _qx115_send_expired(update, context, uid: int) -> None:
    name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")
    text = _qx_expired_card(int(uid), name)
    query = getattr(update, "callback_query", None)
    if query is not None:
        with _cx115.suppress(Exception):
            await query.answer("আপনার access-এর মেয়াদ শেষ হয়েছে।", show_alert=True)
        with _cx115.suppress(Exception):
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        return
    message = getattr(update, "effective_message", None)
    if message is not None:
        with _cx115.suppress(Exception):
            await message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )


async def qx115_access_gate(update, context):
    """Stop every expired command/callback before any legacy handler can run."""
    if _qx115_owner(update, context):
        return
    uid = _qx115_uid(update, context)
    if not uid:
        return
    state = {}
    with _cx115.suppress(Exception):
        state = _qx_access(uid) or {}
    if state.get("ok"):
        return

    query = getattr(update, "callback_query", None)
    message = getattr(update, "effective_message", None)
    text = str(getattr(message, "text", "") or "")
    if query is None and text[:1] not in ("/", "."):
        return
    await _qx115_send_expired(update, context, uid)
    raise ApplicationHandlerStop


async def qx115_student_help(update, context):
    uid = _qx115_uid(update, context)
    if not uid or not _qx115_student(uid):
        return
    state = {}
    with _cx115.suppress(Exception):
        state = _qx_access(uid) or {}
    if not state.get("ok"):
        return  # qx115_access_gate owns the expired response

    question = _qx115_question(update)
    if not question:
        await _qx112_send(update, context, QX115_STUDENT_HELP_CARD, _qx112_back_kb())
        raise ApplicationHandlerStop

    pending = None
    with _cx115.suppress(Exception):
        pending = await update.effective_message.reply_text(
            "💬 <b>Qubix সহায়তা</b>\n" + QX115_ROW + "\nউত্তর প্রস্তুত করা হচ্ছে…",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    answer = ""
    router = globals().get("_gemini_text_router")
    if callable(router):
        loop = asyncio.get_running_loop()
        prompt = _qx115_student_prompt(question)
        with _cx115.suppress(Exception):
            answer = await asyncio.wait_for(
                loop.run_in_executor(_QX113_POOL, _qx113_router_call, prompt, 14),
                timeout=17.0,
            )
    if not answer:
        answer = (
            "এই মুহূর্তে উত্তর দেওয়া যাচ্ছে না। কিছুক্ষণ পর আবার চেষ্টা করুন।\n\n"
            "Quiz তৈরি করতে একটি ছবি, টেক্সট বা poll-এ reply করে "
            "<code>.gen 15</code> লিখুন।"
        )
    with _cx115.suppress(Exception):
        answer = _qx92_sanitize_html(str(answer)) or str(answer)
    body = "💬 <b>Qubix সহায়তা</b>\n" + QX115_ROW + "\n" + str(answer)[:3500]
    if pending is not None:
        try:
            await pending.edit_text(
                body,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx112_back_kb(),
                disable_web_page_preview=True,
            )
        except Exception:
            with _cx115.suppress(Exception):
                await pending.edit_text(
                    re.sub(r"<[^>]+>", "", body),
                    reply_markup=_qx112_back_kb(),
                    disable_web_page_preview=True,
                )
    else:
        await _qx112_send(update, context, body, _qx112_back_kb())
    raise ApplicationHandlerStop


async def qx115_student_ask_callback(update, context):
    query = getattr(update, "callback_query", None)
    if query is None or str(getattr(query, "data", "") or "") != "qx93:ask":
        return
    uid = _qx115_uid(update, context)
    if not uid or not _qx115_student(uid):
        return
    with _cx115.suppress(Exception):
        await query.answer()
    with _cx115.suppress(Exception):
        await query.edit_message_text(
            QX115_STUDENT_HELP_CARD,
            parse_mode=ParseMode.HTML,
            reply_markup=_qx112_back_kb(),
            disable_web_page_preview=True,
        )
    raise ApplicationHandlerStop


# Remove the casual trial sentence while preserving the useful plan comparison.
_qx115_previous_welcome = globals().get("_qx112_welcome_text")


def _qx112_welcome_text(name: str, st) -> str:  # noqa: F811
    text = _qx115_previous_welcome(name, st) if callable(_qx115_previous_welcome) else ""
    text = str(text or "")
    text = re.sub(
        r"<b>Qubix</b>-এ দুই ধরনের premium workspace আছে।.*?ব্যবহার করে "
        r"দেখতে পারবেন।\s*",
        "",
        text,
        count=1,
        flags=re.S,
    )
    return text


globals()["_qx112_welcome_text"] = _qx112_welcome_text


# Section 114's scrubber is called dynamically by its installed Bot wrappers.
# Make it complete, case-insensitive, and safe even when the whole card is blocked.
_QX115_MASTER_MARKERS = (
    "channel directory", "your channels", "channels", "/addchannel",
    "/listchannels", "/removechannel", "channel#", ".post", ".sp ", ".sx ",
    "topics", "groups", ".pt ", ".adg", ".adtc", ".listgroups",
    ".listtopics", ".topic", ".aitopic", ".topicpin", ".usetopic",
    "personal bot", "/addbot", "bot token",
)


def _qx114_scrub(text: str) -> str:  # noqa: F811
    body = str(text or "")
    if not body:
        return body
    kept = []
    removed = False
    for line in body.split("\n"):
        low = line.lower()
        if any(marker in low for marker in _QX115_MASTER_MARKERS):
            removed = True
            continue
        kept.append(line)
    if not removed:
        return body
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return cleaned or (
        "🎓 <b>Student workspace</b>\n" + QX115_ROW +
        "\nএই অংশটি Master Access-এর জন্য সংরক্ষিত।\n"
        "Student commands দেখতে <code>/commands</code> দিন।"
    )


globals()["_qx114_scrub"] = _qx114_scrub
with _cx115.suppress(Exception):
    _QX114_TIER_CACHE.clear()  # prevent stale Master state after plan switching


def _qx114_tier(uid) -> str:  # noqa: F811
    """Always resolve the current plan; plan switches must take effect instantly."""
    with _cx115.suppress(Exception):
        return str(_qx112_tier(int(uid or 0)) or "")
    return ""


globals()["_qx114_tier"] = _qx114_tier


_qx115_previous_student_kb = globals().get("_qx112_student_menu_kb")


def _qx112_student_menu_kb():  # noqa: F811
    kb = _qx115_previous_student_kb() if callable(_qx115_previous_student_kb) else None
    rows = [list(row) for row in (getattr(kb, "inline_keyboard", []) or [])]
    for row_index, row in enumerate(rows):
        for button_index, button in enumerate(row):
            if str(getattr(button, "callback_data", "") or "") == "qx93:ask":
                rows[row_index][button_index] = InlineKeyboardButton(
                    "💬 সহায়তা", callback_data="qx93:ask"
                )
    return InlineKeyboardMarkup(rows) if rows else kb


globals()["_qx112_student_menu_kb"] = _qx112_student_menu_kb


_qx115_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx115_prev_build_app() if callable(_qx115_prev_build_app) else None
    if app is None:
        return app

    with _cx115.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx115_access_gate), group=-40000)
    with _cx115.suppress(Exception):
        app.add_handler(CallbackQueryHandler(qx115_access_gate), group=-40000)
    with _cx115.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx115_student_ask_callback, pattern=r"^qx93:ask$"),
            group=-39999,
        )

    register = globals().get("_register_dual_command")
    for command in ("help", "ask", "ai"):
        with _cx115.suppress(Exception):
            if callable(register):
                register(app, command, qx115_student_help, group=-39999)
            else:
                app.add_handler(CommandHandler(command, qx115_student_help), group=-39999)

    _qx_log.info("[QUBIX-115] production access guard + isolated Student help wired.")
    return app


_qx_log.info("[SECTION 115] Qubix production access guard loaded.")