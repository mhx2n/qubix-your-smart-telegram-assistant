# ──────────────────────────────────────────────────────────────────────────────
# Section: 100_qubix_backup_scope_rich_menus_08_04
# Purpose:
#   1. Backup console now renders as a NATIVE rich table (Bot API sendRichMessage
#      markdown tables) with a preformatted fallback — no more ragged text.
#   2. MongoDB mirror scope trimmed to exactly what the owner asked for:
#      user info, approved users' bot tokens, owner-added AI API keys, and every
#      user's channels / groups / forum topics (+ access records).
#   3. Full "/" command menus: owner sees every owner command, users see every
#      command they are allowed to run — in the main bot and in their own bot.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx100
import datetime as _dt100

from telegram.constants import ParseMode as _PM100
from telegram.ext import ApplicationHandlerStop as _AHS100


def _qx100_log(msg):
    with _cx100.suppress(Exception):
        logger.info("[QX100] %s", msg)


# ═════════════════════════════════════════════════════════════════════════════
# 1) Backup scope — only the data the owner wants mirrored
# ═════════════════════════════════════════════════════════════════════════════
QX100_BACKUP_TABLES = [
    # (sqlite_table, mongo_collection, unique_key, label)
    ("users",                "users",                "user_id", "User info"),
    ("qubix_access",         "qubix_access",         "user_id", "Access grants"),
    ("qubix_bots",           "qubix_bots",           "user_id", "User bot tokens"),
    ("gemini_api_keys",      "gemini_api_keys",      "api_key", "Gemini API keys"),
    ("mistral_api_keys",     "mistral_api_keys",     "api_key", "Mistral API keys"),
    ("channels",             "channels",             "channel_chat_id", "Channels"),
    ("saved_groups",         "saved_groups",         "group_chat_id", "Groups"),
    ("group_topics",         "group_topics",         None, "Forum topics"),
    ("saved_topic_anchors",  "saved_topic_anchors",  None, "Topic anchors"),
]

globals()["_MONGO_TABLES"] = [(t, c, k) for (t, c, k, _l) in QX100_BACKUP_TABLES]
QX100_LABELS = {t: l for (t, _c, _k, l) in QX100_BACKUP_TABLES}


# ═════════════════════════════════════════════════════════════════════════════
# 2) Rich (native table) backup console
# ═════════════════════════════════════════════════════════════════════════════
def _qx100_cluster() -> str:
    uri = str(globals().get("QX99_MONGO_URI") or "")
    if not uri:
        return "—"
    return uri.split("@")[-1].split("/")[0][:48] or "—"


