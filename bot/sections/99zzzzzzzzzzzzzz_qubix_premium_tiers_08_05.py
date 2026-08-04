# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 112 — QUBIX PREMIUM TIERS (2026-08-05)
#
#   Two premium products, one bot:
#
#   1. 🎓 Student Access  — inbox-only practice workspace.
#        • quiz generation from photo / text / poll (unlimited)
#        • generated quizzes are delivered INTO the user's own inbox
#          ("📥 Send to Inbox" button beside "📂 Export CSV")
#        • tiny command surface: generation + help + /switchaccess
#        • quiz prefix & explanation link are OWNER-controlled
#          (/studentprefix · /studentexplink)
#
#   2. 👑 Master Access — exactly today's full workspace (channels, groups,
#        topics, personal bot, everything). Student widgets are hidden.
#
#   Trial users pick a side from the /start welcome card (both are testable).
#   Owner assigns the paid tier with:  /qtier <user_id> student|master
#
#   Nothing existing is modified — this section only layers new handlers in
#   front of the current ones and falls through for Master users.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx112

_QX112_TIER_KEY = "tier:%d"
_QX112_STUDENT_PREFIX_KEY = "student_prefix"
_QX112_STUDENT_EXPLINK_KEY = "student_explink"

QX112_STUDENT_COMMANDS = {
    "start", "menu", "guide", "help", "cmd", "commands",
    "gen", "g", "buffer", "b", "buffercount", "bc",
    "done", "d", "clear", "c", "myid", "id",
    "switchaccess", "switchacsess", "switchasccess", "sa",
}

QX112_STUDENT_CALLBACK_OK = (
    "qx112:", "qx93:gen", "qx93:buffer", "qx93:export", "qx93:ask",
    "qx93:menu", "qx93:access", "qx93:cmds",
    "pba:csv", "pba:clr", "pba:close",
    "g59:", "genq:", "src59:",
)

with _cx112.suppress(Exception):
    _qx112_ws = globals().get("QX_WORKSPACE_COMMANDS")
    if isinstance(_qx112_ws, set):
        _qx112_ws |= {"switchaccess", "sa", "qtier", "studentprefix", "studentexplink"}

with _cx112.suppress(Exception):
    _qx112_prefixes = tuple(globals().get("QX_WORKSPACE_CALLBACK_PREFIXES") or ())
    if "qx112:" not in _qx112_prefixes:
        globals()["QX_WORKSPACE_CALLBACK_PREFIXES"] = _qx112_prefixes + ("qx112:",)
        QX_WORKSPACE_CALLBACK_PREFIXES = globals()["QX_WORKSPACE_CALLBACK_PREFIXES"]


# ─────────────────────────────────────────────────────────────────────────────
# 1) Tier storage (reuses the existing qubix_settings table — no migration)
# ─────────────────────────────────────────────────────────────────────────────
def _qx112_stored_tier(uid: int) -> str:
    with _cx112.suppress(Exception):
        value = str(_qx_setting(_QX112_TIER_KEY % int(uid), "") or "").strip().lower()
        if value in ("student", "master"):
            return value
    return ""


def _qx112_set_tier(uid: int, tier: str) -> None:
    with _cx112.suppress(Exception):
        _qx_set_setting(_QX112_TIER_KEY % int(uid), str(tier or "").strip().lower())


def _qx112_tier(uid: int) -> str:
    """'' = trial user who has not picked yet · 'student' · 'master'."""
    uid = int(uid or 0)
    if not uid:
        return "master"
    with _cx112.suppress(Exception):
        if _qx_real_owner(uid):
            return "master"
    stored = _qx112_stored_tier(uid)
    if stored:
        return stored
    mode = ""
    with _cx112.suppress(Exception):
        mode = str(_qx_access(uid).get("mode") or "")
    if mode == "trial":
        return ""
    return "master"


