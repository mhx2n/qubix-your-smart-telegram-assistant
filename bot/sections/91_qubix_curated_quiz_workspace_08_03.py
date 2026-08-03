# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 91 — QUBIX CURATED QUIZ WORKSPACE (2026-08-03)
#
# Gives an approved/trial user the same focused workspace on the main Qubix bot
# and on their token-added personal bot.  It deliberately exposes quiz creation,
# export and the user's own publishing destinations — never owner infrastructure.
# ══════════════════════════════════════════════════════════════════════════════

QX_WORKSPACE_COMMANDS = {
    "start", "help", "cmd", "commands", "guide", "myid", "id",
    "gen", "done", "buffer", "clear", "stopquiz", "resumequiz",
    "addchannel", "listchannels", "channels", "removechannel", "setprefix",
    "setexplink", "post", "adg", "addgroup", "listgroups", "groups",
    "adtc", "addtopic", "listtopics", "topics", "info", "pt", "pg",
    "topic", "aitopic", "mytopics", "usetopic", "cleartopic", "linktopic",
    "topicinfo", "topicoff", "topicpin", "topicunpin", "shuffle", "qex",
    "explain", "explainon", "explainoff", "postdelay",
    "addbot", "mybot", "removebot", "delbot", "wake", "q", "status",
}

QX_WORKSPACE_CALLBACK_PREFIXES = (
    "g59:", "genq:", "src59:", "pba:", "ait80:",
)

QX_WORKSPACE_HELP = (
    "🧠 <b>Qubix — Quiz Workspace</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "একই workflow এই Qubix bot এবং আপনার token-added personal bot—দুই জায়গাতেই কাজ করবে।\n\n"
    "<b>1 · Quiz generate</b>\n"
    "একটি poll/quiz, photo/PDF, অথবা topic text-এ reply করে লিখুন:\n"
    "<code>.gen 15</code> — source অনুযায়ী 15টি\n"
    "<code>.gen medical 15</code> — Medical standard\n"
    "<code>.gen engineering 15</code> — Engineering standard\n"
    "<code>.gen versity 15</code> — University standard\n"
    "Count 1–500; command আবার দিলে একই topic থেকে আরও unique quiz হবে।\n\n"
    "<b>2 · Buffer &amp; export</b>\n"
    "<code>/buffer</code> · <code>.done</code> (CSV + JSON) · <code>.clear</code>\n\n"
    "<b>3 · Channel</b>\n"
    "Bot-কে channel admin করে <code>/addchannel @channel</code>\n"
    "তারপর <code>/listchannels</code> → <code>.post &lt;channel#&gt;</code>\n\n"
    "<b>4 · Forum group/topic</b>\n"
    "Bot-কে group admin করে <code>.adg -100...</code>\n"
    "Topic-এর ভিতরে <code>.info</code>, তারপর inbox-এ\n"
    "<code>.adtc &lt;group#&gt; &lt;thread_id&gt; Biology</code>\n"
    "Post: <code>.pt &lt;group#&gt; &lt;topic#&gt;</code>\n\n"
    "<b>5 · Topic header / anchor</b>\n"
    "Text/media reply: <code>.topic c1 pin</code> অথবা <code>.topic g1 2</code>\n"
    "AI review: <code>.aitopic c1 pin</code> / <code>.aitopic g1 2</code>\n"
    "<code>.mytopics</code> · <code>.usetopic &lt;id&gt;</code> · "
    "<code>.topicpin</code> · <code>.topicunpin</code> · <code>.cleartopic</code>\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔐 শুধু আপনার নিজের buffer, channel, group ও topic দেখা/ব্যবহার হবে।"
)


def _qx91_is_child(context) -> bool:
    return bool(getattr(context, "application", None) and context.application.bot_data.get("qx_tenant_uid"))


def _qx91_access_uid(update, context) -> int:
    if _qx91_is_child(context):
        return int(context.application.bot_data.get("qx_tenant_uid") or 0)
    return int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)


