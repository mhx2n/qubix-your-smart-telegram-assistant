# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 93 — QUBIX WORKSPACE FINAL FIX (2026-08-03)
#
# Fixes reported in production:
#   1. Export CSV / Channels / Topics buttons replied "Unauthorized … staff
#      operations" because the scoped acting-owner context was never set on the
#      callback path (section 92 stops before the section-91 gate).
#      → A pre-gate now sets the scoped identity FIRST, on every update, on the
#        main bot and on every tenant bot.
#   2. Tenant (token-added) bots never answered / never generated, because the
#      main-bot-only gate from section 91 was cloned onto the child and consumed
#      every update.  → It is now marked main-only and the child gets its own
#      earliest-priority gate.
#   3. Users could not see which commands they own → full rich command sheet.
#   4. The inbox card now shows the running bot's own name/@username, the user's
#      ID, access mode, time left and exactly how to request access.
#   5. Channels / Groups / Topics / Buffer listings are rendered natively and
#      scoped to the user's own rows (never the owner's data).
# ══════════════════════════════════════════════════════════════════════════════

QX93_ROW = "<code>──────────────────────────</code>"


# ─────────────────────────────────────────────────────────────────────────────
# Identity helpers
# ─────────────────────────────────────────────────────────────────────────────
def _qx93_tenant_uid(context) -> int:
    try:
        return int(context.application.bot_data.get("qx_tenant_uid") or 0)
    except Exception:
        return 0


def _qx93_uid(update, context) -> int:
    tenant = _qx93_tenant_uid(context)
    if tenant:
        return tenant
    return int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)


def _qx93_privileged(update) -> bool:
    uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not uid:
        return False
    if _qx_real_owner(uid):
        return True
    return bool(_qx_prev_is_admin and _qx_prev_is_admin(uid))


async def _qx93_bot_label(context) -> str:
    """'Name · @username' of the bot the user is actually talking to."""
    data = getattr(getattr(context, "application", None), "bot_data", None)
    if isinstance(data, dict) and data.get("qx93_label"):
        return str(data["qx93_label"])
    label = "Qubix"
    with contextlib.suppress(Exception):
        me = await context.bot.get_me()
        name = str(getattr(me, "first_name", "") or "").strip()
        username = str(getattr(me, "username", "") or "").strip()
        label = name or "Qubix"
        if username:
            label = f"{label} · @{username}"
    if isinstance(data, dict):
        data["qx93_label"] = label
    return label


def _qx93_mode_badge(st: Dict[str, Any]) -> str:
    return {
        "owner": "👑 Owner",
        "approved": "✅ Approved · full access",
        "trial": "🧪 Trial",
    }.get(str(st.get("mode")), "🔒 Locked")


# ─────────────────────────────────────────────────────────────────────────────
# Scoped data helpers (own rows only — never the owner's)
# ─────────────────────────────────────────────────────────────────────────────
def _qx93_rows(sql: str, params: Tuple[Any, ...]) -> List[Any]:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            return list(conn.execute(sql, params).fetchall())
        finally:
            conn.close()
    return []


def _qx93_my_channels(uid: int) -> List[Any]:
    return _qx93_rows(
        "SELECT id, channel_chat_id, title FROM channels WHERE added_by=? ORDER BY id ASC",
        (int(uid),),
    )


def _qx93_my_groups(uid: int) -> List[Any]:
    return _qx93_rows(
        "SELECT id, group_chat_id, title FROM saved_groups WHERE added_by=? ORDER BY id ASC",
        (int(uid),),
    )


def _qx93_my_topics(uid: int) -> List[Any]:
    return _qx93_rows(
        "SELECT id, group_id, topic_name, thread_id FROM group_topics WHERE added_by=? ORDER BY id ASC",
        (int(uid),),
    )


