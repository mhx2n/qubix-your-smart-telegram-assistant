# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 92 — QUBIX RICH INBOX UI (2026-08-03)
#
#   1. Inbox-only: for non-owner users Qubix (and every personal bot) answers
#      ONLY in private chat. All group-side behaviour is switched off.
#   2. Trims the user command surface: logs/status/dashboard, buffercount,
#      stopquiz, resumequiz, clear, setprefix, setexplink, explain on/off,
#      exo/exf and score on/off are no longer part of the user workspace.
#   3. Rich-text workspace UI driven by responsive inline buttons.
#   4. `.help <question>` → AI answers about the user's own allowed features
#      in clean rich format (no owner infrastructure ever exposed).
# ══════════════════════════════════════════════════════════════════════════════

QX_WORKSPACE_COMMANDS = {
    "start", "help", "cmd", "commands", "guide", "menu", "myid", "id",
    "gen", "done", "buffer",
    "addchannel", "listchannels", "channels", "removechannel", "post",
    "adg", "addgroup", "listgroups", "groups",
    "adtc", "addtopic", "listtopics", "topics", "info", "pt",
    "topic", "aitopic", "mytopics", "usetopic", "cleartopic", "linktopic",
    "topicinfo", "topicpin", "topicunpin", "shuffle",
    "addbot", "mybot", "removebot", "delbot", "wake",
}
globals()["QX_WORKSPACE_COMMANDS"] = QX_WORKSPACE_COMMANDS

QX_WORKSPACE_CALLBACK_PREFIXES = (
    "g59:", "genq:", "src59:", "pba:", "ait80:", "qx92:",
)
globals()["QX_WORKSPACE_CALLBACK_PREFIXES"] = QX_WORKSPACE_CALLBACK_PREFIXES

# Commands users used to be able to type but that are intentionally retired.
QX_RETIRED_USER_COMMANDS = {
    "logs", "log", "status", "stats", "dashboard", "buffercount",
    "clear", "stopquiz", "resumequiz", "setprefix", "setexplink",
    "explain", "explainon", "explainoff", "exo", "exf", "exp",
    "score", "scoreon", "scoreoff", "postdelay", "qex", "pg", "q",
    "sh", "pro",
}

QX_MENU_TEXT = (
    "🧠 <b>Qubix — Quiz Workspace</b>\n"
    "<code>─────────────────────────</code>\n"
    "একই workflow এই Qubix bot এবং আপনার token-added personal bot—দুই জায়গাতেই।\n"
    "শুধু <b>inbox</b>-এ কাজ করবে, নিচের button গুলো দিয়েই সব চালানো যাবে।\n\n"
    "⚡️ <b>Quick start</b>\n"
    "একটি <b>poll / photo / text</b>-এ reply করে লিখুন:\n"
    "<code>.gen 15</code> · <code>.gen medical 15</code> · "
    "<code>.gen engineering 15</code> · <code>.gen versity 15</code>\n\n"
    "💬 প্রশ্ন থাকলে লিখুন: <code>.help কিভাবে channel এ post করব?</code>"
)


def _qx92_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 Generate", callback_data="qx92:how:gen"),
            InlineKeyboardButton("📦 Buffer", callback_data="qx92:buffer"),
        ],
        [
            InlineKeyboardButton("📤 Export CSV", callback_data="qx92:export"),
            InlineKeyboardButton("📣 Channels", callback_data="qx92:channels"),
        ],
        [
            InlineKeyboardButton("🧵 Topics", callback_data="qx92:topics"),
            InlineKeyboardButton("🤖 My Bot", callback_data="qx92:mybot"),
        ],
        [
            InlineKeyboardButton("📘 Full Guide", callback_data="qx92:guide"),
            InlineKeyboardButton("💬 Ask AI Help", callback_data="qx92:ask"),
        ],
    ])


def _qx92_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menu", callback_data="qx92:menu")]])