def _qx91_source_from_poll(poll) -> Dict[str, Any]:
    question = str(getattr(poll, "question", "") or "").strip()
    options = [str(getattr(opt, "text", "") or "").strip() for opt in (getattr(poll, "options", None) or [])]
    options = [value for value in options if value]
    source = "QUESTION:\n" + question
    if options:
        source += "\nOPTIONS:\n" + "\n".join(
            f"{chr(65 + index)}. {value}" for index, value in enumerate(options)
        )
    return {
        "raw_markdown": source,
        "clean_text": source,
        "items": [{"questions": question, **{f"option{i + 1}": value for i, value in enumerate(options)}}],
        "source_label": "forwarded_poll",
    }


def _qx91_source_from_text(text: str) -> Dict[str, Any]:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return {
        "raw_markdown": clean,
        "clean_text": clean,
        "items": [],
        "source_label": "replied_text",
    }


async def _qx91_resolve_source(update, context, reply, uid: int) -> Optional[Dict[str, Any]]:
    poll = getattr(reply, "poll", None)
    if poll:
        return _qx91_source_from_poll(poll)

    text = str(getattr(reply, "text", None) or getattr(reply, "caption", None) or "").strip()
    has_media = bool(getattr(reply, "photo", None) or getattr(reply, "document", None))
    if has_media:
        resolver = globals().get("_resolve_ocr_ctx_59")
        if callable(resolver):
            ocr_ctx = await resolver(update, context, reply, uid)
            if ocr_ctx:
                return ocr_ctx
    if text:
        return _qx91_source_from_text(text)
    return None


