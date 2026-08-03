# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 94 — QUBIX OWNER/USER PANEL SPLIT + CLEAN INBOX UI (2026-08-03)
#
#   1. Owner panel and user panel are now fully separate surfaces.
#      Owner sees access-granting + every control command; a user sees ONLY the
#      commands allocated to them — nothing more, anywhere.
#   2. Telegram's native command menu (the "/" menu) is synced per chat:
#      owner chat gets the owner sheet, user chats (main bot AND every
#      token-added personal bot) get the user sheet only.
#   3. Clean inbox: a workspace command deletes the user's command message and
#      the previous workspace card, then posts one fresh card. No pile-up.
#   4. "PDF থেকে quiz" wording removed from every user-facing card.
# ══════════════════════════════════════════════════════════════════════════════

from telegram import BotCommand, BotCommandScopeChat

QX94_ROW = globals().get("QX93_ROW") or "<code>──────────────────────────</code>"


# ─────────────────────────────────────────────────────────────────────────────
# Command sheets
# ─────────────────────────────────────────────────────────────────────────────
QX94_USER_MENU_COMMANDS: List[Tuple[str, str]] = [
    ("start", "Workspace menu"),
    ("menu", "Workspace menu"),
    ("commands", "আমার সব command"),
    ("buffer", "Buffer কতটি quiz"),
    ("done", "CSV + JSON export"),
    ("addchannel", "Channel যোগ করুন"),
    ("listchannels", "আমার channel list"),
    ("removechannel", "Channel সরান"),
    ("post", "Channel-এ post"),
    ("listgroups", "আমার group list"),
    ("listtopics", "আমার topic list"),
    ("addbot", "নিজের bot token যোগ"),
    ("mybot", "নিজের bot on/off"),
    ("removebot", "নিজের bot সরান"),
    ("myid", "আমার User ID"),
    ("help", "AI সহায়তা"),
]

QX94_OWNER_MENU_COMMANDS: List[Tuple[str, str]] = [
    ("start", "Owner control panel"),
    ("menu", "Owner control panel"),
    ("qapprove", "User-কে full access দিন"),
    ("qrevoke", "Access + token বাতিল"),
    ("qtrial", "Trial সময় সেট (minutes)"),
    ("qbots", "সব tenant bot দেখুন"),
    ("qkill", "কোনো tenant bot বন্ধ"),
    ("adminpanel", "Admin stats"),
    ("logs", "System logs"),
    ("status", "System status"),
    ("broadcast", "Broadcast message"),
    ("buffer", "Buffer"),
    ("done", "Export"),
    ("listchannels", "Channels"),
    ("commands", "Full owner command sheet"),
]

QX94_USER_COMMANDS_CARD = (
    "📜 <b>Your Command Sheet</b>\n"
    f"{QX94_ROW}\n"
    "<b>1 · Quiz generate</b> (reply দিয়ে)\n"
    "<code>.gen 15</code> — source অনুযায়ী\n"
    "<code>.gen medical 15</code> · <code>.gen engineering 15</code> · "
    "<code>.gen versity 15</code>\n"
    "Poll/quiz forward, photo অথবা যেকোনো text — তিনটাতেই কাজ করে (1–500)।\n\n"
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
    "<code>/addbot &lt;token&gt;</code> · <code>/mybot on|off</code> · "
    "<code>/removebot</code> · <code>/myid</code>\n\n"
    "<b>7 · সহায়তা</b>\n"
    "<code>.help কিভাবে channel এ post করব?</code>\n"
    f"{QX94_ROW}\n"
    "🔐 শুধু আপনার নিজের buffer, channel, group ও topic দেখা/ব্যবহার হয়।"
)

QX94_HOW_GEN = (
    "🧠 <b>Quiz Generation</b>\n"
    f"{QX94_ROW}\n"
    "<b>1 · Poll / Quiz থেকে</b>\n"
    "যেকোনো quiz/poll forward করুন → সেটিতে <b>reply</b> করে <code>.gen 20</code>\n\n"
    "<b>2 · ছবি থেকে</b>\n"
    "ছবি পাঠান → ছবিতে reply করে <code>.gen 20</code>\n\n"
    "<b>3 · Text topic থেকে</b>\n"
    "যেকোনো topic লিখুন → সেটিতে reply করে <code>.gen 20</code>\n\n"
    "<b>Standard</b>\n"
    "<code>.gen medical 15</code> · <code>.gen engineering 15</code> · "
    "<code>.gen versity 15</code> · <code>.gen 15</code>\n\n"
    "একই source-এ আবার command দিলে আরও <b>unique</b> quiz তৈরি হবে (1–500)।"
)