def _qx93_my_anchors(uid: int) -> List[Any]:
    return _qx93_rows(
        "SELECT id, name, chat_id, msg_id FROM saved_topic_anchors WHERE admin_id=? ORDER BY id DESC",
        (int(uid),),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Rich cards
# ─────────────────────────────────────────────────────────────────────────────
def _qx93_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 Generate", callback_data="qx93:gen"),
            InlineKeyboardButton("📦 Buffer", callback_data="qx93:buffer"),
        ],
        [
            InlineKeyboardButton("📤 Export CSV", callback_data="qx93:export"),
            InlineKeyboardButton("📣 Channels", callback_data="qx93:channels"),
        ],
        [
            InlineKeyboardButton("🧵 Topics", callback_data="qx93:topics"),
            InlineKeyboardButton("👥 Groups", callback_data="qx93:groups"),
        ],
        [
            InlineKeyboardButton("📜 All Commands", callback_data="qx93:cmds"),
            InlineKeyboardButton("🪪 My Access", callback_data="qx93:access"),
        ],
        [
            InlineKeyboardButton("🤖 My Bot", callback_data="qx93:mybot"),
            InlineKeyboardButton("💬 Ask AI Help", callback_data="qx93:ask"),
        ],
    ])


def _qx93_back_kb(extra: Optional[List[List[InlineKeyboardButton]]] = None) -> InlineKeyboardMarkup:
    rows = list(extra or [])
    rows.append([InlineKeyboardButton("◀️ Menu", callback_data="qx93:menu")])
    return InlineKeyboardMarkup(rows)


async def _qx93_menu_text(update, context, uid: int, st: Dict[str, Any]) -> str:
    label = await _qx93_bot_label(context)
    name = getattr(getattr(update, "effective_user", None), "full_name", "") or "—"
    tenant = _qx93_tenant_uid(context)
    scope = "আপনার নিজের bot" if tenant else "Qubix workspace"
    return (
        f"🤖 <b>{h(label)}</b>\n"
        f"{QX93_ROW}\n"
        f"👤 <b>{h(name)}</b>\n"
        f"🆔 User ID: <code>{int(uid)}</code>\n"
        f"🔑 Access: {_qx93_mode_badge(st)}\n"
        f"⏳ Time left: <code>{h(_qx_human_left(st.get('remaining')))}</code>\n"
        f"📍 Workspace: <b>{h(scope)}</b> · inbox-only\n"
        f"{QX93_ROW}\n"
        "⚡️ <b>Quick start</b>\n"
        "একটি <b>poll / photo / PDF / text</b>-এ <b>reply</b> করে লিখুন:\n"
        "<code>.gen 15</code> · <code>.gen medical 15</code>\n"
        "<code>.gen engineering 15</code> · <code>.gen versity 15</code>\n\n"
        "📦 Buffer জমা হলে <code>.done</code> দিলে CSV + JSON,\n"
        "📣 <code>.post &lt;channel#&gt;</code> দিয়ে channel-এ, "
        "<code>.pt &lt;group#&gt; &lt;topic#&gt;</code> দিয়ে topic-এ post।\n\n"
        "💬 কিছু জানার থাকলে: <code>.help কিভাবে channel এ post করব?</code>"
    )


