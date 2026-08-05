# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 90 — QUBIX MULTI-TENANT USER BOTS (2026-08-03)
#
# What this section does:
#   1. Renames the product surface to "Qubix".
#   2. REMOVES every AI/solve/generation feature from ordinary users on the
#      MAIN Qubix bot (quiz solving, image solving, AI chat replies, .gen …).
#      The main bot becomes a control panel only.
#   3. Adds a multi-tenant runtime: a user submits their OWN @BotFather token
#      and Qubix runs that bot for them, on demand, with the FULL owner-grade
#      quiz workflow (forwarded quiz → unlimited generation on that topic,
#      image → quiz, reply-to-text → unlimited quiz, channel posting,
#      forum topic posting) — identical to how the owner's inbox works.
#   4. Access control:
#        • Owner-approved users  → full access (token persisted in DB).
#        • Everyone else         → time-limited trial set by the owner
#          (token kept in memory only, never written to the DB).
#        • On expiry the user gets a professional card with their user id and
#          the owner contact to request permission.
#   5. On-demand lifecycle: idle bots perform no work and resume silently on
#      the next update; users never need a separate wake command.
# ══════════════════════════════════════════════════════════════════════════════

import contextvars as _qx_cv

_qx_log = logging.getLogger("qubix")

# ─────────────────────────────────────────────────────────────────────────────
# Branding
# ─────────────────────────────────────────────────────────────────────────────
BOT_BRAND = "Qubix"
globals()["BOT_BRAND"] = "Qubix"
QX_BRAND = "Qubix"
QX_OWNER_CONTACT = str(globals().get("OWNER_CONTACT") or "@Your_Himus")

QX_DEFAULT_TRIAL_SECONDS = 15 * 60      # owner-tunable via /qtrial
# A Telegram bot that has fully stopped polling cannot receive the command that
# is supposed to wake it.  Tenant bots therefore keep only their lightweight
# update listener alive while idle; work starts naturally with the next update.
QX_IDLE_STOP_SECONDS = 0
QX_WATCHDOG_TICK = 20                   # seconds

# Commands a tenant must never run on their own bot (owner-infrastructure).
QX_BLOCKED_CHILD_COMMANDS = {
    "broadcast", "restart", "promote", "demote", "ban", "unban", "banned",
    "mongobackup", "mongorestore", "mongostatus", "addkey", "keys", "delkey",
    "gemini", "mistral", "mk", "models", "advmode", "advadd", "advrm",
    "advprio", "elevenlabs", "el", "ellog", "el_log", "stats", "userinfo",
    "private_send", "send_private", "qapprove", "qrevoke", "qtrial", "qbots",
    "qkill", "qstart",
}

# Commands ordinary users may still use on the MAIN Qubix bot.
QX_MAIN_ALLOWED_COMMANDS = {
    "start", "help", "cmd", "id", "myid", "addbot", "mybot", "removebot",
    "delbot", "wake", "q", "status",
}

_QX_TOKEN_RE = re.compile(r"\b(\d{6,}:[A-Za-z0-9_\-]{30,})\b")

# Acting-owner override — lets a tenant behave as "owner" inside their own bot
# without touching the real OWNER_IDS.
_QX_ACTING_OWNER = _qx_cv.ContextVar("qx_acting_owner", default=0)

# Trial tokens are deliberately memory-only (never persisted).
_QX_TRIAL_TOKENS: Dict[int, str] = {}
_QX_RUNNERS: Dict[int, "QxRunner"] = {}
_QX_MAIN_APP = None


# ─────────────────────────────────────────────────────────────────────────────
# Owner-check patching
# ─────────────────────────────────────────────────────────────────────────────
def _qx_acting(uid) -> bool:
    try:
        cur = int(_QX_ACTING_OWNER.get() or 0)
        return bool(cur) and int(uid or 0) == cur
    except Exception:
        return False


_qx_prev_is_owner = globals().get("is_owner")
_qx_prev_is_admin = globals().get("is_admin")
_qx_prev_is_owner_id = globals().get("_is_owner_id")


def is_owner(user_id) -> bool:  # noqa: F811
    if _qx_acting(user_id):
        return True
    try:
        return bool(_qx_prev_is_owner(user_id)) if _qx_prev_is_owner else False
    except Exception:
        return False


def is_admin(user_id) -> bool:  # noqa: F811
    if _qx_acting(user_id):
        return True
    try:
        return bool(_qx_prev_is_admin(user_id)) if _qx_prev_is_admin else False
    except Exception:
        return False


def _is_owner_id(user_id) -> bool:  # noqa: F811
    if _qx_acting(user_id):
        return True
    try:
        return bool(_qx_prev_is_owner_id(user_id)) if _qx_prev_is_owner_id else False
    except Exception:
        return False


globals()["is_owner"] = is_owner
globals()["is_admin"] = is_admin
globals()["_is_owner_id"] = _is_owner_id