globals()["QX93_COMMANDS_CARD"] = QX94_USER_COMMANDS_CARD
globals()["QX_HOW_GEN"] = QX94_HOW_GEN


QX94_OWNER_CARD = (
    "👑 <b>Qubix — Owner Control Panel</b>\n"
    f"{QX94_ROW}\n"
    "<b>1 · Access management</b>\n"
    "<code>/qapprove &lt;user_id&gt; [days]</code> — full access (days না দিলে unlimited)\n"
    "<code>/qrevoke &lt;user_id&gt;</code> — access + saved token বাতিল\n"
    "<code>/qtrial &lt;minutes&gt;</code> — প্রতি user-এর trial সময়\n"
    "<code>/qbots</code> — সব tenant bot ও তাদের access\n"
    "<code>/qkill &lt;user_id&gt;</code> — কোনো tenant bot বন্ধ\n\n"
    "<b>2 · Staff &amp; system</b>\n"
    "<code>/adminpanel</code> · <code>/status</code> · <code>/logs</code> · "
    "<code>/dashboard</code>\n"
    "<code>/broadcast</code> · <code>/ask</code> · <code>/reply</code> · "
    "<code>/banned</code>\n\n"
    "<b>3 · Quiz &amp; publishing (full)</b>\n"
    "<code>.gen</code> · <code>/buffer</code> · <code>/buffercount</code> · "
    "<code>.done</code> · <code>/clear</code>\n"
    "<code>/addchannel</code> · <code>/listchannels</code> · <code>.post</code> · "
    "<code>.adg</code> · <code>.adtc</code> · <code>.pt</code>\n"
    "<code>.topic</code> · <code>.aitopic</code> · <code>.topicpin</code> · "
    "<code>.topicunpin</code> · <code>.linktopic</code>\n"
    "<code>.setprefix</code> · <code>.setexplink</code> · <code>.exo</code>/"
    "<code>.exf</code> · <code>.score</code> · <code>.stopquiz</code>/"
    "<code>.resumequiz</code>\n\n"
    "<b>4 · কিভাবে কাউকে access দিবেন</b>\n"
    "1️⃣ user আপনাকে তার <b>User ID</b> পাঠাবে (<code>/myid</code>)\n"
    "2️⃣ আপনি লিখবেন <code>/qapprove 123456789 30</code>\n"
    "3️⃣ user <code>/addbot &lt;token&gt;</code> → <code>/mybot on</code>\n"
    f"{QX94_ROW}\n"
    "🧪 Approve না করলে user শুধু trial সময় পর্যন্ত ব্যবহার করতে পারবে।"
)


def _qx94_owner_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤖 Tenant Bots", callback_data="qx94:bots"),
            InlineKeyboardButton("⏳ Trial Time", callback_data="qx94:trial"),
        ],
        [
            InlineKeyboardButton("🔑 Access How-to", callback_data="qx94:access"),
            InlineKeyboardButton("📜 Owner Commands", callback_data="qx94:cmds"),
        ],
    ])


QX94_OWNER_ACCESS_HOWTO = (
    "🔑 <b>Access দেওয়ার নিয়ম</b>\n"
    f"{QX94_ROW}\n"
    "<code>/qapprove &lt;user_id&gt;</code> — unlimited access\n"
    "<code>/qapprove &lt;user_id&gt; 30</code> — ৩০ দিনের access\n"
    "<code>/qrevoke &lt;user_id&gt;</code> — access ও token বাতিল\n"
    "<code>/qtrial 20</code> — নতুন user-দের trial ২০ মিনিট\n\n"
    "Approve করার সাথে সাথেই user-এর কাছে notification যাবে এবং তার "
    "trial token স্থায়ীভাবে সেভ হয়ে যাবে।"
)


