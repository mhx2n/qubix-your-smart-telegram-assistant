# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 116 — LIVE SCORE TOGGLE + DAY-AWARE ACCESS GRANTS (2026-08-05)
#
# Fixes:
#   1) Score Reply on/off did not persist and the card never updated live.
#      Root cause: `_set_score_reply` used a bare UPDATE, so a user without a
#      row in `users` silently stayed at the default (ON) — the rebuilt card was
#      byte-identical and Telegram rejected the edit as "message is not
#      modified" (suppressed), so nothing appeared to happen.
#   2) Owner grants had no single place to set plan + duration:
#        /qapprove <id> [days|unlimited] [student|master]
#        /qtier    <id> student|master|reset [days|unlimited]
#        /qinfo    <id>            → plan + validity at a glance
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx116
import time as _t116
import datetime as _dt116


# ─────────────────────────────────────────────────────────────────────────────
# 1) Durable score-reply persistence
# ─────────────────────────────────────────────────────────────────────────────
def _qx116_ensure_user_row(uid: int) -> None:
    for name in ("ensure_user", "_ensure_user", "ensure_user_row", "upsert_user"):
        fn = globals().get(name)
        if callable(fn):
            with _cx116.suppress(Exception):
                fn(int(uid))
                return
    with _cx116.suppress(Exception):
        conn = db_connect()
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (int(uid),))
        conn.commit()
        conn.close()


def _set_score_reply(admin_id: int, val: bool) -> None:  # noqa: F811
    """Upsert-based toggle — works even when the user has no `users` row yet."""
    uid = int(admin_id or 0)
    if not uid:
        return
    _qx116_ensure_user_row(uid)
    with _cx116.suppress(Exception):
        conn = db_connect()
        conn.execute(
            "INSERT INTO users(user_id, score_reply_on) VALUES(?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET score_reply_on=excluded.score_reply_on",
            (uid, 1 if val else 0),
        )
        conn.commit()
        conn.close()
        return
    with _cx116.suppress(Exception):
        conn = db_connect()
        conn.execute(
            "UPDATE users SET score_reply_on=? WHERE user_id=?",
            (1 if val else 0, uid),
        )
        conn.commit()
        conn.close()


globals()["_set_score_reply"] = _set_score_reply


def _qx116_score_state(uid: int) -> bool:
    getter = globals().get("_score_reply_enabled")
    if callable(getter):
        with _cx116.suppress(Exception):
            return bool(getter(int(uid)))
    return True


def _qx116_score_card(active: bool) -> str:
    badge = "🟢 চালু" if active else "🔴 বন্ধ"
    detail = (
        "প্রতিটি প্রকাশ শেষে প্রথম quiz-কে reply করে score কার্ড পাঠানো হবে।"
        if active else
        "প্রকাশ শেষে আর কোনো score কার্ড পাঠানো হবে না — শুধু quiz-গুলোই যাবে।"
    )
    stamp = _dt116.datetime.now().strftime("%H:%M:%S")
    return (
        "🏆 <b>Score Reply</b>\n"
        "<code>─────────────────────────</code>\n"
        f"অবস্থা: <b>{badge}</b>\n\n"
        f"{detail}\n\n"
        f"<i>সর্বশেষ আপডেট: {stamp}</i>"
    )


def _qx116_score_kb(active: bool):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                ("✅ চালু আছে" if active else "🟢 চালু করুন"),
                callback_data="qx101:score:on",
            ),
            InlineKeyboardButton(
                ("✅ বন্ধ আছে" if not active else "🔴 বন্ধ করুন"),
                callback_data="qx101:score:off",
            ),
        ],
        [
            InlineKeyboardButton("🔄 রিফ্রেশ", callback_data="qx101:score:rf"),
            InlineKeyboardButton("✖️ বন্ধ", callback_data="qx101:score:cl"),
        ],
    ])


async def qx116_cb_score(update, context):
    """Authoritative Score Reply toggle — always persists and always re-renders."""
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    uid = 0
    with _cx116.suppress(Exception):
        uid = int(query.from_user.id)
    if not uid:
        return

    action = str(getattr(query, "data", "") or "").split(":")[-1]
    if action == "cl":
        with _cx116.suppress(Exception):
            await query.answer("বন্ধ করা হলো")
        with _cx116.suppress(Exception):
            await query.message.delete()
        raise ApplicationHandlerStop

    if action == "on":
        _set_score_reply(uid, True)
        note = "Score reply চালু হয়েছে"
    elif action == "off":
        _set_score_reply(uid, False)
        note = "Score reply বন্ধ হয়েছে"
    else:
        note = "রিফ্রেশ হলো"

    active = _qx116_score_state(uid)
    with _cx116.suppress(Exception):
        await query.answer(note)

    body = _qx116_score_card(active)
    kb = _qx116_score_kb(active)
    try:
        await query.edit_message_text(
            body, parse_mode=ParseMode.HTML,
            reply_markup=kb, disable_web_page_preview=True,
        )
    except Exception:
        with _cx116.suppress(Exception):
            await query.edit_message_reply_markup(reply_markup=kb)
        with _cx116.suppress(Exception):
            await query.message.reply_text(
                body, parse_mode=ParseMode.HTML,
                reply_markup=kb, disable_web_page_preview=True,
            )
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 2) Day-aware access grants
# ─────────────────────────────────────────────────────────────────────────────
_QX116_UNLIMITED = ("unlimited", "unlimited", "lifetime", "forever", "inf", "∞", "0")
_QX116_TIERS = ("student", "master", "reset")