def _qx_real_owner(uid) -> bool:
    try:
        return bool(_qx_prev_is_owner_id and _qx_prev_is_owner_id(uid)) or (
            bool(_qx_prev_is_owner) and bool(_qx_prev_is_owner(uid))
        )
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────────────────────
def _qx_db_init() -> None:
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS qubix_bots(
                   user_id      INTEGER PRIMARY KEY,
                   token        TEXT NOT NULL,
                   bot_username TEXT,
                   added_at     REAL,
                   last_active  REAL)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS qubix_access(
                   user_id     INTEGER PRIMARY KEY,
                   mode        TEXT NOT NULL DEFAULT 'trial',
                   expires_at  REAL,
                   granted_at  REAL,
                   warned      INTEGER NOT NULL DEFAULT 0)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS qubix_settings(
                   key   TEXT PRIMARY KEY,
                   value TEXT)"""
        )
        conn.commit()
    finally:
        with contextlib.suppress(Exception):
            conn.close()


with contextlib.suppress(Exception):
    _qx_db_init()


def _qx_setting(key: str, default: str = "") -> str:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT value FROM qubix_settings WHERE key=?", (key,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            return str(row["value"])
    return default


def _qx_set_setting(key: str, value: str) -> None:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO qubix_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )
            conn.commit()
        finally:
            conn.close()


def _qx_trial_seconds() -> int:
    try:
        return max(60, int(float(_qx_setting("trial_seconds", str(QX_DEFAULT_TRIAL_SECONDS)))))
    except Exception:
        return QX_DEFAULT_TRIAL_SECONDS


def _qx_access_row(uid: int) -> Optional[sqlite3.Row]:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            return conn.execute(
                "SELECT * FROM qubix_access WHERE user_id=?", (int(uid),)
            ).fetchone()
        finally:
            conn.close()
    return None


def _qx_access_write(uid: int, mode: str, expires_at: Optional[float]) -> None:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            conn.execute(
                """INSERT INTO qubix_access(user_id,mode,expires_at,granted_at,warned)
                   VALUES(?,?,?,?,0)
                   ON CONFLICT(user_id) DO UPDATE SET
                       mode=excluded.mode,
                       expires_at=excluded.expires_at,
                       granted_at=excluded.granted_at,
                       warned=0""",
                (int(uid), str(mode), expires_at, time.time()),
            )
            conn.commit()
        finally:
            conn.close()


def _qx_mark_warned(uid: int) -> None:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            conn.execute("UPDATE qubix_access SET warned=1 WHERE user_id=?", (int(uid),))
            conn.commit()
        finally:
            conn.close()


def _qx_save_bot(uid: int, token: str, username: str) -> None:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            conn.execute(
                """INSERT INTO qubix_bots(user_id,token,bot_username,added_at,last_active)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       token=excluded.token,
                       bot_username=excluded.bot_username,
                       last_active=excluded.last_active""",
                (int(uid), str(token), str(username or ""), time.time(), time.time()),
            )
            conn.commit()
        finally:
            conn.close()


def _qx_delete_bot(uid: int) -> None:
    _QX_TRIAL_TOKENS.pop(int(uid), None)
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            conn.execute("DELETE FROM qubix_bots WHERE user_id=?", (int(uid),))
            conn.commit()
        finally:
            conn.close()


def _qx_get_token(uid: int) -> Optional[str]:
    uid = int(uid)
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT token FROM qubix_bots WHERE user_id=?", (uid,)
            ).fetchone()
        finally:
            conn.close()
        if row and row["token"]:
            return str(row["token"])
    return _QX_TRIAL_TOKENS.get(uid)


def _qx_all_saved_bots() -> List[sqlite3.Row]:
    with contextlib.suppress(Exception):
        conn = db_connect()
        try:
            return list(
                conn.execute(
                    "SELECT user_id,bot_username,added_at,last_active FROM qubix_bots "
                    "ORDER BY added_at DESC"
                ).fetchall()
            )
        finally:
            conn.close()
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Access resolution
# ─────────────────────────────────────────────────────────────────────────────
def _qx_access(uid: int) -> Dict[str, Any]:
    """Return {'ok', 'mode', 'expires_at', 'remaining'} for a tenant."""
    uid = int(uid or 0)
    if _qx_real_owner(uid):
        return {"ok": True, "mode": "owner", "expires_at": None, "remaining": None}

    row = _qx_access_row(uid)
    now = time.time()

    if row and str(row["mode"]) == "approved":
        exp = row["expires_at"]
        if exp is None:
            return {"ok": True, "mode": "approved", "expires_at": None, "remaining": None}
        if float(exp) > now:
            return {
                "ok": True, "mode": "approved",
                "expires_at": float(exp), "remaining": float(exp) - now,
            }
        return {"ok": False, "mode": "expired", "expires_at": float(exp), "remaining": 0}

    if row and str(row["mode"]) == "blocked":
        return {"ok": False, "mode": "blocked", "expires_at": None, "remaining": 0}

    if not row:
        exp = now + _qx_trial_seconds()
        _qx_access_write(uid, "trial", exp)
        return {"ok": True, "mode": "trial", "expires_at": exp, "remaining": exp - now}

    exp = float(row["expires_at"] or 0)
    if exp > now:
        return {"ok": True, "mode": "trial", "expires_at": exp, "remaining": exp - now}
    return {"ok": False, "mode": "trial_expired", "expires_at": exp, "remaining": 0}


def _qx_human_left(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unlimited"
    seconds = int(max(0, seconds))
    if seconds >= 86400:
        return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"
    if seconds >= 3600:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    if seconds >= 60:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds}s"


def _qx_expired_card(uid: int, name: str = "") -> str:
    return (
        "🔒 <b>Qubix — Access Expired</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Name:</b> {h(name or '—')}\n"
        f"🆔 <b>Your User ID:</b> <code>{int(uid)}</code>\n"
        "⏳ <b>Status:</b> Trial period finished\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "আপনার ট্রায়াল সময় শেষ হয়েছে। পূর্ণ access নিতে হলে উপরের "
        "<b>User ID</b> টি কপি করে owner-কে পাঠান:\n"
        f"👑 <b>Owner:</b> {h(QX_OWNER_CONTACT)}\n\n"
        "<i>Approval পাওয়ার সাথে সাথে আপনার নিজের বট আবার সম্পূর্ণভাবে চালু হবে।</i>"
    )


def _qx_access_card(uid: int, name: str, st: Dict[str, Any], username: str = "") -> str:
    mode = {
        "owner": "👑 Owner",
        "approved": "✅ Approved",
        "trial": "🧪 Trial",
    }.get(str(st.get("mode")), "🔒 Locked")
    lines = [
        "🤖 <b>Qubix — My Bot</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Name:</b> {h(name or '—')}",
        f"🆔 <b>User ID:</b> <code>{int(uid)}</code>",
        f"🔑 <b>Access:</b> {mode}",
        f"⏳ <b>Time left:</b> {h(_qx_human_left(st.get('remaining')))}",
    ]
    if username:
        lines.append(f"🔗 <b>Your bot:</b> @{h(username)}")
    running = int(uid) in _QX_RUNNERS and _QX_RUNNERS[int(uid)].running
    lines.append(f"⚡ <b>Runtime:</b> {'🟢 Active' if running else '⚪ Sleeping (idle)'}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    if not st.get("ok"):
        lines.append(f"Access নিতে owner-কে জানান: {h(QX_OWNER_CONTACT)}")
    else:
        lines.append("আপনার bot idle অবস্থায়ও পরের command স্বয়ংক্রিয়ভাবে গ্রহণ করবে।")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Child (tenant) bot runtime
# ─────────────────────────────────────────────────────────────────────────────
async def _qx_child_gate(update, context) -> None:
    """group=-1000 gate installed on every tenant bot."""
    app = context.application
    owner_uid = int(app.bot_data.get("qx_tenant_uid") or 0)
    user = getattr(update, "effective_user", None)
    uid = int(getattr(user, "id", 0) or 0)

    if uid and uid != owner_uid:
        with contextlib.suppress(Exception):
            msg = getattr(update, "effective_message", None)
            if msg:
                await msg.reply_text(
                    "🔒 এই বটটি ব্যক্তিগত। শুধুমাত্র এর মালিক ব্যবহার করতে পারবেন।\n"
                    f"নিজের বট চালাতে চাইলে {QX_BRAND} ব্যবহার করুন।"
                )
        raise ApplicationHandlerStop

    st = _qx_access(owner_uid)
    if not st["ok"]:
        with contextlib.suppress(Exception):
            msg = getattr(update, "effective_message", None)
            if msg:
                await msg.reply_text(
                    _qx_expired_card(owner_uid, app.bot_data.get("qx_tenant_name", "")),
                    parse_mode=ParseMode.HTML,
                )
        asyncio.create_task(_qx_stop_runner(owner_uid, reason="access expired"))
        raise ApplicationHandlerStop

    text = ""
    with contextlib.suppress(Exception):
        text = str(getattr(getattr(update, "effective_message", None), "text", "") or "")
    if text[:1] in ("/", "."):
        cmd = re.split(r"[\s@]", text[1:].strip(), 1)[0].lower()
        if cmd in QX_BLOCKED_CHILD_COMMANDS:
            with contextlib.suppress(Exception):
                await update.effective_message.reply_text(
                    "⛔ এই command টি Qubix infrastructure-এর জন্য সংরক্ষিত।"
                )
            raise ApplicationHandlerStop

    _QX_ACTING_OWNER.set(owner_uid)
    app.bot_data["qx_last_active"] = time.time()


async def _qx_child_menu_router(update, context) -> None:
    """Route the personal-bot workspace menu before any cloned legacy gate.

    Tenant applications clone a large handler graph where several callbacks
    share groups.  Dispatching the current workspace menu explicitly keeps the
    visible buttons independent from that legacy ordering.
    """
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "")
    if query is None or not data.startswith("qx93:"):
        return

    tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
    actor = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not tenant or actor != tenant:
        with contextlib.suppress(Exception):
            await query.answer("This personal bot is private.", show_alert=True)
        raise ApplicationHandlerStop
    if not _qx_access(tenant).get("ok"):
        with contextlib.suppress(Exception):
            await query.answer("Access expired.", show_alert=True)
        raise ApplicationHandlerStop

    _QX_ACTING_OWNER.set(tenant)
    context.application.bot_data["qx_last_active"] = time.time()
    callback = globals().get("qx93_on_callback")
    if callable(callback):
        try:
            await callback(update, context)
        except ApplicationHandlerStop:
            raise
        except Exception as error:
            with contextlib.suppress(Exception):
                logger.warning("[QUBIX-90] personal menu callback failed: %s", error)
            with contextlib.suppress(Exception):
                await query.answer("Menu unavailable—send /menu once.", show_alert=True)
            raise ApplicationHandlerStop
        # qx93_on_callback already answers the callback and edits the card.
        # Stop here: answering the same callback again makes Telegram reject it
        # and was the reason personal-bot buttons appeared completely inert.
        raise ApplicationHandlerStop
    with contextlib.suppress(Exception):
        await query.answer("Menu unavailable—send /menu once.", show_alert=True)
    raise ApplicationHandlerStop


class QxRunner:
    """Runs one tenant's Telegram bot inside the main event loop."""

    def __init__(self, uid: int, token: str, name: str = ""):
        self.uid = int(uid)
        self.token = str(token)
        self.name = name
        self.app = None
        self.username = ""
        self.running = False

    async def start(self) -> Tuple[bool, str]:
        if self.running:
            return True, self.username
        template = globals().get("_QX_MAIN_APP")
        if template is None:
            return False, "runtime not ready"
        try:
            child = ApplicationBuilder().token(self.token).concurrent_updates(True).build()
        except Exception as exc:
            return False, f"invalid token ({exc})"

        try:
            me = await child.bot.get_me()
            self.username = me.username or ""
        except Exception as exc:
            with contextlib.suppress(Exception):
                await child.shutdown()
            return False, f"token rejected by Telegram ({exc})"

        # Clone the owner-grade workflow handlers onto the tenant bot.
        cloned = 0
        for group, handlers in sorted(template.handlers.items()):
            for handler in handlers:
                if _qx_is_main_only(handler):
                    continue
                with contextlib.suppress(Exception):
                    child.add_handler(handler, group=group)
                    cloned += 1
        with contextlib.suppress(Exception):
            # Install the universal callback dispatcher before polling starts.
            # Late QxRunner wrappers used to add it after start_polling(), which
            # left a real race where a freshly pressed inline button could enter
            # the cloned legacy gates before the dispatcher existed.
            dispatcher = globals().get("_qx109_dispatch_callback")
            if callable(dispatcher):
                dispatcher_group = min(
                    getattr(child, "handlers", {}).keys(),
                    default=0,
                ) - 1
                child.add_handler(
                    CallbackQueryHandler(dispatcher),
                    group=dispatcher_group,
                )
                child.bot_data["qx109_dispatcher"] = True
                child.bot_data["qx109_dispatcher_group"] = dispatcher_group

            # Install before initialize/start_polling.  Adding this only after
            # the child starts creates a race where freshly displayed buttons
            # have no reliable callback route.
            child.add_handler(
                CallbackQueryHandler(_qx_child_menu_router, pattern=r"^qx93:"),
                group=-10000,
            )
            child.add_handler(
                MessageHandler(filters.ALL, _qx_child_gate), group=-1000
            )
            child.add_handler(
                CallbackQueryHandler(_qx_child_gate), group=-1000
            )
        for err_handler in list(getattr(template, "error_handlers", {}) or {}):
            with contextlib.suppress(Exception):
                child.add_error_handler(err_handler)

        child.bot_data["qx_tenant_uid"] = self.uid
        child.bot_data["qx_tenant_name"] = self.name
        child.bot_data["qx_last_active"] = time.time()

        try:
            await child.initialize()
            await child.start()
            await child.updater.start_polling(drop_pending_updates=True)
        except Exception as exc:
            with contextlib.suppress(Exception):
                await child.stop()
            with contextlib.suppress(Exception):
                await child.shutdown()
            return False, f"could not start polling ({exc})"

        self.app = child
        self.running = True
        _qx_log.info(
            "[QUBIX] tenant bot @%s started for uid=%s (%s handlers cloned)",
            self.username, self.uid, cloned,
        )
        return True, self.username

    async def stop(self) -> None:
        self.running = False
        app, self.app = self.app, None
        if app is None:
            return
        with contextlib.suppress(Exception):
            if app.updater and app.updater.running:
                await app.updater.stop()
        with contextlib.suppress(Exception):
            await app.stop()
        with contextlib.suppress(Exception):
            await app.shutdown()
        _qx_log.info("[QUBIX] tenant bot stopped for uid=%s", self.uid)

    def idle_for(self) -> float:
        if not self.app:
            return 0.0
        return time.time() - float(self.app.bot_data.get("qx_last_active") or time.time())