QX_HOW_GEN = (
    "🧠 <b>Quiz Generation</b>\n"
    "<code>─────────────────────────</code>\n"
    "<b>1 · Poll থেকে</b>\nএকটি quiz/poll forward করুন → সেটিতে reply করে "
    "<code>.gen 20</code>\n\n"
    "<b>2 · ছবি / PDF থেকে</b>\nছবি বা PDF পাঠান → reply করে <code>.gen 20</code>\n\n"
    "<b>3 · Text topic থেকে</b>\nযেকোনো topic লিখে সেটিতে reply করে <code>.gen 20</code>\n\n"
    "<b>Standard</b>\n"
    "<code>.gen medical 15</code> · <code>.gen engineering 15</code> · "
    "<code>.gen versity 15</code> · <code>.gen 15</code>\n\n"
    "একই source-এ command আবার দিলে আরও <b>unique</b> quiz তৈরি হবে (1–500)।"
)

QX_HOW_GUIDE = (
    "📘 <b>Qubix Guide</b>\n"
    "<code>─────────────────────────</code>\n"
    "<b>1 · Generate</b> — poll/photo/text-এ reply করে <code>.gen 15</code>\n"
    "<b>2 · Export</b> — <code>.done</code> দিলে CSV + JSON\n"
    "<b>3 · Channel</b> — bot-কে channel admin করে <code>/addchannel @channel</code>, "
    "তারপর <code>/listchannels</code> → <code>.post &lt;channel#&gt;</code>\n"
    "<b>4 · Topic</b> — text/media reply করে <code>.topic c1 pin</code>, "
    "AI review চাইলে <code>.aitopic c1 pin</code>\n"
    "<code>.mytopics</code> · <code>.usetopic &lt;id&gt;</code> · "
    "<code>.topicpin</code> · <code>.topicunpin</code>\n"
    "<b>5 · Personal bot</b> — <code>/addbot &lt;token&gt;</code> দিলে আপনার নিজের "
    "নামের bot-এ ঠিক এই workspace-টাই চলবে।\n"
    "<code>─────────────────────────</code>\n"
    "🔐 শুধু আপনার নিজের buffer, channel ও topic দেখা/ব্যবহার হবে।"
)


class _Qx92Shim:
    """Minimal Update-like object so button presses can reuse real commands."""

    def __init__(self, update):
        message = getattr(getattr(update, "callback_query", None), "message", None)
        self.message = message
        self.effective_message = message
        self.effective_chat = getattr(message, "chat", None)
        self.effective_user = getattr(update, "effective_user", None)
        self.callback_query = None
        self.edited_message = None
        self.channel_post = None
        self.poll = None
        self.update_id = int(getattr(update, "update_id", 0) or 0)


async def _qx92_invoke(name: str, update, context, args=None):
    fn = globals().get(name)
    if not callable(fn):
        return False
    prev_args = list(getattr(context, "args", []) or [])
    try:
        context.args = list(args or [])
        await fn(_Qx92Shim(update), context)
        return True
    except ApplicationHandlerStop:
        return True
    except Exception as error:
        _qx_log.warning("[QUBIX-92] %s via button failed: %s", name, error)
        return False
    finally:
        with contextlib.suppress(Exception):
            context.args = prev_args


_QX92_ALLOWED_TAGS = ("b", "i", "u", "s", "code", "pre", "a", "br")


def _qx92_sanitize_html(text: str) -> str:
    raw = str(text or "").strip()
    raw = re.sub(r"```[a-zA-Z]*\n?", "", raw)
    raw = raw.replace("```", "")
    raw = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", raw, flags=re.S)
    raw = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<i>\1</i>", raw, flags=re.S)

    def _keep(match):
        tag = match.group(2).lower()
        return match.group(0) if tag in _QX92_ALLOWED_TAGS else ""

    raw = re.sub(r"<(/?)([a-zA-Z0-9]+)[^>]*>", _keep, raw)
    return raw.strip()[:3500]