def _qx112_is_student(update, context) -> bool:
    with _cx112.suppress(Exception):
        if _qx93_privileged(update) and not _qx95_is_tenant(context):
            return False
    with _cx112.suppress(Exception):
        return _qx112_tier(_qx95_scope_uid(update, context)) == "student"
    return False


def _qx112_student_prefix() -> str:
    with _cx112.suppress(Exception):
        return str(_qx_setting(_QX112_STUDENT_PREFIX_KEY, "") or "").strip()
    return ""


def _qx112_student_explink() -> str:
    with _cx112.suppress(Exception):
        return str(_qx_setting(_QX112_STUDENT_EXPLINK_KEY, "") or "").strip()
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# 2) Cards & keyboards
# ─────────────────────────────────────────────────────────────────────────────
QX112_ROW = "<code>─────────────────────────</code>"


def _qx112_welcome_text(name: str, st) -> str:
    left = ""
    with _cx112.suppress(Exception):
        left = _qx_human_left(st.get("remaining"))
    return (
        f"👋 <b>স্বাগতম, {h(name or 'বন্ধু')}!</b>\n"
        f"{QX112_ROW}\n"
        "<b>Qubix</b>-এ দুই ধরনের premium workspace আছে। ট্রায়াল চলাকালীন "
        "আপনি <b>দুটোই</b> ব্যবহার করে দেখতে পারবেন।\n\n"
        "🎓 <b>Student Access</b>\n"
        "ছবি · টেক্সট · পোল থেকে আনলিমিটেড quiz তৈরি করে নিজের inbox-এ "
        "প্র্যাকটিস + CSV export।\n\n"
        "👑 <b>Master Access</b>\n"
        "সব কিছু — channel, group, topic, score card, নিজের bot token সহ "
        "পূর্ণ workspace।\n"
        f"{QX112_ROW}\n"
        f"⏳ <b>Trial বাকি:</b> <code>{h(left or '—')}</code>\n"
        "নিচের যেকোনো একটি বেছে নিন 👇"
    )


def _qx112_welcome_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎓 Student Access", callback_data="qx112:pick:student")],
        [InlineKeyboardButton("👑 Master Access", callback_data="qx112:pick:master")],
    ])


def _qx112_student_menu_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 Generate", callback_data="qx93:gen"),
            InlineKeyboardButton("📦 Buffer", callback_data="qx93:buffer"),
        ],
        [
            InlineKeyboardButton("📥 Send to Inbox", callback_data="qx112:inbox:buffer"),
            InlineKeyboardButton("📂 Export CSV", callback_data="qx93:export"),
        ],
        [
            InlineKeyboardButton("📜 My Commands", callback_data="qx112:cmds"),
            InlineKeyboardButton("💬 Ask AI Help", callback_data="qx93:ask"),
        ],
        [InlineKeyboardButton("👑 Master Access নিতে চাই", callback_data="qx112:switch")],
    ])


def _qx112_back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menu", callback_data="qx112:menu")]])


def _qx112_student_menu_text(name: str, uid: int, st) -> str:
    left = ""
    with _cx112.suppress(Exception):
        left = _qx_human_left(st.get("remaining"))
    total = 0
    with _cx112.suppress(Exception):
        total = int(buffer_count(uid))
    mode = str((st or {}).get("mode") or "")
    plan = "🎓 Student Access" + (" · Trial" if mode == "trial" else "")
    return (
        f"🎓 <b>Qubix — Student Practice</b>\n"
        f"{QX112_ROW}\n"
        f"👤 <b>{h(name or '—')}</b>\n"
        f"🪪 <b>Plan:</b> {plan}\n"
        f"⏳ <b>Validity:</b> <code>{h(left or 'unlimited')}</code>\n"
        f"📦 <b>Buffer:</b> <code>{total}</code> quiz\n"
        f"{QX112_ROW}\n"
        "⚡️ <b>এভাবে প্র্যাকটিস করুন</b>\n"
        "একটি <b>ছবি · টেক্সট · quiz/poll</b>-এ reply করে লিখুন:\n"
        "<code>.gen 15</code> · <code>.gen medical 15</code> · "
        "<code>.gen engineering 15</code> · <code>.gen versity 15</code>\n\n"
        "তারপর <b>📥 Send to Inbox</b> চাপলে quiz গুলো এখানেই চলে আসবে, "
        "আর <b>📂 Export CSV</b> চাপলে ফাইল পাবেন।"
    )