def _qx116_parse_grant(text: str):
    """Return (uid, days|None, tier|'') from a free-form owner command."""
    parts = str(text or "").split()[1:]
    uid = 0
    days = None
    tier = ""
    unlimited = False
    for raw in parts:
        token = raw.strip().lower()
        if not token:
            continue
        if token in _QX116_TIERS:
            tier = token
            continue
        if token in _QX116_UNLIMITED and token != "0":
            unlimited = True
            continue
        candidate = token.lstrip("-")
        if candidate.replace(".", "", 1).isdigit():
            if not uid and candidate.isdigit() and len(candidate) >= 5:
                uid = int(token)
            elif days is None:
                value = float(candidate)
                if value <= 0:
                    unlimited = True
                else:
                    days = value
            continue
    if unlimited:
        days = None
    return uid, days, tier


def _qx116_validity_line(state) -> str:
    st = state or {}
    if not st.get("ok"):
        return "⛔ মেয়াদ শেষ / অনুমোদন নেই"
    expires = st.get("expires_at")
    if not expires:
        return "♾️ Unlimited access"
    left = float(expires) - _t116.time()
    human = ""
    with _cx116.suppress(Exception):
        human = str(_qx_human_left(left))
    when = ""
    with _cx116.suppress(Exception):
        when = _dt116.datetime.fromtimestamp(float(expires)).strftime("%d %b %Y, %I:%M %p")
    return f"⏳ {human or 'সীমিত'} বাকি" + (f" · শেষ হবে: {when}" if when else "")


def _qx116_tier_label(tier: str) -> str:
    if tier == "student":
        return "🎓 Student Access"
    if tier == "master":
        return "👑 Master Access"
    return "🕒 Trial (user নিজে বেছে নেবে)"


def _qx116_state(uid: int):
    with _cx116.suppress(Exception):
        return _qx_access(int(uid)) or {}
    return {}


def _qx116_current_tier(uid: int) -> str:
    with _cx116.suppress(Exception):
        return str(_qx112_stored_tier(int(uid)) or "")
    return ""