def _qx100_report_md() -> str:
    """Markdown report — real tables, rendered natively by Telegram."""
    stamp = _dt100.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    uri = str(globals().get("QX99_MONGO_URI") or "")
    dbname = str(globals().get("QX99_MONGO_DB") or "qubix_db")

    if not uri:
        return (
            "## 🔐 Backup Console\n\n"
            "> ☁️ MongoDB এখনো কনফিগার করা হয়নি।\n\n"
            "| Variable | Value |\n|---|---|\n"
            "| `MONGODB_URI` | আপনার connection string |\n"
            f"| `MONGODB_DB` | `{dbname}` |\n\n"
            "Render → Service → **Environment** এ যোগ করে redeploy দিন।"
        )

    client = globals()["_qx99_client"]()
    if client is None:
        return (
            "## ⚠️ Backup Console\n\n"
            "> ☁️ MongoDB-তে সংযোগ করা যাচ্ছে না।\n\n"
            f"**Cluster:** `{_qx100_cluster()}`\n\n"
            "Atlas → **Network Access** এ `0.0.0.0/0` যোগ করুন এবং "
            "user / password যাচাই করুন।"
        )

    local_fn = globals()["_qx99_local_count"]
    rows = []
    local_total = remote_total = 0
    meta = {}
    try:
        db = client[dbname]
        with _cx100.suppress(Exception):
            meta = db["_meta"].find_one({"_id": "backup_info"}) or {}
        for table, coll, _key, label in QX100_BACKUP_TABLES:
            local = max(0, int(local_fn(table)))
            remote = 0
            with _cx100.suppress(Exception):
                remote = int(db[coll].count_documents({}))
            local_total += local
            remote_total += remote
            if local == 0 and remote == 0:
                mark = "— empty"
            elif remote >= local:
                mark = "✅ OK"
            elif remote == 0:
                mark = "❌ Missing"
            else:
                mark = "🟡 Lagging"
            rows.append((label, local, remote, mark))
    finally:
        with _cx100.suppress(Exception):
            client.close()

    drift = local_total - remote_total
    health = (
        "🟢 Synchronised" if drift <= 0
        else ("🟡 Partial drift" if drift <= 25 else "🔴 Backup required")
    )
    last = str(meta.get("last_backup_at") or "কখনো নয়")[:32]
    by = str(meta.get("requester") or "—")[:24]

    table_md = (
        "| Data | Local | Cloud | Status |\n"
        "|:---|---:|---:|:---|\n"
        + "\n".join(f"| {lbl} | {lo} | {re_} | {mk} |" for (lbl, lo, re_, mk) in rows)
        + f"\n| **TOTAL** | **{local_total}** | **{remote_total}** | **{health}** |"
    )

    return (
        "## 🗄 Backup Console\n\n"
        "| Field | Value |\n|:---|:---|\n"
        f"| Database | `{dbname}` |\n"
        f"| Cluster | `{_qx100_cluster()}` |\n"
        f"| Report | `{stamp}` |\n"
        f"| শেষ ব্যাকআপ | `{last}` |\n"
        f"| Requested by | `{by}` |\n\n"
        "### Mirror contents\n\n"
        f"{table_md}\n\n"
        f"**Drift:** `{drift}` row(s)  ·  **Health:** {health}\n\n"
        "> এই ডিবিতে শুধু user info, access পাওয়া user-দের bot token, "
        "owner-এর যোগ করা API key এবং সব user-এর channel / group / topic "
        "মিরর হয়। বাকি কিছুই নয়।\n\n"
        "🗄 **Backup Now** চাপলেই cloud-এ push হবে — কোনো অটো ব্যাকআপ নেই।"
    )


async def _qx100_send_rich(bot, chat_id, markdown, kb=None, reply_to=None):
    """Native rich message (real tables) with an HTML fallback."""
    native = globals().get("_qx98_native_rich")
    if callable(native):
        with _cx100.suppress(Exception):
            sent = await native(
                bot, chat_id, markdown, reply_to=reply_to, reply_markup=kb
            )
            if sent is not None:
                return sent
    fallback = globals().get("_qx98_html_fallback")
    body = fallback(markdown) if callable(fallback) else markdown
    with _cx100.suppress(Exception):
        return await bot.send_message(
            chat_id=chat_id, text=body[:4000], parse_mode=_PM100.HTML,
            reply_markup=kb, disable_web_page_preview=True,
        )
    return None


async def qx100_cmd_backup(update, context):
    message = getattr(update, "effective_message", None)
    uid = globals()["_qx99_uid"](update)
    if message is None or not globals()["_qx99_is_owner"](uid):
        raise _AHS100
    token = globals()["_QX99_BYPASS"].set(True)
    try:
        with _cx100.suppress(Exception):
            await message.delete()
        store = getattr(context, "chat_data", None)
        if isinstance(store, dict):
            old = store.pop("qx100_console_id", None)
            if old:
                with _cx100.suppress(Exception):
                    await context.bot.delete_message(
                        chat_id=message.chat_id, message_id=int(old)
                    )
        report = await asyncio.get_event_loop().run_in_executor(None, _qx100_report_md)
        sent = await _qx100_send_rich(
            context.bot, message.chat_id, report, globals()["_qx99_console_kb"]()
        )
        if sent is not None and isinstance(store, dict):
            with _cx100.suppress(Exception):
                store["qx100_console_id"] = int(sent.message_id)
    finally:
        globals()["_QX99_BYPASS"].reset(token)
    raise _AHS100