QX93_COMMANDS_CARD = (
    "📜 <b>Your Command Sheet</b>\n"
    f"{QX93_ROW}\n"
    "<b>1 · Quiz generate</b> (reply দিয়ে)\n"
    "<code>.gen 15</code> — source অনুযায়ী\n"
    "<code>.gen medical 15</code> · <code>.gen engineering 15</code> · "
    "<code>.gen versity 15</code>\n"
    "Poll/quiz forward, photo, PDF অথবা যেকোনো text — তিনটাতেই কাজ করে (1–500)।\n\n"
    "<b>2 · Buffer &amp; export</b>\n"
    "<code>/buffer</code> — কতটি জমা আছে\n"
    "<code>.done</code> — CSV + JSON export\n\n"
    "<b>3 · Channel</b>\n"
    "<code>/addchannel @channel</code> (আগে bot-কে channel admin করুন)\n"
    "<code>/listchannels</code> · <code>/removechannel &lt;#&gt;</code>\n"
    "<code>.post &lt;channel#&gt;</code>\n\n"
    "<b>4 · Group &amp; forum topic</b>\n"
    "<code>.adg -100xxxxxxxxxx</code> — group যোগ\n"
    "<code>.info</code> — topic-এর ভিতরে thread id\n"
    "<code>.adtc &lt;group#&gt; &lt;thread_id&gt; Biology</code>\n"
    "<code>.listgroups</code> · <code>.listtopics</code> · "
    "<code>.pt &lt;group#&gt; &lt;topic#&gt;</code>\n\n"
    "<b>5 · Topic header / anchor</b>\n"
    "<code>.topic c1 pin</code> · <code>.aitopic c1 pin</code>\n"
    "<code>.mytopics</code> · <code>.usetopic &lt;id&gt;</code>\n"
    "<code>.topicpin</code> · <code>.topicunpin</code> · <code>.cleartopic</code>\n\n"
    "<b>6 · Own bot &amp; identity</b>\n"
    "<code>/addbot &lt;token&gt;</code> — নিজের নামের bot চালু\n"
    "<code>/mybot</code> · <code>/mybot on</code> · <code>/mybot off</code> · "
    "<code>/removebot</code>\n"
    "<code>/myid</code> · <code>/menu</code> · <code>.help &lt;প্রশ্ন&gt;</code>\n"
    f"{QX93_ROW}\n"
    "🔐 সব listing শুধুমাত্র আপনার নিজের data দেখায়।"
)


def _qx93_access_card(uid: int, name: str, st: Dict[str, Any], label: str) -> str:
    lines = [
        "🪪 <b>Access &amp; Identity</b>",
        QX93_ROW,
        f"🤖 Bot: <b>{h(label)}</b>",
        f"👤 Name: {h(name or '—')}",
        f"🆔 User ID: <code>{int(uid)}</code>",
        f"🔑 Access: {_qx93_mode_badge(st)}",
        f"⏳ Time left: <code>{h(_qx_human_left(st.get('remaining')))}</code>",
        QX93_ROW,
    ]
    if st.get("mode") in ("approved", "owner"):
        lines.append("✅ আপনার access পূর্ণ — unlimited generation চালু।")
    else:
        lines.append(
            "🧪 এটি trial access। পূর্ণ access নিতে উপরের <b>User ID</b> কপি করে "
            f"owner-কে পাঠান: {h(QX_OWNER_CONTACT)}"
        )
    lines.append("<i>Approved হলে সাথে সাথেই unlimited হয়ে যাবে, কিছু করতে হবে না।</i>")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Pre-gate: scoped acting-owner for EVERY update (main + tenant)
# ─────────────────────────────────────────────────────────────────────────────
async def qx93_pre_gate(update, context):
    """Runs before every other handler; never blocks, only scopes identity."""
    if _qx93_privileged(update):
        return
    uid = _qx93_uid(update, context)
    if not uid:
        return
    tenant = _qx93_tenant_uid(context)
    if tenant:
        actor = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
        if actor and actor != tenant:
            return
    st = _qx_access(uid)
    if not st.get("ok"):
        return
    _QX_ACTING_OWNER.set(int(uid))
    with contextlib.suppress(Exception):
        context.application.bot_data["qx_last_active"] = time.time()


# ─────────────────────────────────────────────────────────────────────────────
# Native, scoped listings
# ─────────────────────────────────────────────────────────────────────────────
def _qx93_channels_card(uid: int) -> str:
    rows = _qx93_my_channels(uid)
    if not rows:
        return (
            "📣 <b>Your Channels</b>\n" + QX93_ROW + "\n"
            "<i>এখনো কোনো channel যোগ করা হয়নি।</i>\n\n"
            "<b>যোগ করবেন যেভাবে</b>\n"
            "1️⃣ এই bot-কে আপনার channel-এ <b>admin</b> করুন\n"
            "2️⃣ এখানে লিখুন <code>/addchannel @yourchannel</code>\n"
            "3️⃣ <code>/listchannels</code> → <code>.post &lt;channel#&gt;</code>"
        )
    body = [f"📣 <b>Your Channels</b>", QX93_ROW]
    for row in rows:
        body.append(
            f"<b>#{int(row['id'])}</b> · {h(str(row['title'] or '—'))}\n"
            f"   Chat: <code>{h(str(row['channel_chat_id']))}</code>"
        )
    body += [QX93_ROW, "Post করতে: <code>.post &lt;channel#&gt;</code> · "
             "সরাতে: <code>/removechannel &lt;#&gt;</code>"]
    return "\n".join(body)