def _qx92_help_prompt(question: str) -> str:
    return (
        "You are Qubix, a Telegram quiz-workspace assistant. Answer ONLY about the "
        "features listed below. Never mention owner/admin infrastructure, logs, "
        "keys, broadcast, database, or any command not listed.\n\n"
        "Available user features (inbox only):\n"
        "- Generate quiz: reply to a poll/quiz, photo/PDF, or text topic with "
        ".gen <count>, .gen medical <count>, .gen engineering <count>, .gen versity <count> (1-500)\n"
        "- View buffer: /buffer ; Export CSV+JSON: .done\n"
        "- Channels: /addchannel @channel, /listchannels, /removechannel, .post <channel#>\n"
        "- Groups/topics publishing: .adg <group_id>, .adtc <group#> <thread_id> <name>, "
        ".pt <group#> <topic#>, .listgroups, .listtopics\n"
        "- Topic header/anchor: .topic, .aitopic, .mytopics, .usetopic <id>, "
        ".topicpin, .topicunpin, .cleartopic, .linktopic\n"
        "- Personal bot: /addbot <token>, /mybot on|off, /removebot, /myid\n\n"
        "Rules: answer in the user's language (Bangla/Banglish if they wrote so), "
        "be short and practical, use Telegram HTML only (<b>, <i>, <code>), "
        "give exact command examples, max 12 lines.\n\n"
        f"User question: {question}"
    )


async def _qx92_ai_help(question: str) -> str:
    router = globals().get("_gemini_text_router")
    if not callable(router):
        return ""
    try:
        loop = asyncio.get_running_loop()
        text, _src = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: router(_qx92_help_prompt(question), timeout_seconds=25)),
            timeout=40,
        )
        return _qx92_sanitize_html(text)
    except Exception as error:
        _qx_log.warning("[QUBIX-92] AI help failed: %s", error)
        return ""


def _qx92_is_privileged(update) -> bool:
    uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not uid:
        return False
    if _qx_real_owner(uid):
        return True
    return bool(_qx_prev_is_admin and _qx_prev_is_admin(uid))