QX112_STUDENT_COMMANDS_CARD = (
    "📜 <b>Student Commands</b>\n"
    f"{QX112_ROW}\n"
    "<b>Generate</b>\n"
    "<code>.gen 15</code> — reply করা source থেকে quiz\n"
    "<code>.gen medical 15</code> · <code>.gen engineering 15</code> · "
    "<code>.gen versity 15</code>\n\n"
    "<b>Buffer &amp; Export</b>\n"
    "<code>/buffer</code> — জমা quiz দেখুন\n"
    "<code>/bc</code> — কতটি quiz আছে\n"
    "<code>.done</code> — নাম দিয়ে CSV export\n"
    "<code>.clear</code> — buffer খালি\n\n"
    "<b>Practice</b>\n"
    "📥 <b>Send to Inbox</b> button — quiz গুলো inbox-এ পাঠান\n\n"
    "<b>অন্যান্য</b>\n"
    "<code>/help আপনার প্রশ্ন</code> — AI সহায়তা\n"
    "<code>/switchaccess</code> — Master Access-এর জন্য অনুরোধ\n"
    "<code>/myid</code> — আপনার User ID\n"
    f"{QX112_ROW}\n"
    "🔐 Student workspace শুধু আপনার inbox-এই কাজ করে।"
)


def _qx112_switch_text(uid: int) -> str:
    contact = str(globals().get("OWNER_CONTACT") or "")
    return (
        "👑 <b>Master Access</b>\n"
        f"{QX112_ROW}\n"
        "Master Access নিলে আপনি পাবেন —\n"
        "• Channel · Group · Topic-এ সরাসরি quiz post\n"
        "• Prefix · Explanation link · Score card নিজের মতো সেট\n"
        "• নিজের bot token দিয়ে আলাদা bot চালানো\n"
        f"{QX112_ROW}\n"
        f"🆔 আপনার User ID: <code>{int(uid)}</code>\n"
        f"📩 যোগাযোগ: {h(contact or 'owner')}\n\n"
        "নিচের button চাপলে owner-এর কাছে আপনার অনুরোধ পৌঁছে যাবে।"
    )


def _qx112_switch_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 অনুরোধ পাঠান", callback_data="qx112:req")],
        [InlineKeyboardButton("◀️ Menu", callback_data="qx112:menu")],
    ])


async def _qx112_send(update, context, text, kb=None):
    sender = globals().get("_qx94_clean_send")
    if callable(sender):
        with _cx112.suppress(Exception):
            await sender(update, context, text, kb)
            return
    with _cx112.suppress(Exception):
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb,
            disable_web_page_preview=True,
        )


async def _qx112_show_student_menu(update, context, uid=None):
    uid = int(uid or _qx95_scope_uid(update, context))
    st = {}
    with _cx112.suppress(Exception):
        st = _qx_access(uid)
    name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")
    await _qx112_send(update, context, _qx112_student_menu_text(name, uid, st), _qx112_student_menu_kb())


# ─────────────────────────────────────────────────────────────────────────────
# 3) /start · /menu · /help · /commands  (fall through for Master users)
# ─────────────────────────────────────────────────────────────────────────────
async def qx112_panel_router(update, context):
    with _cx112.suppress(Exception):
        if _qx93_privileged(update) and not _qx95_is_tenant(context):
            return
    uid = int(_qx95_scope_uid(update, context) or 0)
    if not uid:
        return
    st = {}
    with _cx112.suppress(Exception):
        st = _qx_access(uid)
    if not st.get("ok"):
        return  # existing expired card handles this

    tier = _qx112_tier(uid)
    name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")
    if tier == "":
        await _qx112_send(update, context, _qx112_welcome_text(name, st), _qx112_welcome_kb())
        raise ApplicationHandlerStop
    if tier == "student":
        await _qx112_show_student_menu(update, context, uid)
        raise ApplicationHandlerStop
    return  # master → untouched behaviour


