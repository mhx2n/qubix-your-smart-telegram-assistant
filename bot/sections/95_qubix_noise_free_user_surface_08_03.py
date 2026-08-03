# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 95 — QUBIX NOISE-FREE USER SURFACE (2026-08-03)
#
# Production bugs fixed here:
#   1. "⚠️ Unauthorized — restricted for staff operations" reached approved /
#      trial users. Every such warning is produced by legacy staff guards that
#      funnel through `safe_reply`. A single choke point now swallows those
#      staff-only warnings for a valid workspace user, so the user only ever
#      sees their own panel.
#   2. Duplicate identical cards ("Buffer Empty" twice, etc.) — legacy sections
#      register several handlers for the same command. `safe_reply` now drops an
#      identical message to the same chat inside a short window.
#   3. Owner panel never renders inside a token-added personal bot: a single
#      start/menu router decides owner-vs-user before section 94's handlers.
#   4. `.gen` now shows a real progress trail ("ছবি পড়া হচ্ছে → quiz তৈরি
#      হচ্ছে") and finishes with ONE merged result card carrying the action
#      buttons — no more "Quiz Ready" + "Quiz Actions" double card.
#   5. Buffer count is a first-class user command: /buffercount, .bc, /buffer.
# ══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 0) Workspace command surface — everything a user can really run
# ─────────────────────────────────────────────────────────────────────────────
with contextlib.suppress(Exception):
    QX_WORKSPACE_COMMANDS |= {
        "menu", "buffercount", "bc", "export", "csv", "myid", "id",
        "exo", "exf", "score", "b", "c",
    }

# Buffer-count and buffer-clear are user features again (mutate in place so the
# section-92 gate, which reads the same set object, sees the change).
with contextlib.suppress(Exception):
    for _name in ("buffercount", "bc", "b", "clear", "c"):
        QX_RETIRED_USER_COMMANDS.discard(_name)




def _qx95_is_tenant(context) -> bool:
    """True when the update arrived on a token-added personal bot."""
    with contextlib.suppress(Exception):
        if int(context.application.bot_data.get("qx_tenant_uid") or 0):
            return True
    with contextlib.suppress(Exception):
        token = str(getattr(context.bot, "token", "") or "")
        main = str(globals().get("BOT_TOKEN") or "")
        if token and main and token != main:
            return True
    return False


def _qx95_scope_uid(update, context) -> int:
    with contextlib.suppress(Exception):
        tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
        if tenant:
            return tenant
    return int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)


def _qx95_workspace_user(update, context=None) -> bool:
    """Approved/trial (non-staff) user whose access is still valid."""
    uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not uid:
        return False
    with contextlib.suppress(Exception):
        if _qx93_privileged(update):
            return False
    with contextlib.suppress(Exception):
        return bool(_qx_access(uid).get("ok"))
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 1) + 2) Single choke point: kill staff-only noise and duplicate cards
# ─────────────────────────────────────────────────────────────────────────────
_QX95_STAFF_NOISE = (
    "restricted for staff operations",
    "only admin/owner can use this feature",
    "only a group admin",
    "only owner/admin",
    "owner infrastructure command",
    "not allowed for your role",
)

_QX95_RECENT: Dict[Any, float] = {}
_QX95_DEDUPE_WINDOW = 12.0


def _qx95_norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


_qx95_prev_safe_reply = globals().get("safe_reply")


async def safe_reply(update: Update, text: str) -> None:  # noqa: F811
    """Legacy-safe reply with staff-noise suppression + duplicate collapsing."""
    body = str(text or "")
    low = _qx95_norm(body)

    if low.startswith("⚠️ unauthorized") or "unauthorized" in low[:40]:
        if any(marker in low for marker in _QX95_STAFF_NOISE) and _qx95_workspace_user(update):
            return
    if any(marker in low for marker in _QX95_STAFF_NOISE) and _qx95_workspace_user(update):
        return

    chat_id = 0
    with contextlib.suppress(Exception):
        chat_id = int(getattr(getattr(update, "effective_chat", None), "id", 0) or 0)
    now = time.time()
    for key, stamp in list(_QX95_RECENT.items()):
        if now - stamp > 60:
            _QX95_RECENT.pop(key, None)
    signature = (chat_id, low[:400])
    if now - float(_QX95_RECENT.get(signature, 0.0)) < _QX95_DEDUPE_WINDOW:
        return
    _QX95_RECENT[signature] = now

    if callable(_qx95_prev_safe_reply):
        await _qx95_prev_safe_reply(update, body)


