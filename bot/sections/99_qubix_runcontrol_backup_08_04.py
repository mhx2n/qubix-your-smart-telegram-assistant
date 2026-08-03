# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 99 — QUBIX RUN CONTROL + MONGO ANALYSIS BACKUP (2026-08-04)
#
#   1. /stopquiz now halts a running publish job INSTANTLY (channel, group,
#      topic, emoji quiz) — the send layer itself refuses further delivery and
#      the already-published rows are removed from the buffer, so nothing is
#      duplicated later.
#   2. /resumequiz clears the halt and CONTINUES the interrupted run from the
#      exact point it stopped (same channel / topic, remaining buffer only).
#   3. `.gen` on the same source replaces the previous result card instead of
#      stacking a new one.
#   4. Owner-only `/qbackup` — a full MongoDB analysis console: rich table
#      report (SQLite vs MongoDB, delta, health) plus on-demand backup and
#      restore. Manual only; nothing runs automatically.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx99
import contextvars as _cv99
import datetime as _dt99
import time as _t99

import telegram as _tg99
from telegram.ext import ApplicationHandlerStop as _AHS99
from telegram import InlineKeyboardButton as _IKB99, InlineKeyboardMarkup as _IKM99
from telegram.constants import ParseMode as _PM99


_QX99_LOG = globals().get("_qx_log") or globals().get("logger")


def _qx99_log(msg, level="info"):
    with _cx99.suppress(Exception):
        getattr(_QX99_LOG, level)("[QUBIX-99] %s", msg)


# ═════════════════════════════════════════════════════════════════════════════
# 1) RUN CONTROL — instant stop / true resume
# ═════════════════════════════════════════════════════════════════════════════
class _QX99Stop(BaseException):
    """Raised inside the transport layer to abort a publishing run at once."""


_QX99_STOP: set = set()          # uids with an active stop request
_QX99_ACTIVE: dict = {}          # uid -> run state while publishing
_QX99_PENDING: dict = {}         # uid -> interrupted job (for /resumequiz)
_QX99_RUN_UID = _cv99.ContextVar("qx99_run_uid", default=0)
_QX99_BYPASS = _cv99.ContextVar("qx99_bypass", default=False)

_QX99_POST_CMDS = {
    "post", "p", "postemoji", "pe", "pt", "pg", "postall", "ptopic",
}


def _qx99_uid(update) -> int:
    with _cx99.suppress(Exception):
        acting = int(globals().get("_QX_ACTING_OWNER").get() or 0)  # type: ignore[union-attr]
        if acting:
            return acting
    with _cx99.suppress(Exception):
        return int(update.effective_user.id)
    return 0


def _qx99_cmd_word(update) -> str:
    with _cx99.suppress(Exception):
        text = (getattr(getattr(update, "effective_message", None), "text", "") or "").strip()
        if text[:1] in (".", "/", "!"):
            return text[1:].split()[0].split("@")[0].strip().lower()
    return ""


def _qx99_snapshot(uid: int) -> None:
    """Remember buffer order once, so a halted run can trim what it published."""
    state = _QX99_ACTIVE.get(uid)
    if state is None or state.get("rows") is not None:
        return
    rows = []
    with _cx99.suppress(Exception):
        rows = [int(r[0]) for r in (buffer_list(uid, limit=MAX_BUFFERED_QUESTIONS) or [])]
    state["rows"] = rows


def _qx99_count_sent(uid: int) -> None:
    state = _QX99_ACTIVE.get(uid)
    if state is not None:
        state["sent"] = int(state.get("sent") or 0) + 1


def _qx99_should_halt(uid: int) -> bool:
    if not uid or _QX99_BYPASS.get():
        return False
    return uid in _QX99_STOP and uid in _QX99_ACTIVE


# ── transport guards ─────────────────────────────────────────────────────────
_qx99_prev_send_poll = _tg99.Bot.send_poll
_qx99_prev_send_message = _tg99.Bot.send_message


async def _qx99_send_poll(self, *args, **kwargs):
    uid = int(_QX99_RUN_UID.get() or 0)
    if _qx99_should_halt(uid):
        raise _QX99Stop()
    if uid in _QX99_ACTIVE:
        _qx99_snapshot(uid)
    result = await _qx99_prev_send_poll(self, *args, **kwargs)
    if uid in _QX99_ACTIVE:
        _qx99_count_sent(uid)
    return result