# ─────────────────────────────────────────────────────────────────────────────
# Clean-inbox card sender
# ─────────────────────────────────────────────────────────────────────────────
async def _qx94_clean_send(update, context, text: str, kb=None):
    """Delete the command message + previous card, then post one fresh card."""
    message = getattr(update, "effective_message", None)
    chat = getattr(update, "effective_chat", None)
    if message is None or chat is None:
        return None

    with contextlib.suppress(Exception):
        await message.delete()

    store = getattr(context, "chat_data", None)
    if isinstance(store, dict):
        old = store.get("qx94_card_id")
        if old:
            with contextlib.suppress(Exception):
                await context.bot.delete_message(chat_id=chat.id, message_id=int(old))

    sent = None
    with contextlib.suppress(Exception):
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
    if sent is not None and isinstance(store, dict):
        store["qx94_card_id"] = int(sent.message_id)
    return sent


# ─────────────────────────────────────────────────────────────────────────────
# Native "/" command menu sync — owner sheet vs user sheet
# ─────────────────────────────────────────────────────────────────────────────
def _qx94_bot_commands(owner: bool) -> List[BotCommand]:
    source = QX94_OWNER_MENU_COMMANDS if owner else QX94_USER_MENU_COMMANDS
    out: List[BotCommand] = []
    for name, desc in source:
        with contextlib.suppress(Exception):
            out.append(BotCommand(name, desc[:256]))
    return out


async def _qx94_sync_menu(context, chat_id: int, owner: bool) -> None:
    data = getattr(getattr(context, "application", None), "bot_data", None)
    if not isinstance(data, dict):
        return
    seen = data.setdefault("qx94_menu_synced", {})
    want = "owner" if owner else "user"
    if seen.get(chat_id) == want:
        return
    seen[chat_id] = want
    with contextlib.suppress(Exception):
        await context.bot.set_my_commands(
            _qx94_bot_commands(owner), scope=BotCommandScopeChat(chat_id=chat_id)
        )


async def qx94_menu_sync_gate(update, context):
    """Never blocks. Keeps the per-chat '/' menu correct for owner vs user."""
    chat = getattr(update, "effective_chat", None)
    if chat is None or str(getattr(chat, "type", "")) != "private":
        return
    tenant = 0
    with contextlib.suppress(Exception):
        tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
    owner = False if tenant else bool(_qx93_privileged(update))
    with contextlib.suppress(Exception):
        await _qx94_sync_menu(context, int(chat.id), owner)


# ─────────────────────────────────────────────────────────────────────────────
# Owner panel commands (main bot only)
# ─────────────────────────────────────────────────────────────────────────────
async def qx94_owner_menu(update, context):
    if not _qx93_privileged(update):
        return                      # fall through to the user workspace panel
    tenant = 0
    with contextlib.suppress(Exception):
        tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
    if tenant:
        return
    await _qx94_clean_send(update, context, QX94_OWNER_CARD, _qx94_owner_kb())
    raise ApplicationHandlerStop