globals()["safe_reply"] = safe_reply

_qx95_prev_warn_unauthorized = globals().get("warn_unauthorized")


async def warn_unauthorized(update: Update, reason: str = "") -> None:  # noqa: F811
    if _qx95_workspace_user(update):
        return
    if callable(_qx95_prev_warn_unauthorized):
        await _qx95_prev_warn_unauthorized(update, reason)


globals()["warn_unauthorized"] = warn_unauthorized


# ─────────────────────────────────────────────────────────────────────────────
# 3) Owner-vs-user router (runs before section 94's panel handlers)
# ─────────────────────────────────────────────────────────────────────────────
async def qx95_panel_router(update, context):
    tenant = _qx95_is_tenant(context)
    owner = False
    with contextlib.suppress(Exception):
        owner = bool(_qx93_privileged(update)) and not tenant

    if owner:
        await _qx94_clean_send(update, context, QX94_OWNER_CARD, _qx94_owner_kb())
        raise ApplicationHandlerStop

    uid = _qx95_scope_uid(update, context)
    st = _qx_access(uid)
    if not st.get("ok"):
        await _qx94_clean_send(
            update, context,
            _qx_expired_card(uid, getattr(getattr(update, "effective_user", None), "full_name", "")),
        )
        raise ApplicationHandlerStop

    await _qx94_clean_send(
        update, context,
        await _qx94_user_menu_text(update, context, uid, st),
        _qx93_menu_kb(),
    )
    raise ApplicationHandlerStop


async def qx95_panel_router_help(update, context):
    """`/help <question>` keeps the AI path; bare `/help` shows the panel."""
    if " ".join(list(getattr(context, "args", []) or [])).strip():
        return
    await qx95_panel_router(update, context)


async def qx95_owner_callback_shield(update, context):
    """Owner-panel buttons must never act inside a token-added personal bot."""
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    if not _qx95_is_tenant(context):
        return
    with contextlib.suppress(Exception):
        await query.answer()
    uid = _qx95_scope_uid(update, context)
    st = _qx_access(uid)
    with contextlib.suppress(Exception):
        await query.edit_message_text(
            await _qx94_user_menu_text(update, context, uid, st),
            parse_mode=ParseMode.HTML,
            reply_markup=_qx93_menu_kb(),
            disable_web_page_preview=True,
        )
    raise ApplicationHandlerStop


async def qx95_cmd_commands(update, context):

    tenant = _qx95_is_tenant(context)
    owner = False
    with contextlib.suppress(Exception):
        owner = bool(_qx93_privileged(update)) and not tenant
    if owner:
        await _qx94_clean_send(update, context, QX94_OWNER_CARD, _qx94_owner_kb())
        raise ApplicationHandlerStop
    uid = _qx95_scope_uid(update, context)
    if not _qx_access(uid).get("ok"):
        await _qx94_clean_send(
            update, context,
            _qx_expired_card(uid, getattr(getattr(update, "effective_user", None), "full_name", "")),
        )
        raise ApplicationHandlerStop
    await _qx94_clean_send(update, context, QX95_USER_COMMANDS_CARD, _qx93_menu_kb())
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 5) Buffer count as a user command
# ─────────────────────────────────────────────────────────────────────────────
def _qx95_buffer_card(uid: int) -> str:
    total = 0
    with contextlib.suppress(Exception):
        total = int(buffer_count(uid))
    lines = [
        "📦 <b>Buffer Count</b>",
        QX94_ROW,
        f"🧠 Ready quiz: <b>{total}</b>",
    ]
    if total:
        lines += [
            "",
            "📤 <code>.done</code> — CSV + JSON export",
            "📣 <code>.post &lt;channel#&gt;</code> — channel-এ post",
            "🧵 <code>.pt &lt;group#&gt; &lt;topic#&gt;</code> — topic-এ post",
            "🧹 <code>.clear</code> — buffer খালি",
        ]
    else:
        lines += [
            "",
            "<i>এখনো কিছু জমা হয়নি।</i>",
            "একটি <b>poll / photo / text</b>-এ reply করে <code>.gen 15</code> দিন।",
        ]
    return "\n".join(lines)


async def qx95_cmd_buffercount(update, context):
    uid = _qx95_scope_uid(update, context)
    if not _qx_access(uid).get("ok"):
        await _qx94_clean_send(
            update, context,
            _qx_expired_card(uid, getattr(getattr(update, "effective_user", None), "full_name", "")),
        )
        raise ApplicationHandlerStop
    await _qx94_clean_send(update, context, _qx95_buffer_card(uid), _qx93_menu_kb())
    raise ApplicationHandlerStop