async def _qx99_send_message(self, *args, **kwargs):
    uid = int(_QX99_RUN_UID.get() or 0)
    state = _QX99_ACTIVE.get(uid)
    if state is not None and state.get("emoji") and _qx99_should_halt(uid):
        raise _QX99Stop()
    if state is not None and state.get("emoji"):
        _qx99_snapshot(uid)
    result = await _qx99_prev_send_message(self, *args, **kwargs)
    if state is not None and state.get("emoji") and str(kwargs.get("reply_markup") or ""):
        _qx99_count_sent(uid)
    return result


_tg99.Bot.send_poll = _qx99_send_poll
_tg99.Bot.send_message = _qx99_send_message


def _qx99_stop_card(sent: int, remaining: int) -> str:
    body = (
        f"প্রকাশ থামানো হয়েছে।\n"
        f"✅ পাঠানো হয়েছে: <b>{sent}</b>\n"
        f"📦 বাকি আছে: <b>{remaining}</b>\n\n"
        "▶️ <code>/resumequiz</code> — ঠিক যেখানে থেমেছে, সেখান থেকেই বাকিগুলো যাবে।"
    )
    with _cx99.suppress(Exception):
        return ui_box_html("Run Halted", body, emoji="⏹")
    return body


async def _qx99_notify(update, context, text, keyboard=None):
    token = _QX99_BYPASS.set(True)
    try:
        with _cx99.suppress(Exception):
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=text,
                parse_mode=_PM99.HTML, reply_markup=keyboard,
                disable_web_page_preview=True,
            )
    finally:
        _QX99_BYPASS.reset(token)


def _qx99_shield(callback):
    """Wrap a handler so a halted publishing run finishes cleanly."""
    if getattr(callback, "_qx99_shielded", False) or not callable(callback):
        return callback

    async def shielded(update, context, _cb=callback):
        uid = _qx99_uid(update)
        word = _qx99_cmd_word(update)
        run_mode = bool(uid) and word in _QX99_POST_CMDS
        token = None
        if run_mode:
            if not context.__dict__.get("_qx99_resumed"):
                _QX99_STOP.discard(uid)
            _QX99_ACTIVE[uid] = {
                "sent": 0, "rows": None,
                "emoji": word in ("postemoji", "pe"),
            }
            token = _QX99_RUN_UID.set(uid)
        try:
            return await _cb(update, context)
        except _QX99Stop:
            state = _QX99_ACTIVE.get(uid) or {}
            sent = int(state.get("sent") or 0)
            rows = list(state.get("rows") or [])
            with _cx99.suppress(Exception):
                if sent and rows:
                    buffer_remove_ids(uid, rows[:sent])
            remaining = 0
            with _cx99.suppress(Exception):
                remaining = int(buffer_count(uid))
            _QX99_PENDING[uid] = {
                "update": update, "context": context,
                "args": list(getattr(context, "args", []) or []),
                "word": word, "ts": _t99.time(), "sent": sent,
            }
            if token is not None:
                _QX99_RUN_UID.reset(token)
                token = None
            await _qx99_notify(update, context, _qx99_stop_card(sent, remaining))
            _qx99_log(f"run halted for {uid}: sent={sent} remaining={remaining}")
            raise _AHS99
        finally:
            if token is not None:
                _QX99_RUN_UID.reset(token)
            if run_mode:
                _QX99_ACTIVE.pop(uid, None)

    shielded._qx99_shielded = True  # type: ignore[attr-defined]
    with _cx99.suppress(Exception):
        shielded.__name__ = getattr(callback, "__name__", "shielded")
    return shielded


# ── /stopquiz · /resumequiz for every workspace user ─────────────────────────
def _qx99_may_run(uid: int) -> bool:
    with _cx99.suppress(Exception):
        if globals()["_qx99_hard_owner"](uid):  # type: ignore[index]
            return True
    with _cx99.suppress(Exception):
        if int(uid) in set(globals().get("OWNER_IDS_SET") or ()):
            return True
    with _cx99.suppress(Exception):
        return bool((_qx_access(int(uid)) or {}).get("ok"))
    return False