async def qx112_panel_router_help(update, context):
    if " ".join(list(getattr(context, "args", []) or [])).strip():
        return
    await qx112_panel_router(update, context)


async def qx112_cmd_commands(update, context):
    if not _qx112_is_student(update, context):
        return
    await _qx112_send(update, context, QX112_STUDENT_COMMANDS_CARD, _qx112_back_kb())
    raise ApplicationHandlerStop


async def qx112_cmd_switchaccess(update, context):
    uid = int(_qx95_scope_uid(update, context) or 0)
    await _qx112_send(update, context, _qx112_switch_text(uid), _qx112_switch_kb())
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 4) Student scope gate — tiny command surface, no owner/master widgets
# ─────────────────────────────────────────────────────────────────────────────
async def qx112_student_gate(update, context):
    if not _qx112_is_student(update, context):
        return
    message = getattr(update, "effective_message", None)
    if message is None:
        return
    text = str(getattr(message, "text", "") or "")
    if text[:1] not in ("/", "."):
        return
    command = re.split(r"[\s@]", text[1:].strip(), 1)[0].lower()
    if command in QX112_STUDENT_COMMANDS:
        with _cx112.suppress(Exception):
            _QX_ACTING_OWNER.set(int(_qx95_scope_uid(update, context)))
        return
    await _qx112_send(
        update, context,
        "🎓 <b>Student workspace</b>\n"
        f"{QX112_ROW}\n"
        "এই command আপনার plan-এ নেই। Student workspace-এ quiz generate, "
        "inbox practice আর CSV export করা যায়।\n\n"
        "সব command দেখতে <code>/commands</code>, আর পূর্ণ access নিতে "
        "<code>/switchaccess</code>।",
        _qx112_student_menu_kb(),
    )
    raise ApplicationHandlerStop


async def qx112_student_callback_gate(update, context):
    query = getattr(update, "callback_query", None)
    if query is None or not _qx112_is_student(update, context):
        return
    data = str(getattr(query, "data", "") or "")
    if data.startswith(QX112_STUDENT_CALLBACK_OK):
        with _cx112.suppress(Exception):
            _QX_ACTING_OWNER.set(int(_qx95_scope_uid(update, context)))
        return
    with _cx112.suppress(Exception):
        await query.answer("এই feature Master Access-এ পাওয়া যায়।", show_alert=True)
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 5) Student inbox delivery + result keyboard button
# ─────────────────────────────────────────────────────────────────────────────
async def _qx112_deliver_to_inbox(context, uid: int, chat_id: int) -> tuple:
    items = []
    with _cx112.suppress(Exception):
        items = list(buffer_list(int(uid)) or [])
    if not items:
        return (0, 0)
    poster = globals().get("_post_buffer_to_chat")
    if not callable(poster):
        return (0, 0)
    with _cx112.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))
    ok_count = 0
    fail_count = 0
    with _cx112.suppress(Exception):
        ok_count, fail_count, _first = await poster(
            context, int(uid), int(chat_id), items, None,
            _qx112_student_prefix(), _qx112_student_explink(),
        )
    return (int(ok_count or 0), int(fail_count or 0))


_qx112_prev_result_kb = globals().get("_qx95_result_kb")


async def _qx95_result_kb(context, uid: int, chat_id: int):  # noqa: F811
    kb = await _qx112_prev_result_kb(context, uid, chat_id) if callable(_qx112_prev_result_kb) else None
    if kb is None:
        return kb
    if _qx112_tier(uid) != "student":
        return kb
    rows = []
    with _cx112.suppress(Exception):
        rows = [list(row) for row in (getattr(kb, "inline_keyboard", []) or [])]
    if not rows:
        return kb
    with _cx112.suppress(Exception):
        rows.insert(0, [InlineKeyboardButton("📥 Send to Inbox", callback_data="qx112:inbox:buffer")])
        return InlineKeyboardMarkup(rows)
    return kb