globals()["_qx93_buffer_card"] = _qx95_buffer_card


# ─────────────────────────────────────────────────────────────────────────────
# 4) `.gen` — live progress + ONE merged result card
# ─────────────────────────────────────────────────────────────────────────────
def _qx95_source_kind(reply) -> Tuple[str, str]:
    if getattr(reply, "poll", None):
        return "poll", "🧩 Forwarded quiz/poll পড়া হচ্ছে…"
    if getattr(reply, "photo", None):
        return "photo", "🖼 ছবি থেকে লেখা পড়া হচ্ছে (OCR)…"
    if getattr(reply, "document", None):
        return "file", "📄 File থেকে লেখা পড়া হচ্ছে…"
    return "text", "📝 Text topic পড়া হচ্ছে…"


_QX95_SOURCE_LABEL = {
    "forwarded_poll": "🧩 Forwarded quiz/poll",
    "replied_text": "📝 Text topic",
}


def _qx95_pretty_source(kind: str, source: Dict[str, Any]) -> str:
    if kind == "photo":
        return "🖼 ছবি (OCR)"
    if kind == "file":
        return "📄 File (OCR)"
    label = str((source or {}).get("source_label") or "")
    return _QX95_SOURCE_LABEL.get(label, "🧩 Source content" if kind == "poll" else "📝 Text topic")


def _qx95_channel_directory(uid: int) -> str:
    """Numbered channel directory for the result card (no post buttons)."""
    try:
        channels = channel_list_for_user(uid) or []
    except Exception:
        channels = []
    if not channels:
        return (
            "📣 <b>Channel Directory</b>\n"
            "কোনো channel সংযুক্ত নেই — <code>/addchannel @channel</code> দিয়ে যোগ করুন।"
        )
    lines = ["📣 <b>Channel Directory</b>"]
    for ch in channels[:25]:
        title = str(getattr(ch, "title", None) or getattr(ch, "channel_chat_id", "—"))
        lines.append(f"<code>{getattr(ch, 'id', '?')}</code> · <b>{h(title[:32])}</b>")
    lines.append("Publish: <code>.post &lt;channel#&gt;</code>")
    return "\n".join(lines)


async def _qx95_result_kb(context, uid: int, chat_id: int) -> Optional[InlineKeyboardMarkup]:
    with contextlib.suppress(Exception):
        token = uuid.uuid4().hex[:10]
        _pb_store(context)[token] = {"uid": uid, "chat_id": chat_id, "ts": time.time()}
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📂 Export CSV", callback_data=f"pba:csv:{token}"),
                InlineKeyboardButton("🧹 Clear Buffer", callback_data=f"pba:clr:{token}"),
            ],
            [InlineKeyboardButton("✖ Close", callback_data=f"pba:close:{token}")],
        ])
    return None