async def qx92_scope_gate(update, context):
    """Inbox-only + retired-command guard. Runs before every other handler."""
    if _qx92_is_privileged(update):
        return
    chat = getattr(update, "effective_chat", None)
    chat_type = str(getattr(chat, "type", "") or "")
    if chat_type and chat_type != "private":
        raise ApplicationHandlerStop

    message = getattr(update, "effective_message", None)
    text = str(getattr(message, "text", "") or "")
    if text[:1] in ("/", "."):
        command = re.split(r"[\s@]", text[1:].strip(), 1)[0].lower()
        if command in QX_RETIRED_USER_COMMANDS:
            with contextlib.suppress(Exception):
                await message.reply_text(
                    ui_box_html(
                        "Not Available",
                        "এই command এখন workspace-এ নেই। নিচের button গুলো দিয়েই সব কাজ হবে।",
                        emoji="⛔",
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=_qx92_menu_kb(),
                )
            raise ApplicationHandlerStop


async def qx92_cmd_menu(update, context):
    uid = _qx91_access_uid(update, context)
    st = _qx_access(uid)
    if not st.get("ok"):
        await update.effective_message.reply_text(
            _qx_expired_card(uid, getattr(update.effective_user, "full_name", "")),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    question = " ".join(list(context.args or [])).strip()
    if question:
        thinking = await update.effective_message.reply_text(
            ui_box_html("Qubix Assistant", "উত্তর তৈরি হচ্ছে…", emoji="💬"),
            parse_mode=ParseMode.HTML,
        )
        answer = await _qx92_ai_help(question)
        body = answer or (
            "এই মুহূর্তে AI উত্তর দিতে পারছে না। নিচের guide ও button ব্যবহার করুন।"
        )
        with contextlib.suppress(Exception):
            await thinking.edit_text(
                "💬 <b>Qubix Assistant</b>\n<code>─────────────────────────</code>\n" + body,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx92_menu_kb(),
                disable_web_page_preview=True,
            )
        raise ApplicationHandlerStop

    await update.effective_message.reply_text(
        QX_MENU_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_qx92_menu_kb(),
        disable_web_page_preview=True,
    )
    raise ApplicationHandlerStop


async def qx92_on_callback(update, context):
    query = update.callback_query
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("qx92:"):
        return
    action = data.split(":", 2)[1] if ":" in data else "menu"
    uid = _qx91_access_uid(update, context)

    async def _card(text_html: str):
        with contextlib.suppress(Exception):
            await query.edit_message_text(
                text_html,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx92_back_kb(),
                disable_web_page_preview=True,
            )

    await query.answer()
    if action == "menu":
        with contextlib.suppress(Exception):
            await query.edit_message_text(
                QX_MENU_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx92_menu_kb(),
                disable_web_page_preview=True,
            )
    elif action == "how":
        await _card(QX_HOW_GEN)
    elif action == "guide":
        await _card(QX_HOW_GUIDE)
    elif action == "ask":
        await _card(
            "💬 <b>Ask AI Help</b>\n<code>─────────────────────────</code>\n"
            "আপনার প্রশ্নটি এভাবে লিখুন:\n"
            "<code>.help কিভাবে channel এ quiz post করব?</code>\n"
            "<code>.help topic pin কিভাবে করে?</code>\n\n"
            "শুধু আপনার জন্য বরাদ্দ ফিচার নিয়েই উত্তর দেওয়া হবে।"
        )
    elif action == "buffer":
        total = 0
        with contextlib.suppress(Exception):
            total = int(buffer_count(uid))
        await _card(
            "📦 <b>Buffer</b>\n<code>─────────────────────────</code>\n"
            f"Ready quiz: <code>{total}</code>\n\n"
            "সব দেখতে <code>/buffer</code>, export করতে <code>.done</code>।"
        )
    elif action == "export":
        if not await _qx92_invoke("cmd_done", update, context):
            await _card(
                "📤 <b>Export</b>\n<code>─────────────────────────</code>\n"
                "Export করতে লিখুন <code>.done</code> — CSV + JSON পাবেন।"
            )
    elif action == "channels":
        if not await _qx92_invoke("cmd_listchannels", update, context):
            await _card(
                "📣 <b>Channels</b>\n<code>─────────────────────────</code>\n"
                "Bot-কে channel admin করে <code>/addchannel @channel</code>, "
                "তারপর <code>/listchannels</code> → <code>.post &lt;channel#&gt;</code>।"
            )
    elif action == "topics":
        if not await _qx92_invoke("_cmd_mytopics_m", update, context):
            await _card(
                "🧵 <b>Topics</b>\n<code>─────────────────────────</code>\n"
                "Text/media reply করে <code>.topic c1 pin</code> বা <code>.aitopic c1 pin</code>, "
                "তারপর <code>.mytopics</code> / <code>.usetopic &lt;id&gt;</code>।"
            )
    elif action == "mybot":
        if not await _qx92_invoke("qx_cmd_mybot", update, context):
            await _card(
                "🤖 <b>Personal Bot</b>\n<code>─────────────────────────</code>\n"
                "<code>/addbot &lt;token&gt;</code> দিলে আপনার নিজের নামের bot-এ এই workspace চলবে।\n"
                "<code>/mybot on</code> · <code>/mybot off</code> · <code>/removebot</code>"
            )
    else:
        await _card(QX_HOW_GUIDE)
    raise ApplicationHandlerStop


_qx92_previous_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx92_previous_build_app() if callable(_qx92_previous_build_app) else None
    if app is None:
        return app

    def _dual(name, callback, group):
        register = globals().get("_register_dual_command")
        if callable(register):
            register(app, name, callback, group=group)
        else:
            app.add_handler(CommandHandler(name, callback), group=group)

    with contextlib.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx92_scope_gate), group=-1020)
        app.add_handler(CallbackQueryHandler(qx92_on_callback, pattern=r"^qx92:"), group=-1015)

    for command in ("start", "menu", "help", "cmd", "commands", "guide"):
        with contextlib.suppress(Exception):
            _dual(command, qx92_cmd_menu, -990)

    _qx_log.info("[QUBIX-92] rich inbox UI, trimmed commands and AI help wired.")
    return app


_qx_log.info("[SECTION 92] Qubix rich inbox workspace UI loaded.")