async def qx91_cmd_gen(update, context):
    if not update.message or not update.effective_user:
        raise ApplicationHandlerStop
    uid = _qx91_access_uid(update, context)
    st = _qx_access(uid)
    if not st.get("ok"):
        await update.message.reply_text(
            _qx_expired_card(uid, update.effective_user.full_name), parse_mode=ParseMode.HTML
        )
        raise ApplicationHandlerStop

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(
            ui_box_html(
                "Generate Quiz",
                "একটি <b>poll/quiz, photo/PDF অথবা topic text</b>-এ reply করে দিন:\n\n"
                "<code>.gen 15</code>\n<code>.gen medical 15</code>\n"
                "<code>.gen engineering 15</code>\n<code>.gen versity 15</code>",
                emoji="ℹ️",
            ),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    mode, count, _cleaned = _mode_count_59(update.message.text or "", list(context.args or []))
    source = await _qx91_resolve_source(update, context, reply, uid)
    if not source:
        await warn(
            update,
            "Source Not Found",
            "Reply directly to a poll/quiz, readable photo/PDF, or a text topic and try again.",
        )
        raise ApplicationHandlerStop

    if count is None:
        token = uuid.uuid4().hex[:10]
        _g59_store(context)[token] = {
            "uid": uid,
            "chat_id": update.message.chat_id,
            "mode": mode or "",
            "ocr_ctx": source,
            "ts": time.time(),
        }
        if mode:
            title, body, keyboard = "Quiz Count", f"Mode: <b>{h(mode.upper())}</b>\nকতটি unique quiz বানাব?", _g59_count_kb(token)
        else:
            title, body, keyboard = "Quiz Standard", "কোন admission standard-এ quiz বানাব?", _g59_mode_kb(token)
        await update.message.reply_text(
            ui_box_html(title, body, emoji="🧠"), parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
        raise ApplicationHandlerStop

    count = max(1, min(500, int(count)))
    status = await update.message.reply_text(
        ui_box_html(
            "Generating Quiz",
            f"Source: <b>{h(source.get('source_label', 'content'))}</b>\n"
            f"Standard: <b>{h((mode or 'std').upper())}</b>\nCount: <code>{count}</code>",
            emoji="⏳",
        ),
        parse_mode=ParseMode.HTML,
    )
    try:
        added, duplicates = await _generate_to_buffer_59(
            update, context, source, uid, count, mode or "std"
        )
        await status.edit_text(
            ui_box_html(
                "Quiz Ready",
                f"Added: <code>{added}</code>\nDuplicates skipped: <code>{duplicates}</code>\n"
                f"Buffer total: <code>{buffer_count(uid)}</code>\n\n"
                "আরও unique quiz চাইলে একই source-এ reply করে command-টি আবার দিন।",
                emoji="✅",
            ),
            parse_mode=ParseMode.HTML,
        )
        if added:
            await _send_pb_action_card(context, update.message.chat_id, uid, added)
    except Exception as error:
        await status.edit_text(
            ui_box_html(
                "Generation Failed",
                f"{h(str(error)[:220])}\n\nSource-এ আবার reply করে চেষ্টা করুন; ব্যর্থ হলে owner-কে জানান।",
                emoji="⚠️",
            ),
            parse_mode=ParseMode.HTML,
        )
    raise ApplicationHandlerStop


async def qx91_cmd_workspace(update, context):
    uid = _qx91_access_uid(update, context)
    st = _qx_access(uid)
    if not st.get("ok"):
        await update.effective_message.reply_text(
            _qx_expired_card(uid, update.effective_user.full_name), parse_mode=ParseMode.HTML
        )
        raise ApplicationHandlerStop
    await update.effective_message.reply_text(
        QX_WORKSPACE_HELP, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
    raise ApplicationHandlerStop


async def qx91_cmd_topic_pin(update, context, pin: bool):
    uid = _qx91_access_uid(update, context)
    anchor_chat, anchor_message = _get_topic_anchor(uid)
    if not anchor_chat or not anchor_message:
        await warn(update, "No Active Topic", "আগে .topic / .aitopic / .usetopic দিয়ে একটি active topic set করুন।")
        raise ApplicationHandlerStop
    try:
        if pin:
            await context.bot.pin_chat_message(
                chat_id=anchor_chat, message_id=anchor_message, disable_notification=True
            )
        else:
            await context.bot.unpin_chat_message(chat_id=anchor_chat, message_id=anchor_message)
        await ok(
            update,
            "Topic Pinned" if pin else "Topic Unpinned",
            "Active topic anchor অপরিবর্তিত আছে; পরবর্তী quiz এখনও এই topic-এ reply হবে।",
        )
    except Exception as error:
        await err(update, "Topic Update Failed", str(error)[:220])
    raise ApplicationHandlerStop


async def qx91_cmd_topicpin(update, context):
    await qx91_cmd_topic_pin(update, context, True)


async def qx91_cmd_topicunpin(update, context):
    await qx91_cmd_topic_pin(update, context, False)


async def qx91_main_gate(update, context):
    """Make the main bot a real curated workspace, not merely a token panel."""
    user = getattr(update, "effective_user", None)
    uid = int(getattr(user, "id", 0) or 0)
    if not uid or _qx_real_owner(uid) or (_qx_prev_is_admin and _qx_prev_is_admin(uid)):
        return
    st = _qx_access(uid)
    if not st.get("ok"):
        await update.effective_message.reply_text(
            _qx_expired_card(uid, getattr(user, "full_name", "")), parse_mode=ParseMode.HTML
        )
        raise ApplicationHandlerStop

    text = str(getattr(getattr(update, "effective_message", None), "text", "") or "")
    if text[:1] in ("/", "."):
        command = re.split(r"[\s@]", text[1:].strip(), 1)[0].lower()
        if command not in QX_WORKSPACE_COMMANDS:
            await update.effective_message.reply_text(
                "⛔ এই command workspace-এর অংশ নয়। Curated guide দেখতে <code>/help</code> দিন।",
                parse_mode=ParseMode.HTML,
            )
            raise ApplicationHandlerStop
        _QX_ACTING_OWNER.set(uid)
        return

    token_match = _QX_TOKEN_RE.search(text)
    if token_match:
        with contextlib.suppress(Exception):
            await update.effective_message.delete()
        await _qx_register_token(update, uid, getattr(user, "full_name", ""), token_match.group(1))
        raise ApplicationHandlerStop

    await update.effective_message.reply_text(
        "📌 Source received. এই poll/photo/text-এ <b>reply</b> করে "
        "<code>.gen 15</code> অথবা <code>.gen medical 15</code> দিন।",
        parse_mode=ParseMode.HTML,
    )
    raise ApplicationHandlerStop


async def qx91_callback_gate(update, context):
    """Restore the user's scoped owner context for interactive workspace cards."""
    query = getattr(update, "callback_query", None)
    user = getattr(update, "effective_user", None)
    uid = int(getattr(user, "id", 0) or 0)
    if not query or not uid or _qx_real_owner(uid) or (_qx_prev_is_admin and _qx_prev_is_admin(uid)):
        return
    tenant_uid = int(context.application.bot_data.get("qx_tenant_uid") or 0)
    if tenant_uid and uid != tenant_uid:
        await query.answer("This personal workspace is private.", show_alert=True)
        raise ApplicationHandlerStop
    scoped_uid = tenant_uid or uid
    st = _qx_access(scoped_uid)
    if not st.get("ok"):
        await query.answer("Your Qubix access has expired.", show_alert=True)
        raise ApplicationHandlerStop
    data = str(getattr(query, "data", "") or "")
    if not data.startswith(QX_WORKSPACE_CALLBACK_PREFIXES):
        await query.answer("This control is not available in your workspace.", show_alert=True)
        raise ApplicationHandlerStop
    _QX_ACTING_OWNER.set(scoped_uid)
    context.application.bot_data["qx_last_active"] = time.time()


async def qx91_child_gate(update, context):
    """Allow only the curated workspace on a tenant bot."""
    owner_uid = int(context.application.bot_data.get("qx_tenant_uid") or 0)
    user_uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if user_uid != owner_uid:
        await update.effective_message.reply_text("🔒 এই personal bot শুধু এর owner ব্যবহার করতে পারবেন।")
        raise ApplicationHandlerStop
    st = _qx_access(owner_uid)
    if not st.get("ok"):
        await update.effective_message.reply_text(
            _qx_expired_card(owner_uid, context.application.bot_data.get("qx_tenant_name", "")),
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(_qx_stop_runner(owner_uid, reason="access expired"))
        raise ApplicationHandlerStop

    callback = getattr(update, "callback_query", None)
    if callback:
        data = str(getattr(callback, "data", "") or "")
        if not data.startswith(QX_WORKSPACE_CALLBACK_PREFIXES):
            await callback.answer("This control is not available in your workspace.", show_alert=True)
            raise ApplicationHandlerStop
    text = str(getattr(getattr(update, "effective_message", None), "text", "") or "")
    if text[:1] in ("/", "."):
        command = re.split(r"[\s@]", text[1:].strip(), 1)[0].lower()
        if command not in QX_WORKSPACE_COMMANDS:
            await update.effective_message.reply_text(
                "⛔ Owner infrastructure command এখানে নেই। আপনার command guide: <code>/help</code>",
                parse_mode=ParseMode.HTML,
            )
            raise ApplicationHandlerStop
    _QX_ACTING_OWNER.set(owner_uid)
    context.application.bot_data["qx_last_active"] = time.time()


# Replace section-90 gates by rebinding the callback globals used by PTB Handler.
globals()["qx_main_gate"] = qx91_main_gate
globals()["_qx_child_gate"] = qx91_child_gate

_qx91_previous_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx91_previous_build_app() if callable(_qx91_previous_build_app) else None
    if app is None:
        return app

    def _dual(name, callback, group):
        register = globals().get("_register_dual_command")
        if callable(register):
            register(app, name, callback, group=group)
        else:
            app.add_handler(CommandHandler(name, callback), group=group)

    # These handlers are intentionally cloneable: they provide the exact same
    # professional surface on Qubix and on every token-added personal bot.
    for command in ("start", "help", "cmd", "commands", "guide"):
        with contextlib.suppress(Exception):
            _dual(command, qx91_cmd_workspace, -980)
    with contextlib.suppress(Exception):
        _dual("gen", qx91_cmd_gen, -975)
    with contextlib.suppress(Exception):
        _dual("topicpin", qx91_cmd_topicpin, -975)
        _dual("topicunpin", qx91_cmd_topicunpin, -975)

    # Gates run before every legacy handler. They convert the approved/trial
    # identity into a tightly scoped acting owner for only the current update.
    with contextlib.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx91_main_gate), group=-1010)
        app.add_handler(CallbackQueryHandler(qx91_callback_gate), group=-1010)

    _qx_log.info("[QUBIX-91] curated main/personal quiz workspace wired.")
    return app


_qx_log.info("[SECTION 91] Qubix curated generation, publishing and topic UI loaded.")