async def qx100_cb_backup(update, context):
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    uid = 0
    with _cx100.suppress(Exception):
        uid = int(query.from_user.id)
    if not globals()["_qx99_is_owner"](uid):
        with _cx100.suppress(Exception):
            await query.answer("Owner only.", show_alert=True)
        raise _AHS100

    action = (query.data or "").split(":")[-1]
    chat_id = query.message.chat_id
    token = globals()["_QX99_BYPASS"].set(True)
    loop = asyncio.get_event_loop()
    try:
        if action == "cl":
            with _cx100.suppress(Exception):
                await query.answer("Closed")
            with _cx100.suppress(Exception):
                await query.message.delete()
            raise _AHS100

        header = ""
        if action == "bk":
            with _cx100.suppress(Exception):
                await query.answer("Backing up…")
            runner = globals().get("mongo_backup_now")
            ok_n = fail_n = 0
            if callable(runner):
                ok_n, fail_n, _s = await loop.run_in_executor(
                    None, lambda: runner(requester=f"owner-{uid}")
                )
            header = (
                "### ✅ Backup complete\n\n"
                "| Result | Count |\n|:---|---:|\n"
                f"| Saved tables | {ok_n} |\n| Failed | {fail_n} |\n\n"
            )
        elif action == "rs":
            with _cx100.suppress(Exception):
                await query.answer("Restoring…")
            runner = globals().get("mongo_restore_now")
            ok_n = fail_n = 0
            if callable(runner):
                ok_n, fail_n, _s = await loop.run_in_executor(None, runner)
            header = (
                "### ⬇️ Restore complete\n\n"
                "| Result | Count |\n|:---|---:|\n"
                f"| Restored tables | {ok_n} |\n| Failed | {fail_n} |\n\n"
            )
        else:
            with _cx100.suppress(Exception):
                await query.answer("Refreshed")

        report = header + await loop.run_in_executor(None, _qx100_report_md)
        with _cx100.suppress(Exception):
            await query.message.delete()
        sent = await _qx100_send_rich(
            context.bot, chat_id, report, globals()["_qx99_console_kb"]()
        )
        store = getattr(context, "chat_data", None)
        if sent is not None and isinstance(store, dict):
            with _cx100.suppress(Exception):
                store["qx100_console_id"] = int(sent.message_id)
    finally:
        globals()["_QX99_BYPASS"].reset(token)
    raise _AHS100


# Route section 99's wiring to the rich implementations.
globals()["qx99_cmd_backup"] = qx100_cmd_backup
globals()["qx99_cb_backup"] = qx100_cb_backup


# ═════════════════════════════════════════════════════════════════════════════
# 3) Complete "/" command menus (owner sheet vs user sheet)
# ═════════════════════════════════════════════════════════════════════════════
QX100_USER_MENU = [
    ("start", "Workspace menu"),
    ("menu", "Workspace menu"),
    ("commands", "আমার সব command"),
    ("help", "AI সহায়তা"),
    ("gen", "Reply দিয়ে quiz generate"),
    ("buffer", "Buffer-এ কতটি quiz"),
    ("buffercount", "Buffer count"),
    ("done", "CSV file export"),
    ("clear", "Buffer খালি করুন"),
    ("stopquiz", "চলমান posting থামান"),
    ("resumequiz", "থামানো posting চালু করুন"),
    ("addchannel", "Channel যোগ করুন"),
    ("listchannels", "আমার channel list"),
    ("removechannel", "Channel সরান"),
    ("post", "Channel-এ post"),
    ("adg", "Group যোগ করুন"),
    ("listgroups", "আমার group list"),
    ("adtc", "Group topic যোগ করুন"),
    ("listtopics", "আমার topic list"),
    ("pt", "Topic-এ post"),
    ("info", "Topic thread id দেখুন"),
    ("topic", "Topic header পাঠান"),
    ("aitopic", "AI topic header"),
    ("topicpin", "Topic header pin"),
    ("topicunpin", "Topic header unpin"),
    ("cleartopic", "Topic header মুছুন"),
    ("mytopics", "সেভ করা topic anchor"),
    ("usetopic", "Topic anchor ব্যবহার"),
    ("linktopic", "Post link থেকে topic"),
    ("setprefix", "Quiz prefix সেট"),
    ("setexplink", "Explanation link সেট"),
    ("exo", "Explanation চালু"),
    ("exf", "Explanation বন্ধ"),
    ("score", "Score reply চালু/বন্ধ"),
    ("addbot", "নিজের bot token যোগ"),
    ("mybot", "নিজের bot status"),
    ("removebot", "নিজের bot সরান"),
    ("myid", "আমার User ID"),
]