async def qx99_cmd_stopquiz(update, context):
    message = getattr(update, "effective_message", None)
    uid = _qx99_uid(update)
    if message is None or not _qx99_may_run(uid):
        raise _AHS99
    _QX99_STOP.add(uid)
    with _cx99.suppress(Exception):
        globals()["_stop_request_81"](uid)
    running = uid in _QX99_ACTIVE
    body = (
        "চলমান প্রকাশ এই মুহূর্তেই থামছে — পরবর্তী কোনো quiz আর যাবে না।\n\n"
        "▶️ চালু করতে: <code>/resumequiz</code>"
        if running else
        "এখন কোনো run চলছে না। পরবর্তী প্রকাশ শুরু হলে তা সাথে সাথে থেমে যাবে।\n\n"
        "▶️ বাতিল করতে: <code>/resumequiz</code>"
    )
    token = _QX99_BYPASS.set(True)
    try:
        with _cx99.suppress(Exception):
            await message.reply_text(
                ui_box_html("Stop Requested", body, emoji="⏹"), parse_mode=_PM99.HTML
            )
    finally:
        _QX99_BYPASS.reset(token)
    raise _AHS99


async def qx99_cmd_resumequiz(update, context):
    message = getattr(update, "effective_message", None)
    uid = _qx99_uid(update)
    if message is None or not _qx99_may_run(uid):
        raise _AHS99
    _QX99_STOP.discard(uid)
    with _cx99.suppress(Exception):
        globals()["_stop_clear_81"](uid)
    job = _QX99_PENDING.pop(uid, None)
    remaining = 0
    with _cx99.suppress(Exception):
        remaining = int(buffer_count(uid))

    token = _QX99_BYPASS.set(True)
    try:
        if not job or remaining <= 0:
            with _cx99.suppress(Exception):
                await message.reply_text(
                    ui_box_html(
                        "Run Cleared",
                        ("Halt সরানো হয়েছে — এখন আবার প্রকাশ করা যাবে।\n"
                         f"📦 Buffer-এ আছে: <b>{remaining}</b>"),
                        emoji="▶️",
                    ),
                    parse_mode=_PM99.HTML,
                )
            raise _AHS99
        with _cx99.suppress(Exception):
            await message.reply_text(
                ui_box_html(
                    "Resuming Run",
                    (f"যেখানে থেমেছিল সেখান থেকেই বাকি <b>{remaining}</b>টি quiz "
                     "একই গন্তব্যে যাচ্ছে…"),
                    emoji="▶️",
                ),
                parse_mode=_PM99.HTML,
            )
    finally:
        _QX99_BYPASS.reset(token)

    # Re-dispatch the interrupted command with its original target/arguments.
    old_update = job.get("update")
    old_context = job.get("context")
    with _cx99.suppress(Exception):
        old_context.args = list(job.get("args") or [])
    with _cx99.suppress(Exception):
        old_context.__dict__["_qx99_resumed"] = True
    callback = _QX99_RESUME_TARGETS.get(job.get("word") or "")
    if callable(callback) and old_update is not None and old_context is not None:
        with _cx99.suppress(_AHS99):
            await callback(old_update, old_context)
        with _cx99.suppress(Exception):
            old_context.__dict__.pop("_qx99_resumed", None)
    raise _AHS99


_QX99_RESUME_TARGETS: dict = {}


# ═════════════════════════════════════════════════════════════════════════════
# 2) MONGODB ANALYSIS + ON-DEMAND BACKUP CONSOLE (owner only)
# ═════════════════════════════════════════════════════════════════════════════
QX99_MONGO_URI = (
    os.getenv("MONGODB_URI", "").strip()
    or os.getenv("MONGO_URI", "").strip()
    or str(globals().get("MONGO_URI") or "").strip()
)
QX99_MONGO_DB = (
    os.getenv("MONGODB_DB", "").strip()
    or str(globals().get("MONGO_DB_NAME") or "").strip()
    or "qubix_db"
)

globals()["MONGO_URI"] = QX99_MONGO_URI
globals()["MONGO_DB_NAME"] = QX99_MONGO_DB



def _qx99_is_owner(uid: int) -> bool:
    with _cx99.suppress(Exception):
        if globals()["_qx99_hard_owner"](uid):  # type: ignore[index]
            return True
    with _cx99.suppress(Exception):
        return int(uid) in set(globals().get("OWNER_IDS_SET") or ())
    return False