async def _qx_start_runner(uid: int, name: str = "") -> Tuple[bool, str]:
    uid = int(uid)
    token = _qx_get_token(uid)
    if not token:
        return False, "no token registered"
    runner = _QX_RUNNERS.get(uid)
    if runner and runner.running:
        return True, runner.username
    runner = QxRunner(uid, token, name)
    ok, info = await runner.start()
    if ok:
        _QX_RUNNERS[uid] = runner
    return ok, info


async def _qx_stop_runner(uid: int, reason: str = "") -> None:
    runner = _QX_RUNNERS.pop(int(uid), None)
    if runner:
        await runner.stop()
        if reason:
            _qx_log.info("[QUBIX] uid=%s stopped: %s", uid, reason)


async def _qx_notify(uid: int, text: str) -> None:
    main_app = globals().get("_QX_MAIN_APP")
    if not main_app:
        return
    with contextlib.suppress(Exception):
        await main_app.bot.send_message(
            chat_id=int(uid), text=text, parse_mode=ParseMode.HTML
        )


async def _qx_watchdog() -> None:
    """Stops idle bots and enforces access expiry."""
    while True:
        try:
            await asyncio.sleep(QX_WATCHDOG_TICK)
            for uid in list(_QX_RUNNERS.keys()):
                runner = _QX_RUNNERS.get(uid)
                if not runner or not runner.running:
                    continue
                st = _qx_access(uid)
                if not st["ok"]:
                    await _qx_stop_runner(uid, reason="access expired")
                    row = _qx_access_row(uid)
                    if not row or not int(row["warned"] or 0):
                        _qx_mark_warned(uid)
                        await _qx_notify(uid, _qx_expired_card(uid, runner.name))
                    continue
                # Do not stop polling for inactivity.  A stopped Telegram bot
                # cannot see the next command, so true command-driven auto-wake
                # is impossible.  Keeping the listener alive is effectively
                # idle (no generation/posting work) and resumes silently.
        except asyncio.CancelledError:
            raise
        except Exception:
            _qx_log.exception("[QUBIX] watchdog tick failed")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN bot — user surface (control panel only)