def _qx93_groups_card(uid: int) -> str:
    rows = _qx93_my_groups(uid)
    if not rows:
        return (
            "👥 <b>Your Groups</b>\n" + QX93_ROW + "\n"
            "<i>কোনো group যোগ করা হয়নি।</i>\n\n"
            "1️⃣ bot-কে group-এ admin করুন\n"
            "2️⃣ inbox-এ <code>.adg -100xxxxxxxxxx</code>\n"
            "3️⃣ topic-এর ভিতরে <code>.info</code> দিয়ে thread id নিয়ে "
            "<code>.adtc &lt;group#&gt; &lt;thread_id&gt; Biology</code>"
        )
    body = ["👥 <b>Your Groups</b>", QX93_ROW]
    for row in rows:
        body.append(
            f"<b>#{int(row['id'])}</b> · {h(str(row['title'] or '—'))}\n"
            f"   Chat: <code>{h(str(row['group_chat_id']))}</code>"
        )
    body += [QX93_ROW, "Topic যোগ: <code>.adtc &lt;group#&gt; &lt;thread_id&gt; &lt;name&gt;</code>"]
    return "\n".join(body)


def _qx93_topics_card(uid: int) -> str:
    topics = _qx93_my_topics(uid)
    anchors = _qx93_my_anchors(uid)
    body = ["🧵 <b>Your Topics</b>", QX93_ROW]
    if topics:
        body.append("<b>Forum topics</b>")
        for row in topics:
            body.append(
                f"<b>#{int(row['id'])}</b> · {h(str(row['topic_name'] or '—'))} · "
                f"group <code>{int(row['group_id'] or 0)}</code> · "
                f"thread <code>{int(row['thread_id'] or 0)}</code>"
            )
    else:
        body.append("<i>কোনো forum topic নেই — <code>.adtc</code> দিয়ে যোগ করুন।</i>")
    body.append("")
    if anchors:
        body.append("<b>Saved topic anchors</b>")
        for row in anchors[:12]:
            body.append(f"<code>{int(row['id'])}</code> · {h(str(row['name'] or '—'))}")
    else:
        body.append("<i>কোনো saved anchor নেই — text/media reply করে <code>.topic c1 pin</code>।</i>")
    body += [
        QX93_ROW,
        "<code>.topic c1 pin</code> · <code>.aitopic c1 pin</code> · "
        "<code>.usetopic &lt;id&gt;</code>\n"
        "<code>.topicpin</code> · <code>.topicunpin</code> · <code>.cleartopic</code>\n"
        "Post: <code>.pt &lt;group#&gt; &lt;topic#&gt;</code>",
    ]
    return "\n".join(body)


def _qx93_buffer_card(uid: int) -> str:
    total = 0
    with contextlib.suppress(Exception):
        total = int(buffer_count(uid))
    return (
        "📦 <b>Buffer</b>\n" + QX93_ROW + "\n"
        f"Ready quiz: <code>{total}</code>\n\n"
        + ("Export করতে <code>.done</code> দিন — CSV + JSON পাবেন।"
           if total else
           "একটি poll / photo / text-এ reply করে <code>.gen 15</code> দিন।")
    )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy invocation with scoped identity (fixes "Unauthorized")
# ─────────────────────────────────────────────────────────────────────────────
class _Qx93Shim:
    def __init__(self, update):
        message = getattr(getattr(update, "callback_query", None), "message", None) or \
            getattr(update, "effective_message", None)
        self.message = message
        self.effective_message = message
        self.effective_chat = getattr(message, "chat", None)
        self.effective_user = getattr(update, "effective_user", None)
        self.callback_query = None
        self.edited_message = None
        self.channel_post = None
        self.poll = None
        self.update_id = int(getattr(update, "update_id", 0) or 0)


