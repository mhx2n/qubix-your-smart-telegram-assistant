# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 96 — QUBIX OWNER-LEAK SHIELD (2026-08-03)
#
# Problem this fixes for real:
#   Some legacy handler paths (e.g. `/post`, `/buffer`, staff guards, owner
#   panel callbacks) could still deliver OWNER-only text into a normal user's
#   inbox — on the main Qubix bot and inside token-added personal bots.
#
# Fix strategy = single outbound choke point:
#   Every Telegram write (send_message / edit_message_text) is inspected.
#   If the text carries owner/staff infrastructure markers and the receiving
#   chat is NOT the real owner on the main bot, the payload is replaced with
#   the user's own workspace card (owner inline keyboards are stripped too).
#   Nothing owner-shaped can reach a user, no matter which section produced it.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx96

import telegram as _tg96


# ─────────────────────────────────────────────────────────────────────────────
# 0) HARD owner check — immune to the acting-owner contextvar
#
# Root cause of the leak: section 90 patches `_is_owner_id`, and the legacy
# `is_owner()` calls that patched helper, so once `_QX_ACTING_OWNER` was set for
# a tenant/user, every downstream owner check (including `_qx_real_owner`)
# answered True → the Owner Control Panel rendered inside a user's inbox.
# From here on, "real owner" means: id literally configured in OWNER_IDS.
# ─────────────────────────────────────────────────────────────────────────────
def _qx96_hard_owner(uid) -> bool:
    try:
        uid = int(uid or 0)
    except Exception:
        return False
    if not uid:
        return False
    try:
        ids = set(int(x) for x in (globals().get("OWNER_IDS_SET") or globals().get("OWNER_IDS") or ()))
    except Exception:
        ids = set()
    return uid in ids


def _qx_real_owner(uid) -> bool:  # noqa: F811
    return _qx96_hard_owner(uid)


globals()["_qx_real_owner"] = _qx_real_owner
globals()["_qx96_hard_owner"] = _qx96_hard_owner


# ─────────────────────────────────────────────────────────────────────────────
# 1) Owner = real owner only (legacy staff/admin rows never unlock the panel)
# ─────────────────────────────────────────────────────────────────────────────
def _qx93_privileged(update) -> bool:  # noqa: F811
    uid = 0
    with _cx96.suppress(Exception):
        uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not uid:
        return False
    return bool(_qx_real_owner(uid))


globals()["_qx93_privileged"] = _qx93_privileged
globals()["_qx92_privileged"] = _qx93_privileged


# ─────────────────────────────────────────────────────────────────────────────
# 2) Owner-only markers
# ─────────────────────────────────────────────────────────────────────────────
_QX96_OWNER_MARKERS = (
    "owner control panel",
    "owner commands",
    "owner panel",
    "tenant bots",
    "/qapprove",
    "/qrevoke",
    "/qtrial",
    "/qbots",
    "/qkill",
    "/adminpanel",
    "/broadcast",
    "/dashboard",
    "/banned",
    "/logs",
    "staff & system",
    "staff &amp; system",
    "access management",
    "trial setting",
    "access দেওয়ার নিয়ম",
    "restricted for staff",
    "staff operation",
    "unauthorized",
    "owner only",
    "owner infrastructure",
    "mongobackup",
    "gemini key",
    "/addkey",
    "/delkey",
)


def _qx96_has_owner_marker(text: str) -> bool:
    low = str(text or "").lower()
    return any(marker in low for marker in _QX96_OWNER_MARKERS)


def _qx96_is_main_bot(token) -> bool:
    main = str(globals().get("BOT_TOKEN") or "")
    token = str(token or "")
    return bool(main) and token == main


def _qx96_owner_chat(token, chat_id) -> bool:
    """True only for the real owner talking to the main Qubix bot."""
    if not _qx96_is_main_bot(token):
        return False
    try:
        cid = int(chat_id)
    except Exception:
        return False
    if cid <= 0:                      # groups/channels never get owner cards
        return False
    return bool(_qx_real_owner(cid))