# ─────────────────────────────────────────────────────────────────────────────
QX_USER_HELP = (
    "🤖 <b>Qubix — Personal Quiz Bot Runner</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "Qubix এখন আপনার <b>নিজের বট</b> চালিয়ে দেয়। এখানে AI বা quiz solve হয় না — "
    "সব কাজ হবে <b>আপনার নিজের বটের ইনবক্সে</b>।\n\n"
    "<b>শুরু করবেন যেভাবে:</b>\n"
    "1️⃣ @BotFather → <code>/newbot</code> → token নিন\n"
    "2️⃣ এখানে পাঠান: <code>/addbot 123456:ABC-token</code>\n"
    "3️⃣ আপনার বটে গিয়ে কাজ শুরু করুন\n\n"
    "<b>আপনার বটে যা পারবেন:</b>\n"
    "• 📥 কোনো quiz forward করলে সেই টপিকে <b>আনলিমিটেড quiz generation</b>\n"
    "• 🖼️ ছবি থেকে quiz generation\n"
    "• ✍️ যেকোনো টেক্সটে reply দিয়ে আনলিমিটেড quiz\n"
    "• 📢 নিজের channel/group-এ add করে সরাসরি post\n"
    "• 🧵 Forum topic তৈরি করে সেখানে reply দিয়ে quiz পাঠানো\n\n"
    "<b>Commands:</b>\n"
    "<code>/addbot &lt;token&gt;</code> — বট যুক্ত করুন\n"
    "<code>/mybot</code> — bot status\n"
    "<code>/removebot</code> — বট সরান\n"
    "<code>/myid</code> — আপনার User ID\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    f"👑 Access/permission: {QX_OWNER_CONTACT}"
)