async def qx94_on_callback(update, context):
    query = update.callback_query
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("qx94:"):
        return
    with contextlib.suppress(Exception):
        await query.answer()
    if not _qx93_privileged(update):
        with contextlib.suppress(Exception):
            await query.answer("Owner only.", show_alert=True)
        raise ApplicationHandlerStop

    action = data.split(":", 1)[1] or "cmds"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Owner Panel", callback_data="qx94:panel")]])

    if action == "panel":
        text, kb = QX94_OWNER_CARD, _qx94_owner_kb()
    elif action == "cmds":
        text = QX94_OWNER_CARD
    elif action == "access":
        text = QX94_OWNER_ACCESS_HOWTO
    elif action == "trial":
        minutes = 0
        with contextlib.suppress(Exception):
            minutes = int(_qx_trial_seconds() // 60)
        text = (
            "⏳ <b>Trial Setting</b>\n" + QX94_ROW + "\n"
            f"বর্তমান trial: <b>{minutes} মিনিট / user</b>\n\n"
            "পরিবর্তন করতে: <code>/qtrial 20</code>"
        )
    elif action == "bots":
        rows = []
        with contextlib.suppress(Exception):
            rows = _qx_all_saved_bots()
        lines = ["🤖 <b>Tenant Bots</b>", QX94_ROW]
        if rows:
            for row in rows:
                uid = int(row["user_id"])
                st = _qx_access(uid)
                lines.append(
                    f"<code>{uid}</code> · @{h(str(row['username'] or '—'))} · "
                    f"{h(str(st.get('mode')))} · {h(_qx_human_left(st.get('remaining')))}"
                )
        else:
            lines.append("<i>কোনো saved tenant bot নেই।</i>")
        lines += [QX94_ROW, "বিস্তারিত: <code>/qbots</code> · বন্ধ: <code>/qkill &lt;user_id&gt;</code>"]
        text = "\n".join(lines)
    else:
        text = QX94_OWNER_CARD

    with contextlib.suppress(Exception):
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True
        )
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# User panel — same cards, but clean-sent (old message removed)
# ─────────────────────────────────────────────────────────────────────────────
async def _qx94_user_menu_text(update, context, uid: int, st) -> str:
    label = await _qx93_bot_label(context)
    name = getattr(getattr(update, "effective_user", None), "full_name", "") or "—"
    tenant = 0
    with contextlib.suppress(Exception):
        tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
    scope = "আপনার নিজের bot" if tenant else "Qubix workspace"
    return (
        f"🤖 <b>{h(label)}</b>\n"
        f"{QX94_ROW}\n"
        f"👤 <b>{h(name)}</b>\n"
        f"🆔 User ID: <code>{int(uid)}</code>\n"
        f"🔑 Access: {_qx93_mode_badge(st)}\n"
        f"⏳ Time left: <code>{h(_qx_human_left(st.get('remaining')))}</code>\n"
        f"📍 Workspace: <b>{h(scope)}</b> · inbox-only\n"
        f"{QX94_ROW}\n"
        "⚡️ <b>Quick start</b>\n"
        "একটি <b>poll / photo / text</b>-এ <b>reply</b> করে লিখুন:\n"
        "<code>.gen 15</code> · <code>.gen medical 15</code>\n"
        "<code>.gen engineering 15</code> · <code>.gen versity 15</code>\n\n"
        "📦 Buffer জমা হলে <code>.done</code> দিলে CSV + JSON,\n"
        "📣 <code>.post &lt;channel#&gt;</code> দিয়ে channel-এ, "
        "<code>.pt &lt;group#&gt; &lt;topic#&gt;</code> দিয়ে topic-এ post।\n\n"
        "💬 কিছু জানার থাকলে: <code>.help কিভাবে channel এ post করব?</code>\n"
        f"{QX94_ROW}\n"
        "📜 সব command দেখতে নিচের <b>All Commands</b> button।"
    )


globals()["_qx93_menu_text"] = _qx94_user_menu_text


async def _qx94_user_guard(update, context, uid: int) -> bool:
    st = _qx_access(uid)
    if st.get("ok"):
        return True
    await _qx94_clean_send(
        update,
        context,
        _qx_expired_card(uid, getattr(getattr(update, "effective_user", None), "full_name", "")),
    )
    return False


async def qx94_user_menu(update, context):
    if _qx93_privileged(update):
        tenant = 0
        with contextlib.suppress(Exception):
            tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
        if not tenant:
            return
    uid = _qx93_uid(update, context)
    question = " ".join(list(getattr(context, "args", []) or [])).strip()
    if question:
        return                       # `.help <question>` → section 93 AI path
    if not await _qx94_user_guard(update, context, uid):
        raise ApplicationHandlerStop
    st = _qx_access(uid)
    await _qx94_clean_send(
        update, context,
        await _qx94_user_menu_text(update, context, uid, st),
        _qx93_menu_kb(),
    )
    raise ApplicationHandlerStop