# ─────────────────────────────────────────────────────────────────────────────
# 3) Replacement payload for a user
# ─────────────────────────────────────────────────────────────────────────────
def _qx96_user_card(chat_id) -> str:
    uid = 0
    with _cx96.suppress(Exception):
        uid = int(chat_id)
    st = {}
    with _cx96.suppress(Exception):
        st = _qx_access(uid) or {}
    if not st.get("ok"):
        with _cx96.suppress(Exception):
            return _qx_expired_card(uid, "")
    left = "—"
    with _cx96.suppress(Exception):
        left = _qx_human_left(st.get("remaining"))
    return (
        "🧠 <b>Qubix — আপনার Workspace</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 User ID: <code>{uid}</code>\n"
        f"⏳ Time left: <code>{left}</code>\n\n"
        "এই command আপনার workspace-এর অংশ নয়। আপনি যা করতে পারবেন:\n\n"
        "🧠 <b>Quiz তৈরি</b> — poll / ছবি / text-এ reply করে\n"
        "<code>.gen 15</code> · <code>.gen medical 15</code> · "
        "<code>.gen engineering 15</code> · <code>.gen versity 15</code>\n\n"
        "📦 <b>Buffer</b> — <code>/buffercount</code> · <code>/buffer</code> · "
        "<code>.clear</code>\n"
        "📤 <b>Export</b> — <code>.done</code> (CSV + JSON)\n"
        "📣 <b>Channel</b> — <code>/addchannel @channel</code> · "
        "<code>/listchannels</code> · <code>.post &lt;channel#&gt;</code>\n"
        "🧵 <b>Group/Topic</b> — <code>.adg &lt;group_id&gt;</code> · "
        "<code>.info</code> · <code>.adtc</code> · <code>.pt &lt;group#&gt; &lt;topic#&gt;</code>\n"
        "📌 <b>Topic card</b> — <code>.topic</code> · <code>.aitopic</code> · "
        "<code>.topicpin</code> · <code>.topicunpin</code>\n"
        "🤖 <b>নিজের bot</b> — <code>/addbot &lt;token&gt;</code> · "
        "<code>/mybot on|off</code> · <code>/removebot</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📜 সব command: <code>/commands</code> · সাহায্য: <code>.help</code>"
    )


def _qx96_clean_markup(markup, owner_chat: bool):
    """Strip owner-panel buttons for users; keep user keyboards untouched."""
    if owner_chat or markup is None:
        return markup
    rows = getattr(markup, "inline_keyboard", None)
    if not rows:
        return markup
    kept = []
    for row in rows:
        keep_row = [
            btn for btn in row
            if not str(getattr(btn, "callback_data", "") or "").startswith(("qx94:", "qx:owner"))
        ]
        if keep_row:
            kept.append(keep_row)
    if not kept:
        with _cx96.suppress(Exception):
            return _qx93_menu_kb()
        return None
    with _cx96.suppress(Exception):
        return _tg96.InlineKeyboardMarkup(kept)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4) Outbound choke point on the Bot API
# ─────────────────────────────────────────────────────────────────────────────
def _qx96_pick(args, kwargs, index, name):
    if name in kwargs:
        return kwargs[name], "kw", None
    if isinstance(index, int) and index >= 0 and len(args) > index:
        return args[index], "pos", index
    return None, None, None


def _qx96_shield(args, kwargs, token, chat_id):
    """Return (args, kwargs) with owner text/markup replaced when needed."""
    text, where, idx = _qx96_pick(args, kwargs, 1, "text")
    if not isinstance(text, str) or not _qx96_has_owner_marker(text):
        return args, kwargs
    if _qx96_owner_chat(token, chat_id):
        return args, kwargs

    replacement = _qx96_user_card(chat_id)
    if where == "kw":
        kwargs["text"] = replacement
    elif where == "pos":
        args = list(args)
        args[idx] = replacement
        args = tuple(args)

    markup, m_where, m_idx = _qx96_pick(args, kwargs, None, "reply_markup")
    new_markup = _qx96_clean_markup(markup, False)
    if m_where == "kw":
        kwargs["reply_markup"] = new_markup
    elif new_markup is not markup:
        kwargs["reply_markup"] = new_markup

    kwargs["parse_mode"] = _tg96.constants.ParseMode.HTML
    return args, kwargs