globals()["_qx95_result_kb"] = _qx95_result_kb


# ─────────────────────────────────────────────────────────────────────────────
# 6) Callbacks
# ─────────────────────────────────────────────────────────────────────────────
async def qx112_on_callback(update, context):
    query = update.callback_query
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("qx112:"):
        return
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else "menu"
    uid = int(_qx95_scope_uid(update, context) or 0)
    name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")

    with _cx112.suppress(Exception):
        await query.answer()
    with _cx112.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))

    async def _edit(text, kb=None):
        with _cx112.suppress(Exception):
            await query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=kb,
                disable_web_page_preview=True,
            )

    if action == "pick":
        choice = (parts[2] if len(parts) > 2 else "student").lower()
        choice = "master" if choice == "master" else "student"
        _qx112_set_tier(uid, choice)
        st = {}
        with _cx112.suppress(Exception):
            st = _qx_access(uid)
        if choice == "student":
            await _edit(_qx112_student_menu_text(name, uid, st), _qx112_student_menu_kb())
        else:
            text = None
            with _cx112.suppress(Exception):
                text = await _qx94_user_menu_text(update, context, uid, st)
            await _edit(
                text or "👑 <b>Master Access</b> চালু হলো। <code>/start</code> দিন।",
                _qx93_menu_kb() if callable(globals().get("_qx93_menu_kb")) else None,
            )
        raise ApplicationHandlerStop

    if action == "menu":
        st = {}
        with _cx112.suppress(Exception):
            st = _qx_access(uid)
        if _qx112_tier(uid) == "student":
            await _edit(_qx112_student_menu_text(name, uid, st), _qx112_student_menu_kb())
        else:
            await _edit(_qx112_welcome_text(name, st), _qx112_welcome_kb())
        raise ApplicationHandlerStop

    if action == "cmds":
        await _edit(QX112_STUDENT_COMMANDS_CARD, _qx112_back_kb())
        raise ApplicationHandlerStop

    if action == "switch":
        await _edit(_qx112_switch_text(uid), _qx112_switch_kb())
        raise ApplicationHandlerStop

    if action == "req":
        sent = False
        with _cx112.suppress(Exception):
            for owner_id in (globals().get("OWNER_IDS") or ()):
                await context.bot.send_message(
                    chat_id=int(owner_id),
                    text=(
                        "👑 <b>Master Access Request</b>\n"
                        f"👤 {h(name or '—')}\n"
                        f"🆔 <code>{int(uid)}</code>\n\n"
                        f"অনুমোদন: <code>/qtier {int(uid)} master</code> ও "
                        f"<code>/qapprove {int(uid)}</code>"
                    ),
                    parse_mode=ParseMode.HTML,
                )
                sent = True
        await _edit(
            "✅ <b>অনুরোধ পাঠানো হয়েছে</b>\n"
            f"{QX112_ROW}\n"
            "Owner খুব দ্রুত আপনার Master Access পর্যালোচনা করবেন। "
            "অনুমোদন হলে <code>/start</code> দিলেই নতুন workspace খুলে যাবে।"
            if sent else
            "ℹ️ এখন অনুরোধ পাঠানো গেল না। একটু পরে আবার চেষ্টা করুন, "
            f"অথবা সরাসরি {h(str(globals().get('OWNER_CONTACT') or ''))}-এ যোগাযোগ করুন।",
            _qx112_back_kb(),
        )
        raise ApplicationHandlerStop

    if action == "inbox":
        chat_id = int(getattr(getattr(query, "message", None), "chat_id", uid) or uid)
        with _cx112.suppress(Exception):
            await query.edit_message_text(
                ui_box_html("Sending", "Quiz গুলো আপনার inbox-এ পাঠানো হচ্ছে…", emoji="📥"),
                parse_mode=ParseMode.HTML,
            )
        ok_count, fail_count = await _qx112_deliver_to_inbox(context, uid, chat_id)
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
        with _cx112.suppress(Exception):
            await context.bot.send_message(
                chat_id=chat_id,
                text="📥 <b>Inbox Practice</b>\n" + QX112_ROW + "\n" + body,
                parse_mode=ParseMode.HTML,
                reply_markup=_qx112_student_menu_kb(),
                disable_web_page_preview=True,
            )
        raise ApplicationHandlerStop

    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 7) Owner controls