async def qx94_user_commands(update, context):
    if _qx93_privileged(update):
        tenant = 0
        with contextlib.suppress(Exception):
            tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
        if not tenant:
            await _qx94_clean_send(update, context, QX94_OWNER_CARD, _qx94_owner_kb())
            raise ApplicationHandlerStop
    uid = _qx93_uid(update, context)
    if not await _qx94_user_guard(update, context, uid):
        raise ApplicationHandlerStop
    await _qx94_clean_send(update, context, QX94_USER_COMMANDS_CARD, _qx93_menu_kb())
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# Tenant bots: user-only "/" menu + clean UI
# ─────────────────────────────────────────────────────────────────────────────
_qx94_runner_start = QxRunner.start


async def _qx94_start(self):
    ok_started, info = await _qx94_runner_start(self)
    if ok_started and self.app is not None:
        with contextlib.suppress(Exception):
            self.app.add_handler(
                MessageHandler(filters.ALL, qx94_menu_sync_gate), group=-1999
            )
        with contextlib.suppress(Exception):
            await self.app.bot.set_my_commands(_qx94_bot_commands(False))
    return ok_started, info


QxRunner.start = _qx94_start


# ─────────────────────────────────────────────────────────────────────────────
# Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx94_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx94_prev_build_app() if callable(_qx94_prev_build_app) else None
    if app is None:
        return app

    def _dual(name, callback, group):
        register = globals().get("_register_dual_command")
        if callable(register):
            register(app, name, callback, group=group)
        else:
            app.add_handler(CommandHandler(name, callback), group=group)

    with contextlib.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx94_menu_sync_gate), group=-1035)
        app.add_handler(CallbackQueryHandler(qx94_on_callback, pattern=r"^qx94:"), group=-1028)

    # Owner panel first, then the user workspace panel (fall-through by role).
    for command in ("start", "menu", "guide"):
        with contextlib.suppress(Exception):
            _dual(command, qx94_owner_menu, -1012)
            _dual(command, qx94_user_menu, -1011)
    for command in ("cmd", "commands"):
        with contextlib.suppress(Exception):
            _dual(command, qx94_user_commands, -1011)
    with contextlib.suppress(Exception):
        _dual("help", qx94_user_menu, -1011)

    _prev_post_init = getattr(app, "post_init", None)

    async def _qx94_post_init(application):
        if callable(_prev_post_init):
            with contextlib.suppress(Exception):
                await _prev_post_init(application)
        with contextlib.suppress(Exception):
            await application.bot.set_my_commands(_qx94_bot_commands(False))

    app.post_init = _qx94_post_init

    _qx_log.info("[QUBIX-94] owner/user panels split, '/' menus scoped, clean inbox UI wired.")
    return app


_qx_log.info("[SECTION 94] Qubix owner/user split + clean inbox UI loaded.")


# ─────────────────────────────────────────────────────────────────────────────
# AI help prompt — user features only, no PDF wording
# ─────────────────────────────────────────────────────────────────────────────
def _qx92_help_prompt(question: str) -> str:  # noqa: F811
    return (
        "You are Qubix, a Telegram quiz-workspace assistant. Answer ONLY about the "
        "features listed below. Never mention owner/admin infrastructure, logs, "
        "keys, broadcast, database, PDF support, or any command not listed.\n\n"
        "Available user features (private inbox only):\n"
        "- Generate quiz: reply to a forwarded poll/quiz, a photo, or a text topic with "
        ".gen <count>, .gen medical <count>, .gen engineering <count>, .gen versity <count> (1-500)\n"
        "- View buffer: /buffer ; Export CSV+JSON: .done\n"
        "- Channels: /addchannel @channel, /listchannels, /removechannel, .post <channel#>\n"
        "- Groups/topics publishing: .adg <group_id>, .info, .adtc <group#> <thread_id> <name>, "
        ".pt <group#> <topic#>, .listgroups, .listtopics\n"
        "- Topic header/anchor: .topic, .aitopic, .mytopics, .usetopic <id>, "
        ".topicpin, .topicunpin, .cleartopic, .linktopic\n"
        "- Personal bot: /addbot <token>, /mybot on|off, /removebot, /myid\n\n"
        "Rules: answer in the user's language (Bangla/Banglish if they wrote so), "
        "be short and practical, use Telegram HTML only (<b>, <i>, <code>), "
        "give exact command examples, max 12 lines.\n\n"
        f"User question: {question}"
    )


globals()["_qx92_help_prompt"] = _qx92_help_prompt