async def qx116_cmd_qapprove(update, context):
    user = getattr(update, "effective_user", None)
    if not _qx_real_owner(getattr(user, "id", 0)):
        raise ApplicationHandlerStop
    message = update.effective_message
    text = str(getattr(message, "text", "") or "")
    uid, days, tier = _qx116_parse_grant(text)
    if not uid:
        await message.reply_text(
            "ℹ️ <b>Access দিন</b>\n"
            "<code>/qapprove &lt;user_id&gt;</code> — unlimited\n"
            "<code>/qapprove &lt;user_id&gt; 75</code> — ৭৫ দিন\n"
            "<code>/qapprove &lt;user_id&gt; 75 student</code> — ৭৫ দিন Student plan\n"
            "<code>/qapprove &lt;user_id&gt; 30 master</code> — ৩০ দিন Master plan",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    expires = None if days is None else _t116.time() + float(days) * 86400.0
    with _cx116.suppress(Exception):
        _qx_access_write(uid, "approved", expires)
    if tier:
        with _cx116.suppress(Exception):
            _qx112_set_tier(uid, "" if tier == "reset" else tier)

    with _cx116.suppress(Exception):
        token = (globals().get("_QX_TRIAL_TOKENS") or {}).pop(uid, None)
        if token:
            _qx_save_bot(uid, token, "")

    plan = _qx116_current_tier(uid)
    await message.reply_text(
        "✅ <b>Access অনুমোদিত</b>\n"
        "<code>─────────────────────────</code>\n"
        f"User ID: <code>{uid}</code>\n"
        f"Plan: <b>{h(_qx116_tier_label(plan))}</b>\n"
        f"Validity: <b>{h(_qx116_validity_line(_qx116_state(uid)))}</b>",
        parse_mode=ParseMode.HTML,
    )
    notify = globals().get("_qx_notify")
    if callable(notify):
        with _cx116.suppress(Exception):
            await notify(
                uid,
                "🎉 <b>Access অনুমোদিত হয়েছে</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Plan: {h(_qx116_tier_label(plan))}\n"
                f"Validity: {h(_qx116_validity_line(_qx116_state(uid)))}\n\n"
                "শুরু করতে <code>/start</code> দিন।",
            )
    raise ApplicationHandlerStop


async def qx116_cmd_qtier(update, context):
    user = getattr(update, "effective_user", None)
    if not _qx_real_owner(getattr(user, "id", 0)):
        raise ApplicationHandlerStop
    message = update.effective_message
    uid, days, tier = _qx116_parse_grant(str(getattr(message, "text", "") or ""))
    if not uid or not tier:
        await message.reply_text(
            "ℹ️ <b>Plan সেট করুন</b>\n"
            "<code>/qtier &lt;user_id&gt; student</code>\n"
            "<code>/qtier &lt;user_id&gt; master 30</code> — ৩০ দিনের Master\n"
            "<code>/qtier &lt;user_id&gt; master unlimited</code>\n"
            "<code>/qtier &lt;user_id&gt; reset</code> — user আবার নিজে বেছে নেবে",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    with _cx116.suppress(Exception):
        _qx112_set_tier(uid, "" if tier == "reset" else tier)

    has_days_token = any(
        tok.strip().lower() in _QX116_UNLIMITED or tok.strip().lstrip("-").replace(".", "", 1).isdigit()
        for tok in str(getattr(message, "text", "") or "").split()[2:]
    )
    if tier != "reset" and has_days_token:
        expires = None if days is None else _t116.time() + float(days) * 86400.0
        with _cx116.suppress(Exception):
            _qx_access_write(uid, "approved", expires)

    plan = _qx116_current_tier(uid)
    await message.reply_text(
        "✅ <b>Plan আপডেট হয়েছে</b>\n"
        "<code>─────────────────────────</code>\n"
        f"User ID: <code>{uid}</code>\n"
        f"Plan: <b>{h(_qx116_tier_label(plan))}</b>\n"
        f"Validity: <b>{h(_qx116_validity_line(_qx116_state(uid)))}</b>",
        parse_mode=ParseMode.HTML,
    )
    notify = globals().get("_qx_notify")
    if callable(notify) and tier != "reset":
        with _cx116.suppress(Exception):
            await notify(
                uid,
                f"{h(_qx116_tier_label(tier))} চালু হয়েছে!\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Validity: {h(_qx116_validity_line(_qx116_state(uid)))}\n\n"
                "নতুন workspace খুলতে এখনই <code>/start</code> দিন।",
            )
    raise ApplicationHandlerStop


async def qx116_cmd_qinfo(update, context):
    user = getattr(update, "effective_user", None)
    if not _qx_real_owner(getattr(user, "id", 0)):
        raise ApplicationHandlerStop
    message = update.effective_message
    uid, _days, _tier = _qx116_parse_grant(str(getattr(message, "text", "") or ""))
    if not uid:
        await message.reply_text(
            "ℹ️ <code>/qinfo &lt;user_id&gt;</code> — plan ও মেয়াদ দেখুন।",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop
    st = _qx116_state(uid)
    await message.reply_text(
        "🪪 <b>Access Report</b>\n"
        "<code>─────────────────────────</code>\n"
        f"User ID: <code>{uid}</code>\n"
        f"Mode: <b>{h(str(st.get('mode') or 'none'))}</b>\n"
        f"Plan: <b>{h(_qx116_tier_label(_qx116_current_tier(uid)))}</b>\n"
        f"Validity: <b>{h(_qx116_validity_line(st))}</b>",
        parse_mode=ParseMode.HTML,
    )
    raise ApplicationHandlerStop


# ─────────────────────────────────────────────────────────────────────────────
# 3) Wiring — earlier than every legacy handler, later than the access gate
# ─────────────────────────────────────────────────────────────────────────────
_qx116_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx116_prev_build_app() if callable(_qx116_prev_build_app) else None
    if app is None:
        return app

    with _cx116.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx116_cb_score, pattern=r"^qx101:score:"),
            group=-35000,
        )

    register = globals().get("_register_dual_command")
    for command, callback in (
        ("qapprove", qx116_cmd_qapprove),
        ("qtier", qx116_cmd_qtier),
        ("qinfo", qx116_cmd_qinfo),
    ):
        with _cx116.suppress(Exception):
            if callable(register):
                register(app, command, callback, group=-35000)
            else:
                app.add_handler(CommandHandler(command, callback), group=-35000)

    with _cx116.suppress(Exception):
        _qx_log.info("[QUBIX-116] live score toggle + day-aware access grants wired.")
    return app


with _cx116.suppress(Exception):
    _qx_log.info("[SECTION 116] score live update + access days loaded.")