def _qx99_client():
    if not QX99_MONGO_URI:
        return None
    factory = globals().get("_mongo_client")
    if callable(factory):
        client = factory()
        if client is not None:
            return client

    try:
        from pymongo import MongoClient
        client = MongoClient(
            QX99_MONGO_URI, serverSelectionTimeoutMS=10_000,
            connectTimeoutMS=10_000, socketTimeoutMS=30_000,
        )
        client.admin.command("ping")
        return client
    except Exception as error:
        _qx99_log(f"mongo connect failed: {error}", "warning")
        return None


def _qx99_local_count(table: str) -> int:
    with _cx99.suppress(Exception):
        conn = db_connect()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM [{table}]")  # noqa: S608
            return int(cur.fetchone()[0])
        finally:
            with _cx99.suppress(Exception):
                conn.close()
    return -1


def _qx99_tables():
    tables = globals().get("_MONGO_TABLES") or []
    return [(str(t[0]), str(t[1])) for t in tables] or [
        ("users", "users"), ("settings", "settings"), ("channels", "channels"),
    ]


def _qx99_pad(text: str, width: int) -> str:
    body = str(text)
    if len(body) > width:
        body = body[: max(1, width - 1)] + "…"
    return body.ljust(width)


def _qx99_analysis() -> str:
    """Rich, tabular SQLite ↔ MongoDB analysis report."""
    stamp = _dt99.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if not QX99_MONGO_URI:
        return ui_box_html(
            "Backup Console",
            ("☁️ MongoDB এখনো কনফিগার করা হয়নি।\n\n"
             "Render → Service → <b>Environment</b> এ যোগ করুন:\n"
             "│ <code>MONGODB_URI</code> = আপনার connection string\n"
             "│ <code>MONGODB_DB</code> = <code>qubix_db</code>\n\n"
             "সেভ করে service redeploy দিলে এই কনসোল স্বয়ংক্রিয়ভাবে চালু হবে।"),
            emoji="🔐",
        )
    client = _qx99_client()
    if client is None:
        return ui_box_html(
            "Backup Console",
            ("☁️ MongoDB-তে সংযোগ করা যাচ্ছে না।\n"
             f"Cluster: <code>{h(QX99_MONGO_URI.split('@')[-1][:48])}</code>\n"
             "Atlas Network Access (0.0.0.0/0) ও user/password যাচাই করে আবার চেষ্টা করুন।"),
            emoji="⚠️",
        )


    rows = []
    local_total = 0
    remote_total = 0
    meta = {}
    try:
        db = client[QX99_MONGO_DB]
        with _cx99.suppress(Exception):
            meta = db["_meta"].find_one({"_id": "backup_info"}) or {}
        for table, coll in _qx99_tables():
            local = _qx99_local_count(table)
            remote = -1
            with _cx99.suppress(Exception):
                remote = int(db[coll].count_documents({}))
            local_total += max(0, local)
            remote_total += max(0, remote)
            if local <= 0 and remote <= 0:
                mark = "—"
            elif remote >= local:
                mark = "OK"
            elif remote <= 0:
                mark = "MISS"
            else:
                mark = "LAG"
            rows.append((table, local, remote, mark))
    finally:
        with _cx99.suppress(Exception):
            client.close()

    head = f"{_qx99_pad('TABLE', 20)}{_qx99_pad('LOCAL', 7)}{_qx99_pad('CLOUD', 7)}STATUS"
    line = "─" * 42
    body_rows = "\n".join(
        f"{_qx99_pad(t, 20)}{_qx99_pad(max(l, 0), 7)}{_qx99_pad(max(r, 0), 7)}{m}"
        for (t, l, r, m) in rows
    )
    drift = local_total - remote_total
    health = "🟢 Synchronised" if drift <= 0 else (
        "🟡 Partial drift" if drift <= 25 else "🔴 Backup required"
    )
    last = str(meta.get("last_backup_at") or "কখনো নয়")
    by = str(meta.get("requester") or "—")

    body = (
        f"🗄 <b>Database:</b> <code>{h(QX99_MONGO_DB)}</code>\n"
        f"☁️ <b>Cluster:</b> <code>{h(QX99_MONGO_URI.split('@')[-1].split('/')[0][:40])}</code>\n"
        f"🕒 <b>Report:</b> <code>{h(stamp)}</code>\n"
        f"📌 <b>শেষ ব্যাকআপ:</b> <code>{h(last[:32])}</code> ({h(by[:24])})\n\n"
        f"<pre>{h(head)}\n{h(line)}\n{h(body_rows)}\n{h(line)}\n"
        f"{h(_qx99_pad('TOTAL', 20))}{h(_qx99_pad(local_total, 7))}"
        f"{h(_qx99_pad(remote_total, 7))}</pre>\n"
        f"📊 <b>Drift:</b> <code>{drift}</code> row(s)\n"
        f"🧭 <b>Health:</b> {health}\n\n"
        "🗄 <b>Backup Now</b> চাপলেই সব টেবিল cloud-এ push হবে — "
        "কোনো অটো ব্যাকআপ চলে না, সম্পূর্ণ আপনার নিয়ন্ত্রণে।"
    )
    return ui_box_html("Backup Console", body, emoji="🗄")