async def qx95_cmd_gen(update, context):
    message = getattr(update, "effective_message", None)
    if message is None or not getattr(update, "effective_user", None):
        raise ApplicationHandlerStop

    uid = _qx95_scope_uid(update, context)
    st = _qx_access(uid)
    if not st.get("ok"):
        await message.reply_text(
            _qx_expired_card(uid, update.effective_user.full_name), parse_mode=ParseMode.HTML
        )
        raise ApplicationHandlerStop
    _QX_ACTING_OWNER.set(int(uid))

    reply = getattr(message, "reply_to_message", None)
    if not reply:
        await message.reply_text(
            ui_box_html(
                "Generate Quiz",
                "একটি <b>quiz/poll, ছবি অথবা topic text</b>-এ <b>reply</b> করে লিখুন:\n\n"
                "<code>.gen 15</code>\n<code>.gen medical 15</code>\n"
                "<code>.gen engineering 15</code>\n<code>.gen versity 15</code>\n\n"
                "Count 1–500; একই source-এ আবার দিলে আরও unique quiz হবে।",
                emoji="ℹ️",
            ),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    mode, count, _cleaned = _mode_count_59(getattr(message, "text", "") or "", list(context.args or []))
    kind, reading_line = _qx95_source_kind(reply)

    status = None
    # Same source, new run → retire the previous result card so only one stays.
    _qx95_cards = globals().setdefault("_QX95_LAST_GEN_CARD", {})
    _qx95_key = (int(message.chat_id), int(uid))
    _qx95_old = _qx95_cards.pop(_qx95_key, None)
    if _qx95_old:
        with contextlib.suppress(Exception):
            await context.bot.delete_message(chat_id=message.chat_id, message_id=int(_qx95_old))

    with contextlib.suppress(Exception):
        status = await message.reply_text(
            ui_box_html("Working", reading_line, emoji="⏳"), parse_mode=ParseMode.HTML
        )
    if status is not None:
        with contextlib.suppress(Exception):
            _qx95_cards[_qx95_key] = int(status.message_id)


    async def _set(title: str, body: str, emoji: str, keyboard=None):
        card = ui_box_html(title, body, emoji=emoji)
        if status is not None:
            with contextlib.suppress(Exception):
                await status.edit_text(
                    card, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                return
        with contextlib.suppress(Exception):
            await message.reply_text(
                card, parse_mode=ParseMode.HTML, reply_markup=keyboard,
                disable_web_page_preview=True,
            )

    source = await _qx91_resolve_source(update, context, reply, uid)
    if not source:
        await _set(
            "Source Not Found",
            "এই message থেকে কিছু পড়া গেল না।\n\n"
            "• ছবি হলে লেখা স্পষ্ট আছে কি না দেখুন\n"
            "• অথবা quiz/poll কিংবা text-এ reply করুন",
            "⚠️",
        )
        raise ApplicationHandlerStop

    pretty = _qx95_pretty_source(kind, source)

    if count is None:
        if status is not None:
            with contextlib.suppress(Exception):
                await status.delete()
            _qx95_cards.pop(_qx95_key, None)

        token = uuid.uuid4().hex[:10]
        _g59_store(context)[token] = {
            "uid": uid, "chat_id": message.chat_id, "mode": mode or "",
            "ocr_ctx": source, "ts": time.time(),
        }
        if mode:
            title, body, keyboard = (
                "Quiz Count",
                f"Source: <b>{h(pretty)}</b>\nMode: <b>{h(mode.upper())}</b>\n\nকতটি unique quiz বানাব?",
                _g59_count_kb(token),
            )
        else:
            title, body, keyboard = (
                "Quiz Standard",
                f"Source: <b>{h(pretty)}</b>\n\nকোন admission standard-এ quiz বানাব?",
                _g59_mode_kb(token),
            )
        await message.reply_text(
            ui_box_html(title, body, emoji="🧠"), parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
        raise ApplicationHandlerStop

    count = max(1, min(500, int(count)))
    await _set(
        "Generating Quiz",
        f"Source: <b>{h(pretty)}</b>\n"
        f"Standard: <b>{h((mode or 'std').upper())}</b>\n"
        f"Count: <code>{count}</code>\n\n"
        "🧠 AI quiz তৈরি করছে… একটু অপেক্ষা করুন।",
        "⏳",
    )

    try:
        added, duplicates = await _generate_to_buffer_59(
            update, context, source, uid, count, mode or "std"
        )
    except Exception as error:
        await _set(
            "Generation Failed",
            f"{h(str(error)[:220])}\n\nএকই source-এ আবার reply করে চেষ্টা করুন।",
            "⚠️",
        )
        raise ApplicationHandlerStop

    total = 0
    with contextlib.suppress(Exception):
        total = int(buffer_count(uid))

    keyboard = await _qx95_result_kb(context, uid, message.chat_id) if added else None
    body = (
        f"Source: <b>{h(pretty)}</b>\n"
        f"Standard: <b>{h((mode or 'std').upper())}</b>\n"
        f"{QX94_ROW}\n"
        f"➕ Added: <b>{added}</b>\n"
        f"♻️ Duplicates skipped: <b>{duplicates}</b>\n"
        f"📦 Buffer total: <b>{total}</b>\n\n"
    )
    if added:
        body += (
            "📤 Export — <code>.done</code> (CSV)\n"
            "🧵 Topic publish — <code>.pt &lt;group#&gt; &lt;topic#&gt;</code>\n"
            "🔁 একই source-এ আবার command দিলে সম্পূর্ণ নতুন unique set তৈরি হবে।\n\n"
            + _qx95_channel_directory(uid)
        )
    else:
        body += "এই source থেকে নতুন unique quiz পাওয়া যায়নি। ভিন্ন source ব্যবহার করুন।"


    await _set("Quiz Ready" if added else "No New Quiz", body, "✅" if added else "ℹ️", keyboard)
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# User command sheet + native "/" menu (with buffer count)
# ─────────────────────────────────────────────────────────────────────────────
QX95_USER_COMMANDS_CARD = (
    "📜 <b>Your Command Sheet</b>\n"
    f"{QX94_ROW}\n"
    "<b>1 · Quiz generate</b> — source-এ <b>reply</b> করে\n"
    "<code>.gen 15</code> — standard জিজ্ঞেস করবে\n"
    "<code>.gen medical 15</code> · <code>.gen engineering 15</code> · "
    "<code>.gen versity 15</code>\n"
    "Source: forwarded quiz/poll · ছবি · যেকোনো text (1–500)\n\n"
    "<b>2 · Buffer &amp; export</b>\n"
    "<code>/buffercount</code> · <code>.bc</code> — কতটি জমা আছে\n"
    "<code>/buffer</code> — buffer card\n"
    "<code>.done</code> — CSV + JSON export\n"
    "<code>.clear</code> — buffer খালি\n\n"
    "<b>3 · Channel post</b>\n"
    "<code>/addchannel @channel</code> (bot-কে channel admin করুন)\n"
    "<code>/listchannels</code> · <code>/removechannel &lt;#&gt;</code>\n"
    "<code>.post &lt;channel#&gt;</code>\n\n"
    "<b>4 · Group &amp; forum topic</b>\n"
    "<code>.adg -100xxxxxxxxxx</code> — group যোগ\n"
    "<code>.info</code> — topic-এর thread id\n"
    "<code>.adtc &lt;group#&gt; &lt;thread_id&gt; Biology</code>\n"
    "<code>.listgroups</code> · <code>.listtopics</code> · "
    "<code>.pt &lt;group#&gt; &lt;topic#&gt;</code>\n\n"
    "<b>5 · Topic header / anchor</b>\n"
    "<code>.topic c1 pin</code> · <code>.aitopic c1 pin</code>\n"
    "<code>.mytopics</code> · <code>.usetopic &lt;id&gt;</code>\n"
    "<code>.topicpin</code> · <code>.topicunpin</code> · <code>.cleartopic</code>\n\n"
    "<b>6 · নিজের bot &amp; identity</b>\n"
    "<code>/addbot &lt;token&gt;</code> · <code>/mybot on|off</code> · "
    "<code>/removebot</code> · <code>/myid</code>\n\n"
    "<b>7 · সহায়তা</b>\n"
    "<code>/menu</code> · <code>.help কিভাবে channel এ post করব?</code>\n"
    f"{QX94_ROW}\n"
    "🔐 সব listing শুধু আপনার নিজের data দেখায়।"
)

globals()["QX93_COMMANDS_CARD"] = QX95_USER_COMMANDS_CARD
globals()["QX94_USER_COMMANDS_CARD"] = QX95_USER_COMMANDS_CARD

with contextlib.suppress(Exception):
    _qx95_menu = [item for item in QX94_USER_MENU_COMMANDS if item[0] != "commands"]
    _qx95_menu.insert(2, ("commands", "আমার সব command"))
    if not any(name == "buffercount" for name, _ in _qx95_menu):
        _qx95_menu.insert(4, ("buffercount", "Buffer-এ কতটি quiz"))
    QX94_USER_MENU_COMMANDS = _qx95_menu[:20]
    globals()["QX94_USER_MENU_COMMANDS"] = QX94_USER_MENU_COMMANDS


# ─────────────────────────────────────────────────────────────────────────────
# Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx95_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx95_prev_build_app() if callable(_qx95_prev_build_app) else None
    if app is None:
        return app

    def _dual(name, callback, group):
        register = globals().get("_register_dual_command")
        if callable(register):
            register(app, name, callback, group=group)
        else:
            app.add_handler(CommandHandler(name, callback), group=group)

    for command in ("start", "menu", "guide"):
        with contextlib.suppress(Exception):
            _dual(command, qx95_panel_router, -1013)
    with contextlib.suppress(Exception):
        _dual("help", qx95_panel_router_help, -1013)
    for command in ("cmd", "commands"):
        with contextlib.suppress(Exception):
            _dual(command, qx95_cmd_commands, -1013)
    for command in ("buffercount", "bc", "buffer", "b"):
        with contextlib.suppress(Exception):
            _dual(command, qx95_cmd_buffercount, -1013)
    with contextlib.suppress(Exception):
        _dual("gen", qx95_cmd_gen, -1013)
    with contextlib.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx95_owner_callback_shield, pattern=r"^qx94:"), group=-1029
        )


    _qx_log.info("[QUBIX-95] noise-free surface: dedupe, staff-noise mute, merged gen card.")
    return app


_qx_log.info("[SECTION 95] Qubix noise-free user surface loaded.")