QX100_OWNER_EXTRA = [
    ("qapprove", "User-কে full access দিন"),
    ("qrevoke", "Access + token বাতিল"),
    ("qtrial", "Trial সময় (minutes)"),
    ("qbots", "সব tenant bot"),
    ("qkill", "কোনো tenant bot বন্ধ"),
    ("qbackup", "MongoDB backup console"),
    ("adminpanel", "Admin stats"),
    ("dashboard", "System dashboard"),
    ("status", "System status"),
    ("logs", "System logs"),
    ("broadcast", "Broadcast message"),
    ("ask", "কোনো user-কে প্রশ্ন"),
    ("reply", "User-কে উত্তর"),
    ("banned", "Ban list"),
    ("filter", "Filter যোগ"),
    ("addkey", "AI key যোগ"),
    ("keys", "AI key list"),
    ("delkey", "AI key মুছুন"),
    ("gemini", "Gemini key pool"),
    ("mistral", "Mistral key pool"),
    ("models", "Model switch"),
    ("elevenlabs", "Voice key"),
    ("restart", "Bot restart"),
]

# Users keep every workspace command; owners get those plus the control set.
_qx100_user_menu = [(n, d) for (n, d) in QX100_USER_MENU]
_qx100_owner_menu = _qx100_user_menu + [
    (n, d) for (n, d) in QX100_OWNER_EXTRA
    if n not in {x for (x, _d) in _qx100_user_menu}
]

globals()["QX94_USER_MENU_COMMANDS"] = _qx100_user_menu[:99]
globals()["QX94_OWNER_MENU_COMMANDS"] = _qx100_owner_menu[:99]

# Self-management commands never appear inside a personal (tenant) bot.
QX100_TENANT_HIDDEN = set(globals().get("QX97_TENANT_HIDDEN") or ()) | {
    "mybot", "removebot", "delbot", "myid", "wake", "addbot"
}
globals()["QX97_TENANT_HIDDEN"] = QX100_TENANT_HIDDEN


def _qx94_bot_commands(owner: bool):  # noqa: F811
    source = _qx100_owner_menu if owner else _qx100_user_menu
    tenant = False
    with _cx100.suppress(Exception):
        tenant = bool(globals()["_QX97_TENANT"].get())
    if tenant:
        source = [(n, d) for (n, d) in source if n not in QX100_TENANT_HIDDEN]
    out = []
    for name, desc in source:
        with _cx100.suppress(Exception):
            out.append(BotCommand(name, str(desc)[:256]))
    return out[:100]


globals()["_qx94_bot_commands"] = _qx94_bot_commands


_qx100_log(
    "backup scope trimmed, rich table console wired, full command menus published"
)


# Tenant bots must publish the user sheet without self-management commands.
_qx100_prev_runner_start = None
with _cx100.suppress(Exception):
    _qx100_prev_runner_start = QxRunner.start


async def _qx100_runner_start(self):
    ok_started, info = await _qx100_prev_runner_start(self)
    if ok_started and getattr(self, "app", None) is not None:
        token = None
        with _cx100.suppress(Exception):
            token = globals()["_QX97_TENANT"].set(True)
        try:
            with _cx100.suppress(Exception):
                await self.app.bot.set_my_commands(_qx94_bot_commands(False))
        finally:
            if token is not None:
                with _cx100.suppress(Exception):
                    globals()["_QX97_TENANT"].reset(token)
    return ok_started, info


if callable(_qx100_prev_runner_start):
    QxRunner.start = _qx100_runner_start