async def qx_cmd_start(update, context):
    user = update.effective_user
    st = _qx_access(user.id)
    await update.effective_message.reply_text(QX_USER_HELP, parse_mode=ParseMode.HTML)
    if not st["ok"]:
        await update.effective_message.reply_text(
            _qx_expired_card(user.id, user.full_name), parse_mode=ParseMode.HTML
        )
    raise ApplicationHandlerStop


async def qx_cmd_myid(update, context):
    u = update.effective_user
    await update.effective_message.reply_text(
        "🪪 <b>Qubix Identity</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Name:</b> {h(u.full_name)}\n"
        f"🆔 <b>User ID:</b> <code>{u.id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Access চাইতে এই ID টি {h(QX_OWNER_CONTACT)}-কে পাঠান।",
        parse_mode=ParseMode.HTML,
    )
    raise ApplicationHandlerStop


async def _qx_register_token(update, uid: int, name: str, token: str):
    st = _qx_access(uid)
    if not st["ok"]:
        await update.effective_message.reply_text(
            _qx_expired_card(uid, name), parse_mode=ParseMode.HTML
        )
        return
    msg = await update.effective_message.reply_text("⏳ Token যাচাই করা হচ্ছে…")

    # Validate before storing.
    try:
        probe = ApplicationBuilder().token(token).build()
        me = await probe.bot.get_me()
        username = me.username or ""
        with contextlib.suppress(Exception):
            await probe.shutdown()
    except Exception as exc:
        with contextlib.suppress(Exception):
            await msg.edit_text(
                "❌ <b>Token গ্রহণ করা যায়নি</b>\n"
                f"<code>{h(str(exc)[:200])}</code>\n\n"
                "@BotFather থেকে সঠিক token কপি করে আবার চেষ্টা করুন।",
                parse_mode=ParseMode.HTML,
            )
        return

    await _qx_stop_runner(uid, reason="token replaced")
    if st["mode"] in ("approved", "owner"):
        _qx_save_bot(uid, token, username)
        stored = "🔐 Approved — token নিরাপদে সংরক্ষিত"
    else:
        _QX_TRIAL_TOKENS[int(uid)] = token
        stored = "🧪 Trial — token শুধু চলতি session-এ রাখা হলো (DB-তে save হয়নি)"

    ok, info = await _qx_start_runner(uid, name)
    if not ok:
        with contextlib.suppress(Exception):
            await msg.edit_text(
                f"⚠️ বট চালু করা গেল না: <code>{h(str(info)[:200])}</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    with contextlib.suppress(Exception):
        await msg.edit_text(
            "✅ <b>আপনার বট চালু হয়েছে</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Bot:</b> @{h(username)}\n"
            f"{stored}\n"
            f"⏳ <b>Access:</b> {h(_qx_human_left(st.get('remaining')))}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"এখন @{h(username)}-এ গিয়ে quiz forward করুন, ছবি দিন বা টেক্সটে reply করুন — "
            "আনলিমিটেড quiz generate হবে।\n"
            "<i>নিষ্ক্রিয় অবস্থায় বট নিজে থেকেই idle থাকবে; পরের command-এ নীরবে কাজ শুরু করবে।</i>",
            parse_mode=ParseMode.HTML,
        )


async def qx_cmd_addbot(update, context):
    u = update.effective_user
    text = str(update.effective_message.text or "")
    m = _QX_TOKEN_RE.search(text)
    if not m:
        await update.effective_message.reply_text(
            "ℹ️ ব্যবহার: <code>/addbot 123456789:AA...token</code>\n"
            "@BotFather → /newbot থেকে token নিন।",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop
    with contextlib.suppress(Exception):
        await update.effective_message.delete()   # keep the token private
    await _qx_register_token(update, u.id, u.full_name, m.group(1))
    raise ApplicationHandlerStop


async def qx_cmd_mybot(update, context):
    u = update.effective_user
    arg = ""
    parts = str(update.effective_message.text or "").split()
    if len(parts) > 1:
        arg = parts[1].lower()
    st = _qx_access(u.id)

    if arg in ("off", "stop", "sleep"):
        await _qx_stop_runner(u.id, reason="user requested")
        await update.effective_message.reply_text("⏸️ আপনার বট বন্ধ করা হলো।")
        raise ApplicationHandlerStop

    if arg in ("on", "start", "wake"):
        if not st["ok"]:
            await update.effective_message.reply_text(
                _qx_expired_card(u.id, u.full_name), parse_mode=ParseMode.HTML
            )
            raise ApplicationHandlerStop
        if not _qx_get_token(u.id):
            await update.effective_message.reply_text(
                "ℹ️ আগে token যুক্ত করুন: <code>/addbot &lt;token&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
            raise ApplicationHandlerStop
        ok, info = await _qx_start_runner(u.id, u.full_name)
        await update.effective_message.reply_text(
            f"⚡ চালু হয়েছে: @{h(info)}" if ok else f"⚠️ চালু করা গেল না: {h(str(info)[:200])}",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    username = ""
    runner = _QX_RUNNERS.get(int(u.id))
    if runner:
        username = runner.username
    await update.effective_message.reply_text(
        _qx_access_card(u.id, u.full_name, st, username), parse_mode=ParseMode.HTML
    )
    raise ApplicationHandlerStop


async def qx_cmd_removebot(update, context):
    u = update.effective_user
    await _qx_stop_runner(u.id, reason="user removed")
    _qx_delete_bot(u.id)
    await update.effective_message.reply_text("🗑️ আপনার বট ও token সরিয়ে ফেলা হয়েছে।")
    raise ApplicationHandlerStop


async def qx_main_gate(update, context):
    """Main bot: ordinary users get the control panel only — no AI features."""
    user = getattr(update, "effective_user", None)
    uid = int(getattr(user, "id", 0) or 0)
    if not uid or _qx_real_owner(uid) or is_admin(uid):
        return  # owner/admin keep the full legacy workflow here

    msg = getattr(update, "effective_message", None)
    text = str(getattr(msg, "text", "") or "")

    if text[:1] in ("/", "."):
        cmd = re.split(r"[\s@]", text[1:].strip(), 1)[0].lower()
        if cmd in QX_MAIN_ALLOWED_COMMANDS:
            return
        await _qx_route_notice(update)
        raise ApplicationHandlerStop

    token_match = _QX_TOKEN_RE.search(text)
    if token_match:
        with contextlib.suppress(Exception):
            await msg.delete()
        await _qx_register_token(update, uid, getattr(user, "full_name", ""), token_match.group(1))
        raise ApplicationHandlerStop

    await _qx_route_notice(update)
    raise ApplicationHandlerStop


async def _qx_route_notice(update):
    msg = getattr(update, "effective_message", None)
    if not msg:
        return
    runner = _QX_RUNNERS.get(int(update.effective_user.id))
    where = f"@{runner.username}" if runner and runner.username else "আপনার নিজের বট"
    with contextlib.suppress(Exception):
        await msg.reply_text(
            "ℹ️ <b>Qubix এখন শুধু control panel</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Quiz solve / AI reply / generation এখানে আর হয় না।\n"
            f"সব কাজ করুন <b>{h(where)}</b>-এ — quiz forward, ছবি বা টেক্সটে reply "
            "দিলেই আনলিমিটেড quiz generate হবে।\n\n"
            "শুরু করতে: <code>/addbot &lt;token&gt;</code> · status: <code>/mybot</code>",
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN bot — owner controls
# ─────────────────────────────────────────────────────────────────────────────
async def qx_cmd_approve(update, context):
    u = update.effective_user
    if not _qx_real_owner(u.id):
        raise ApplicationHandlerStop
    parts = str(update.effective_message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await update.effective_message.reply_text(
            "ℹ️ <code>/qapprove &lt;user_id&gt; [days]</code> — days না দিলে unlimited।",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop
    uid = int(parts[1])
    expires = None
    if len(parts) > 2:
        with contextlib.suppress(Exception):
            expires = time.time() + float(parts[2]) * 86400
    _qx_access_write(uid, "approved", expires)
    token = _QX_TRIAL_TOKENS.pop(uid, None)
    if token:
        _qx_save_bot(uid, token, "")   # promote memory-only token to storage
    await update.effective_message.reply_text(
        f"✅ Approved <code>{uid}</code> — {h(_qx_human_left(None if expires is None else expires - time.time()))}",
        parse_mode=ParseMode.HTML,
    )
    await _qx_notify(
        uid,
        "🎉 <b>Access Approved!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Validity: {h(_qx_human_left(None if expires is None else expires - time.time()))}\n"
        "আপনার সংরক্ষিত bot স্বয়ংক্রিয়ভাবে প্রস্তুত থাকবে।",
    )
    raise ApplicationHandlerStop


async def qx_cmd_revoke(update, context):
    u = update.effective_user
    if not _qx_real_owner(u.id):
        raise ApplicationHandlerStop
    parts = str(update.effective_message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await update.effective_message.reply_text("ℹ️ <code>/qrevoke &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop
    uid = int(parts[1])
    _qx_access_write(uid, "blocked", None)
    await _qx_stop_runner(uid, reason="owner revoked")
    _qx_delete_bot(uid)
    await update.effective_message.reply_text(f"🚫 Revoked <code>{uid}</code> (token removed).", parse_mode=ParseMode.HTML)
    await _qx_notify(uid, _qx_expired_card(uid))
    raise ApplicationHandlerStop


async def qx_cmd_trial(update, context):
    u = update.effective_user
    if not _qx_real_owner(u.id):
        raise ApplicationHandlerStop
    parts = str(update.effective_message.text or "").split()
    if len(parts) < 2:
        await update.effective_message.reply_text(
            f"⏳ বর্তমান trial: <b>{_qx_trial_seconds() // 60} মিনিট</b>\n"
            "পরিবর্তন: <code>/qtrial &lt;minutes&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop
    with contextlib.suppress(Exception):
        _qx_set_setting("trial_seconds", str(int(float(parts[1]) * 60)))
    await update.effective_message.reply_text(
        f"✅ Trial সময় সেট: <b>{_qx_trial_seconds() // 60} মিনিট / user</b>", parse_mode=ParseMode.HTML
    )
    raise ApplicationHandlerStop


async def qx_cmd_bots(update, context):
    u = update.effective_user
    if not _qx_real_owner(u.id):
        raise ApplicationHandlerStop
    rows = _qx_all_saved_bots()
    lines = ["🤖 <b>Qubix — Tenant Bots</b>", "━━━━━━━━━━━━━━━━━━━━━━"]
    if not rows and not _QX_TRIAL_TOKENS:
        lines.append("<i>কোনো বট নেই।</i>")
    for r in rows:
        uid = int(r["user_id"])
        st = _qx_access(uid)
        live = "🟢" if (uid in _QX_RUNNERS and _QX_RUNNERS[uid].running) else "⚪"
        lines.append(
            f"{live} <code>{uid}</code> · @{h(r['bot_username'] or '—')} · "
            f"{h(st['mode'])} · {h(_qx_human_left(st.get('remaining')))}"
        )
    for uid in list(_QX_TRIAL_TOKENS.keys()):
        st = _qx_access(uid)
        live = "🟢" if (uid in _QX_RUNNERS and _QX_RUNNERS[uid].running) else "⚪"
        lines.append(f"{live} <code>{uid}</code> · 🧪 trial (memory-only) · {h(_qx_human_left(st.get('remaining')))}")
    lines += ["━━━━━━━━━━━━━━━━━━━━━━",
              "<code>/qapprove &lt;id&gt; [days]</code> · <code>/qrevoke &lt;id&gt;</code> · "
              "<code>/qkill &lt;id&gt;</code> · <code>/qtrial &lt;min&gt;</code>"]
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    raise ApplicationHandlerStop


async def qx_cmd_kill(update, context):
    u = update.effective_user
    if not _qx_real_owner(u.id):
        raise ApplicationHandlerStop
    parts = str(update.effective_message.text or "").split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await update.effective_message.reply_text("ℹ️ <code>/qkill &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop
    uid = int(parts[1])
    await _qx_stop_runner(uid, reason="owner stop")
    await update.effective_message.reply_text(f"⏹️ Stopped <code>{uid}</code>.", parse_mode=ParseMode.HTML)
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# Wiring
# ─────────────────────────────────────────────────────────────────────────────
_QX_MAIN_ONLY: List[Any] = []      # strong refs; PTB handlers use __slots__


def _qx_mark(handler):
    """Handlers marked main-only are never cloned onto tenant bots."""
    _QX_MAIN_ONLY.append(handler)
    return handler


def _qx_is_main_only(handler) -> bool:
    return any(handler is x for x in _QX_MAIN_ONLY)


_qx_prev_build_app_90 = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx_prev_build_app_90() if callable(_qx_prev_build_app_90) else None
    if app is None:
        return app

    _cmd = globals().get("_cmdh")

    def cmdh(name, cb):
        try:
            return _cmd(name, cb) if callable(_cmd) else CommandHandler(name, cb)
        except Exception:
            return CommandHandler(name, cb)

    # Owner controls (main bot only).
    for name, cb in (
        ("qapprove", qx_cmd_approve),
        ("qrevoke", qx_cmd_revoke),
        ("qtrial", qx_cmd_trial),
        ("qbots", qx_cmd_bots),
        ("qkill", qx_cmd_kill),
    ):
        with contextlib.suppress(Exception):
            app.add_handler(_qx_mark(cmdh(name, cb)), group=-950)

    # User control panel (main bot only).
    for name, cb in (
        ("start", qx_cmd_start),
        ("addbot", qx_cmd_addbot),
        ("mybot", qx_cmd_mybot),
        ("wake", qx_cmd_mybot),
        ("removebot", qx_cmd_removebot),
        ("delbot", qx_cmd_removebot),
        ("myid", qx_cmd_myid),
    ):
        with contextlib.suppress(Exception):
            app.add_handler(_qx_mark(cmdh(name, cb)), group=-940)

    # Feature removal gate for ordinary users on the main bot.
    with contextlib.suppress(Exception):
        app.add_handler(_qx_mark(MessageHandler(filters.ALL, qx_main_gate)), group=-930)

    globals()["_QX_MAIN_APP"] = app

    _prev_post_init = getattr(app, "post_init", None)

    async def _qx_post_init(application):
        if _prev_post_init and callable(_prev_post_init):
            with contextlib.suppress(Exception):
                await _prev_post_init(application)
        with contextlib.suppress(Exception):
            asyncio.create_task(_qx_watchdog())
            _qx_log.info("[QUBIX] multi-tenant watchdog started.")
        # Restore approved personal bots after a service restart.  Their polling
        # listeners remain silent while idle, so users never need /mybot on.
        for row in _qx_all_saved_bots():
            uid = int(row["user_id"])
            if not _qx_access(uid).get("ok"):
                continue
            with contextlib.suppress(Exception):
                asyncio.create_task(_qx_start_runner(uid))

    app.post_init = _qx_post_init

    _qx_log.info("[QUBIX] multi-tenant control panel wired on the main bot.")
    return app


_qx_log.info(
    "[SECTION 90 · 2026-08-03] Qubix multi-tenant user-bot runtime loaded — "
    "main bot = control panel, tenants run their own bots with full quiz workflow."
)
# ===== END SECTION 90 =====