# ─────────────────────────────────────────────────────────────────────────────
async def qx112_cmd_qtier(update, context):
    user = getattr(update, "effective_user", None)
    if not _qx_real_owner(getattr(user, "id", 0)):
        raise ApplicationHandlerStop
    parts = str(getattr(update.effective_message, "text", "") or "").split()
    if len(parts) < 3 or not parts[1].lstrip("-").isdigit() or parts[2].lower() not in ("student", "master", "reset"):
        await update.effective_message.reply_text(
            "ℹ️ <code>/qtier &lt;user_id&gt; student|master|reset</code>\n"
            "student → inbox practice plan · master → পূর্ণ workspace · "
            "reset → user আবার নিজে বেছে নেবে।",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop
    uid = int(parts[1])
    tier = parts[2].lower()
    _qx112_set_tier(uid, "" if tier == "reset" else tier)
    await update.effective_message.reply_text(
        f"✅ <code>{uid}</code> → <b>{h(tier)}</b> plan সেট হয়েছে।",
        parse_mode=ParseMode.HTML,
    )
    notify = globals().get("_qx_notify")
    if callable(notify) and tier != "reset":
        label = "🎓 <b>Student Access</b>" if tier == "student" else "👑 <b>Master Access</b>"
        with _cx112.suppress(Exception):
            await notify(
                uid,
                f"{label} চালু হয়েছে!\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "নতুন workspace খুলতে এখনই <code>/start</code> দিন।",
            )
    raise ApplicationHandlerStop


async def qx112_cmd_studentprefix(update, context):
    if not _qx_real_owner(getattr(getattr(update, "effective_user", None), "id", 0)):
        raise ApplicationHandlerStop
    value = " ".join(list(getattr(context, "args", []) or [])).strip()
    with _cx112.suppress(Exception):
        _qx_set_setting(_QX112_STUDENT_PREFIX_KEY, value)
    current = _qx112_student_prefix()
    await update.effective_message.reply_text(
        "🎓 <b>Student Quiz Prefix</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"এখনকার prefix: <code>{h(current or '(empty)')}</code>\n\n"
        "পরিবর্তন: <code>/studentprefix আপনার লেখা</code>\n"
        "মুছতে: <code>/studentprefix</code>",
        parse_mode=ParseMode.HTML,
    )
    raise ApplicationHandlerStop


async def qx112_cmd_studentexplink(update, context):
    if not _qx_real_owner(getattr(getattr(update, "effective_user", None), "id", 0)):
        raise ApplicationHandlerStop
    value = " ".join(list(getattr(context, "args", []) or [])).strip()
    with _cx112.suppress(Exception):
        _qx_set_setting(_QX112_STUDENT_EXPLINK_KEY, value)
    current = _qx112_student_explink()
    await update.effective_message.reply_text(
        "🎓 <b>Student Explanation Link</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"এখনকার link: <code>{h(current or '(empty)')}</code>\n\n"
        "পরিবর্তন: <code>/studentexplink https://t.me/...</code>\n"
        "মুছতে: <code>/studentexplink</code>",
        parse_mode=ParseMode.HTML,
    )
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 8) Menus / command sheets
# ─────────────────────────────────────────────────────────────────────────────
QX112_OWNER_MENU_ADD = [
    ("qtier", "User plan: student/master"),
    ("studentprefix", "Student quiz prefix"),
    ("studentexplink", "Student explanation link"),
]