def _qx99_console_kb() -> _IKM99:
    return _IKM99([
        [_IKB99("🗄 Backup Now", callback_data="qx99:bk"),
         _IKB99("🔄 Refresh", callback_data="qx99:rf")],
        [_IKB99("⬇️ Restore from Cloud", callback_data="qx99:rs")],
        [_IKB99("✖ Close", callback_data="qx99:cl")],
    ])


async def qx99_cmd_backup(update, context):
    message = getattr(update, "effective_message", None)
    uid = _qx99_uid(update)
    if message is None:
        raise _AHS99
    if not _qx99_is_owner(uid):
        raise _AHS99
    token = _QX99_BYPASS.set(True)
    try:
        card = await asyncio.get_event_loop().run_in_executor(None, _qx99_analysis)
        with _cx99.suppress(Exception):
            await message.reply_text(
                card, parse_mode=_PM99.HTML, reply_markup=_qx99_console_kb(),
                disable_web_page_preview=True,
            )
    finally:
        _QX99_BYPASS.reset(token)
    raise _AHS99


async def qx99_cb_backup(update, context):
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    uid = 0
    with _cx99.suppress(Exception):
        uid = int(query.from_user.id)
    if not _qx99_is_owner(uid):
        with _cx99.suppress(Exception):
            await query.answer("Owner only.", show_alert=True)
        raise _AHS99
    action = (query.data or "").split(":")[-1]
    token = _QX99_BYPASS.set(True)
    try:
        if action == "cl":
            with _cx99.suppress(Exception):
                await query.answer("Closed")
            with _cx99.suppress(Exception):
                await query.message.delete()
            raise _AHS99

        if action == "bk":
            with _cx99.suppress(Exception):
                await query.answer("Backing up…")
            with _cx99.suppress(Exception):
                await query.edit_message_text(
                    ui_box_html("Backup Running", "☁️ সব টেবিল cloud-এ push হচ্ছে…", emoji="⏳"),
                    parse_mode=_PM99.HTML,
                )
            runner = globals().get("mongo_backup_now")
            ok_n = fail_n = 0
            summary = ""
            if callable(runner):
                ok_n, fail_n, summary = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: runner(requester=f"owner-{uid}")
                )
            report = await asyncio.get_event_loop().run_in_executor(None, _qx99_analysis)
            card = (
                ui_box_html(
                    "Backup Complete",
                    (f"✅ Tables saved: <b>{ok_n}</b>\n❌ Failed: <b>{fail_n}</b>\n\n"
                     f"<pre>{h(str(summary)[:700])}</pre>"),
                    emoji="✅",
                )
                + "\n\n" + report
            )
            with _cx99.suppress(Exception):
                await query.edit_message_text(
                    card[:4000], parse_mode=_PM99.HTML,
                    reply_markup=_qx99_console_kb(), disable_web_page_preview=True,
                )
            raise _AHS99

        if action == "rs":
            with _cx99.suppress(Exception):
                await query.answer("Restoring…")
            runner = globals().get("mongo_restore_now")
            ok_n = fail_n = 0
            summary = "Restore unavailable."
            if callable(runner):
                ok_n, fail_n, summary = await asyncio.get_event_loop().run_in_executor(
                    None, runner
                )
            with _cx99.suppress(Exception):
                await query.edit_message_text(
                    ui_box_html(
                        "Restore Complete",
                        (f"✅ Tables restored: <b>{ok_n}</b>\n❌ Failed: <b>{fail_n}</b>\n\n"
                         f"<pre>{h(str(summary)[:700])}</pre>"),
                        emoji="⬇️",
                    )[:4000],
                    parse_mode=_PM99.HTML, reply_markup=_qx99_console_kb(),
                )
            raise _AHS99

        with _cx99.suppress(Exception):
            await query.answer("Refreshed")
        report = await asyncio.get_event_loop().run_in_executor(None, _qx99_analysis)
        with _cx99.suppress(Exception):
            await query.edit_message_text(
                report, parse_mode=_PM99.HTML, reply_markup=_qx99_console_kb(),
                disable_web_page_preview=True,
            )
    finally:
        _QX99_BYPASS.reset(token)
    raise _AHS99