_qx96_orig_send = _tg96.Bot.send_message
_qx96_orig_edit = _tg96.Bot.edit_message_text


async def _qx96_send_message(self, *args, **kwargs):
    with _cx96.suppress(Exception):
        chat_id, _, _ = _qx96_pick(args, kwargs, 0, "chat_id")
        args, kwargs = _qx96_shield(args, kwargs, getattr(self, "token", ""), chat_id)
    return await _qx96_orig_send(self, *args, **kwargs)


async def _qx96_edit_message_text(self, *args, **kwargs):
    with _cx96.suppress(Exception):
        chat_id = kwargs.get("chat_id")
        if chat_id is None and args:
            # edit_message_text(text, chat_id=..., ...) in PTB v20+
            chat_id = kwargs.get("chat_id")
        text, where, idx = _qx96_pick(args, kwargs, 0, "text")
        if isinstance(text, str) and _qx96_has_owner_marker(text) and not _qx96_owner_chat(
            getattr(self, "token", ""), chat_id
        ):
            replacement = _qx96_user_card(chat_id or 0)
            if where == "kw":
                kwargs["text"] = replacement
            elif where == "pos":
                args = list(args)
                args[idx] = replacement
                args = tuple(args)
            kwargs["reply_markup"] = _qx96_clean_markup(kwargs.get("reply_markup"), False)
            kwargs["parse_mode"] = _tg96.constants.ParseMode.HTML
    return await _qx96_orig_edit(self, *args, **kwargs)


if not getattr(_tg96.Bot.send_message, "_qx96", False):
    _qx96_send_message._qx96 = True  # type: ignore[attr-defined]
    _qx96_edit_message_text._qx96 = True  # type: ignore[attr-defined]
    _tg96.Bot.send_message = _qx96_send_message
    _tg96.Bot.edit_message_text = _qx96_edit_message_text


# ─────────────────────────────────────────────────────────────────────────────
# 5) Owner panel handlers double-checked (defence in depth)
# ─────────────────────────────────────────────────────────────────────────────
_qx96_prev_owner_callback = globals().get("qx94_on_callback")


async def qx94_on_callback(update, context):  # noqa: F811
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    if not _qx93_privileged(update) or _qx95_is_tenant(context):
        with _cx96.suppress(Exception):
            await query.answer()
        uid = _qx95_scope_uid(update, context)
        with _cx96.suppress(Exception):
            await query.edit_message_text(
                await _qx94_user_menu_text(update, context, uid, _qx_access(uid)),
                parse_mode=_tg96.constants.ParseMode.HTML,
                reply_markup=_qx93_menu_kb(),
                disable_web_page_preview=True,
            )
        raise ApplicationHandlerStop
    if callable(_qx96_prev_owner_callback):
        return await _qx96_prev_owner_callback(update, context)


globals()["qx94_on_callback"] = qx94_on_callback


# ─────────────────────────────────────────────────────────────────────────────
# 6) Wiring — the shield callback must run before section 94's owner callback
# ─────────────────────────────────────────────────────────────────────────────
_qx96_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx96_prev_build_app() if callable(_qx96_prev_build_app) else None
    if app is None:
        return app
    with _cx96.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx94_on_callback, pattern=r"^qx94:"), group=-1040
        )
    _qx_log.info("[QUBIX-96] owner-leak shield wired (outbound firewall + owner callback guard).")
    return app


_qx_log.info("[SECTION 96] Qubix owner-leak shield loaded (outbound owner-text firewall).")