QX112_STUDENT_MENU_COMMANDS = [
    ("start", "Student workspace"),
    ("menu", "Student workspace"),
    ("gen", "Quiz generate (reply দিয়ে)"),
    ("buffer", "Buffer দেখুন"),
    ("bc", "Buffer count"),
    ("done", "CSV export"),
    ("clear", "Buffer খালি"),
    ("commands", "আমার command গুলো"),
    ("switchaccess", "Master Access চাই"),
    ("help", "সহায়তা / প্রশ্ন"),
    ("myid", "আমার User ID"),
]

with _cx112.suppress(Exception):
    _qx112_user_menu = globals().get("QX97_USER_MENU_COMMANDS")
    if isinstance(_qx112_user_menu, list):
        if not any(str(item[0]) == "switchaccess" for item in _qx112_user_menu if item):
            _qx112_user_menu.append(("switchaccess", "Access plan পরিবর্তন"))

with _cx112.suppress(Exception):
    _qx112_owner_menu = globals().get("QX94_OWNER_MENU_COMMANDS")
    if isinstance(_qx112_owner_menu, list):
        _qx112_owner_have = {str(item[0]) for item in _qx112_owner_menu if item}
        for _qx112_name, _qx112_desc in QX112_OWNER_MENU_ADD:
            if _qx112_name not in _qx112_owner_have:
                _qx112_owner_menu.append((_qx112_name, _qx112_desc))

with _cx112.suppress(Exception):
    _qx112_owner_card = globals().get("QX94_OWNER_CARD")
    if isinstance(_qx112_owner_card, str) and "/qtier" not in _qx112_owner_card:
        globals()["QX94_OWNER_CARD"] = _qx112_owner_card + (
            "\n\n<b>Premium plans</b>\n"
            "<code>/qtier &lt;id&gt; student</code> — inbox practice plan\n"
            "<code>/qtier &lt;id&gt; master</code> — পূর্ণ workspace\n"
            "<code>/qtier &lt;id&gt; reset</code> — user নিজে বেছে নেবে\n"
            "<code>/studentprefix &lt;text&gt;</code> · "
            "<code>/studentexplink &lt;link&gt;</code>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 9) Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx112_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx112_prev_build_app() if callable(_qx112_prev_build_app) else None
    if app is None:
        return app

    def _dual(name, callback, group):
        register = globals().get("_register_dual_command")
        if callable(register):
            register(app, name, callback, group=group)
        else:
            app.add_handler(CommandHandler(name, callback), group=group)

    with _cx112.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx112_on_callback, pattern=r"^qx112:"), group=-1045
        )
    with _cx112.suppress(Exception):
        app.add_handler(CallbackQueryHandler(qx112_student_callback_gate), group=-1044)
    with _cx112.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx112_student_gate), group=-1043)

    for command in ("start", "menu", "guide"):
        with _cx112.suppress(Exception):
            _dual(command, qx112_panel_router, -1042)
    with _cx112.suppress(Exception):
        _dual("help", qx112_panel_router_help, -1042)
    for command in ("cmd", "commands"):
        with _cx112.suppress(Exception):
            _dual(command, qx112_cmd_commands, -1042)
    for command in ("switchaccess", "sa"):
        with _cx112.suppress(Exception):
            _dual(command, qx112_cmd_switchaccess, -1042)

    for command, handler in (
        ("qtier", qx112_cmd_qtier),
        ("studentprefix", qx112_cmd_studentprefix),
        ("studentexplink", qx112_cmd_studentexplink),
    ):
        with _cx112.suppress(Exception):
            _dual(command, handler, -1041)

    _qx_log.info("[QUBIX-112] premium tiers wired: student inbox plan + master access.")
    return app


_qx_log.info("[SECTION 112] Qubix premium tiers (Student / Master Access) loaded.")