# ═════════════════════════════════════════════════════════════════════════════
# 3) Wiring
# ═════════════════════════════════════════════════════════════════════════════
with _cx99.suppress(Exception):
    QX_WORKSPACE_COMMANDS |= {"stopquiz", "resumequiz"}
with _cx99.suppress(Exception):
    for _n99 in ("stopquiz", "resumequiz"):
        QX_RETIRED_USER_COMMANDS.discard(_n99)

globals()["cmd_stopquiz_81"] = qx99_cmd_stopquiz
globals()["cmd_resumequiz_81"] = qx99_cmd_resumequiz

_qx99_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx99_prev_build_app() if callable(_qx99_prev_build_app) else None
    if app is None:
        return app

    register = globals().get("_register_dual_command")
    for name, callback in (
        ("stopquiz", qx99_cmd_stopquiz),
        ("resumequiz", qx99_cmd_resumequiz),
        ("qbackup", qx99_cmd_backup),
        ("mongoconsole", qx99_cmd_backup),
    ):
        with _cx99.suppress(Exception):
            if callable(register):
                register(app, name, callback, group=-1060)
            else:
                app.add_handler(CommandHandler(name, callback), group=-1060)

    with _cx99.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx99_cb_backup, pattern=r"^qx99:"), group=-1060
        )

    # Shield every registered handler so a halted run ends cleanly, and keep a
    # resume map so /resumequiz can continue the exact interrupted job.
    shielded = 0
    with _cx99.suppress(Exception):
        for group_handlers in app.handlers.values():
            for handler in group_handlers:
                cb = getattr(handler, "callback", None)
                if not callable(cb) or getattr(cb, "_qx99_shielded", False):
                    continue
                wrapped = _qx99_shield(cb)
                with _cx99.suppress(Exception):
                    handler.callback = wrapped
                    shielded += 1
                name = ""
                with _cx99.suppress(Exception):
                    cmds = getattr(handler, "commands", None) or ()
                    name = next(iter(cmds), "")
                if name and str(name).lower() in _QX99_POST_CMDS:
                    _QX99_RESUME_TARGETS[str(name).lower()] = wrapped

    _qx99_log(f"run control + backup console wired (shielded handlers: {shielded})")
    return app


_qx99_log("section 99 loaded (instant stop, true resume, Mongo analysis console)")


# ── Owner surface: expose the backup console in the owner panel & "/" menu ───
with _cx99.suppress(Exception):
    if "🗄" not in QX94_OWNER_CARD:
        QX94_OWNER_CARD = QX94_OWNER_CARD + (
            "\n\n🗄 <b>Cloud backup console</b>\n"
            "<code>/qbackup</code> — MongoDB analysis table + on-demand backup/restore "
            "(অটো নয়, শুধু আপনি চাইলে)।"
        )
        globals()["QX94_OWNER_CARD"] = QX94_OWNER_CARD

with _cx99.suppress(Exception):
    _menu99 = list(globals().get("QX94_OWNER_MENU_COMMANDS") or [])
    if _menu99 and not any(n == "qbackup" for n, _ in _menu99):
        _menu99.append(("qbackup", "MongoDB backup console"))
        globals()["QX94_OWNER_MENU_COMMANDS"] = _menu99[:30]