async def _qx93_invoke(name: str, update, context, uid: int, args=None) -> bool:
    fn = globals().get(name)
    if not callable(fn):
        return False
    prev = list(getattr(context, "args", []) or [])
    _QX_ACTING_OWNER.set(int(uid))
    try:
        context.args = list(args or [])
        await fn(_Qx93Shim(update), context)
        return True
    except ApplicationHandlerStop:
        return True
    except Exception as error:
        _qx_log.warning("[QUBIX-93] %s failed: %s", name, error)
        return False
    finally:
        with contextlib.suppress(Exception):
            context.args = prev


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────
async def qx93_cmd_menu(update, context):
    message = getattr(update, "effective_message", None)
    if message is None:
        raise ApplicationHandlerStop
    uid = _qx93_uid(update, context)
    st = _qx_access(uid)
    if not st.get("ok"):
        await message.reply_text(
            _qx_expired_card(uid, getattr(update.effective_user, "full_name", "")),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    question = " ".join(list(getattr(context, "args", []) or [])).strip()
    if question:
        thinking = await message.reply_text(
            ui_box_html("Qubix Assistant", "উত্তর তৈরি হচ্ছে…", emoji="💬"),
            parse_mode=ParseMode.HTML,
        )
        answer = ""
        helper = globals().get("_qx92_ai_help")
        if callable(helper):
            answer = await helper(question)
        body = answer or "এই মুহূর্তে AI উত্তর দিতে পারছে না। নিচের command sheet দেখুন।"
        with contextlib.suppress(Exception):
            await thinking.edit_text(
                "💬 <b>Qubix Assistant</b>\n" + QX93_ROW + "\n" + body,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx93_menu_kb(),
                disable_web_page_preview=True,
            )
        raise ApplicationHandlerStop

    await message.reply_text(
        await _qx93_menu_text(update, context, uid, st),
        parse_mode=ParseMode.HTML,
        reply_markup=_qx93_menu_kb(),
        disable_web_page_preview=True,
    )
    raise ApplicationHandlerStop


async def qx93_cmd_commands(update, context):
    uid = _qx93_uid(update, context)
    st = _qx_access(uid)
    message = update.effective_message
    if not st.get("ok"):
        await message.reply_text(
            _qx_expired_card(uid, getattr(update.effective_user, "full_name", "")),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop
    await message.reply_text(
        QX93_COMMANDS_CARD,
        parse_mode=ParseMode.HTML,
        reply_markup=_qx93_menu_kb(),
        disable_web_page_preview=True,
    )
    raise ApplicationHandlerStop


async def qx93_cmd_channels(update, context):
    if _qx93_privileged(update):
        return
    uid = _qx93_uid(update, context)
    await update.effective_message.reply_text(
        _qx93_channels_card(uid), parse_mode=ParseMode.HTML, reply_markup=_qx93_back_kb()
    )
    raise ApplicationHandlerStop


async def qx93_cmd_groups(update, context):
    if _qx93_privileged(update):
        return
    uid = _qx93_uid(update, context)
    await update.effective_message.reply_text(
        _qx93_groups_card(uid), parse_mode=ParseMode.HTML, reply_markup=_qx93_back_kb()
    )
    raise ApplicationHandlerStop


async def qx93_cmd_topics(update, context):
    if _qx93_privileged(update):
        return
    uid = _qx93_uid(update, context)
    await update.effective_message.reply_text(
        _qx93_topics_card(uid), parse_mode=ParseMode.HTML, reply_markup=_qx93_back_kb()
    )
    raise ApplicationHandlerStop


async def qx93_cmd_buffer(update, context):
    if _qx93_privileged(update):
        return
    uid = _qx93_uid(update, context)
    await update.effective_message.reply_text(
        _qx93_buffer_card(uid), parse_mode=ParseMode.HTML, reply_markup=_qx93_back_kb()
    )
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────────────────────────────────────
async def qx93_on_callback(update, context):
    query = update.callback_query
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("qx93:"):
        return
    action = data.split(":", 1)[1] or "menu"
    uid = _qx93_uid(update, context)
    st = _qx_access(uid)
    with contextlib.suppress(Exception):
        await query.answer()

    if not st.get("ok"):
        with contextlib.suppress(Exception):
            await query.edit_message_text(
                _qx_expired_card(uid, getattr(update.effective_user, "full_name", "")),
                parse_mode=ParseMode.HTML,
            )
        raise ApplicationHandlerStop

    _QX_ACTING_OWNER.set(int(uid))

    async def _card(text_html: str):
        with contextlib.suppress(Exception):
            await query.edit_message_text(
                text_html,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx93_back_kb(),
                disable_web_page_preview=True,
            )

    if action == "menu":
        with contextlib.suppress(Exception):
            await query.edit_message_text(
                await _qx93_menu_text(update, context, uid, st),
                parse_mode=ParseMode.HTML,
                reply_markup=_qx93_menu_kb(),
                disable_web_page_preview=True,
            )
    elif action == "gen":
        await _card(globals().get("QX_HOW_GEN") or QX93_COMMANDS_CARD)
    elif action == "cmds":
        await _card(QX93_COMMANDS_CARD)
    elif action == "buffer":
        await _card(_qx93_buffer_card(uid))
    elif action == "channels":
        await _card(_qx93_channels_card(uid))
    elif action == "groups":
        await _card(_qx93_groups_card(uid))
    elif action == "topics":
        await _card(_qx93_topics_card(uid))
    elif action == "access":
        await _card(_qx93_access_card(
            uid,
            getattr(getattr(update, "effective_user", None), "full_name", ""),
            st,
            await _qx93_bot_label(context),
        ))
    elif action == "export":
        total = 0
        with contextlib.suppress(Exception):
            total = int(buffer_count(uid))
        if not total:
            await _card(
                "📤 <b>Export</b>\n" + QX93_ROW + "\n"
                "Buffer খালি। আগে <code>.gen 15</code> দিয়ে quiz বানান, "
                "তারপর <code>.done</code> দিলে CSV + JSON পাবেন।"
            )
        else:
            with contextlib.suppress(Exception):
                await query.edit_message_text(
                    "📤 <b>Export চলছে…</b>\n" + QX93_ROW + f"\n{total} টি quiz প্যাক করা হচ্ছে।",
                    parse_mode=ParseMode.HTML,
                )
            if not await _qx93_invoke("cmd_done", update, context, uid):
                await _card(
                    "📤 <b>Export</b>\n" + QX93_ROW + "\n"
                    "Export করতে লিখুন <code>.done</code> — CSV + JSON পাবেন।"
                )
    elif action == "mybot":
        if not await _qx93_invoke("qx_cmd_mybot", update, context, uid):
            await _card(
                "🤖 <b>Personal Bot</b>\n" + QX93_ROW + "\n"
                "<code>/addbot &lt;token&gt;</code> দিলে আপনার নিজের নামের bot-এ "
                "ঠিক এই workspace চলবে।\n"
                "<code>/mybot on</code> · <code>/mybot off</code> · <code>/removebot</code>"
            )
    elif action == "ask":
        await _card(
            "💬 <b>Ask AI Help</b>\n" + QX93_ROW + "\n"
            "প্রশ্নটি এভাবে লিখুন:\n"
            "<code>.help কিভাবে channel এ quiz post করব?</code>\n"
            "<code>.help topic pin কিভাবে করে?</code>\n\n"
            "শুধু আপনার জন্য বরাদ্দ ফিচার নিয়েই উত্তর দেওয়া হবে।"
        )
    else:
        await _card(QX93_COMMANDS_CARD)
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# Tenant runtime hardening
# ─────────────────────────────────────────────────────────────────────────────
async def qx93_child_pre_gate(update, context):
    """Earliest gate on a tenant bot: scope identity, keep it awake."""
    app = context.application
    tenant = int(app.bot_data.get("qx_tenant_uid") or 0)
    actor = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not tenant:
        return
    if actor and actor != tenant:
        callback = getattr(update, "callback_query", None)
        if callback:
            with contextlib.suppress(Exception):
                await callback.answer("This personal bot is private.", show_alert=True)
        else:
            with contextlib.suppress(Exception):
                await update.effective_message.reply_text(
                    "🔒 এই bot টি ব্যক্তিগত। নিজের bot চালাতে Qubix ব্যবহার করুন।"
                )
        raise ApplicationHandlerStop
    st = _qx_access(tenant)
    if not st.get("ok"):
        with contextlib.suppress(Exception):
            await update.effective_message.reply_text(
                _qx_expired_card(tenant, app.bot_data.get("qx_tenant_name", "")),
                parse_mode=ParseMode.HTML,
            )
        asyncio.create_task(_qx_stop_runner(tenant, reason="access expired"))
        raise ApplicationHandlerStop
    _QX_ACTING_OWNER.set(tenant)
    app.bot_data["qx_last_active"] = time.time()


_qx93_runner_start = QxRunner.start


async def _qx93_start(self):
    ok_started, info = await _qx93_runner_start(self)
    if ok_started and self.app is not None:
        with contextlib.suppress(Exception):
            self.app.add_handler(
                MessageHandler(filters.ALL, qx93_child_pre_gate), group=-2000
            )
            self.app.add_handler(
                CallbackQueryHandler(qx93_child_pre_gate), group=-2000
            )
        with contextlib.suppress(Exception):
            label = self.username or self.name or "Your Bot"
            self.app.bot_data["qx93_label"] = f"{label} · @{self.username}" if self.username else label
    return ok_started, info


QxRunner.start = _qx93_start


# ─────────────────────────────────────────────────────────────────────────────
# Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx93_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx93_prev_build_app() if callable(_qx93_prev_build_app) else None
    if app is None:
        return app

    def _dual(name, callback, group):
        register = globals().get("_register_dual_command")
        if callable(register):
            register(app, name, callback, group=group)
        else:
            app.add_handler(CommandHandler(name, callback), group=group)

    # 1) The main-bot-only gate from section 91 must never reach a tenant bot.
    marker = globals().get("_qx_mark")
    with contextlib.suppress(Exception):
        for _group, handlers in list(app.handlers.items()):
            for handler in handlers:
                cb = getattr(handler, "callback", None)
                if cb is globals().get("qx91_main_gate") and callable(marker):
                    marker(handler)

    # 2) Identity pre-gate runs before every legacy handler (main + cloned).
    with contextlib.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx93_pre_gate), group=-1030)
        app.add_handler(CallbackQueryHandler(qx93_pre_gate), group=-1030)

    # 3) Rich workspace UI + native scoped listings.
    with contextlib.suppress(Exception):
        app.add_handler(CallbackQueryHandler(qx93_on_callback, pattern=r"^qx93:"), group=-1025)

    for command in ("start", "menu", "help", "guide"):
        with contextlib.suppress(Exception):
            _dual(command, qx93_cmd_menu, -1000)
    for command in ("cmd", "commands"):
        with contextlib.suppress(Exception):
            _dual(command, qx93_cmd_commands, -1000)
    for command, callback in (
        ("listchannels", qx93_cmd_channels),
        ("channels", qx93_cmd_channels),
        ("listgroups", qx93_cmd_groups),
        ("groups", qx93_cmd_groups),
        ("listtopics", qx93_cmd_topics),
        ("topics", qx93_cmd_topics),
        ("buffer", qx93_cmd_buffer),
    ):
        with contextlib.suppress(Exception):
            _dual(command, callback, -1000)

    _qx_log.info("[QUBIX-93] workspace fix wired: scoped identity, rich UI, tenant gate.")
    return app


_qx_log.info("[SECTION 93] Qubix final workspace fix loaded.")
