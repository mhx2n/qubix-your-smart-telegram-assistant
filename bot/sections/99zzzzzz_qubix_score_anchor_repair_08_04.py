# ──────────────────────────────────────────────────────────────────────────────
# Section 104 (2026-08-04) — score card + topic anchor repair.
#
#   1. Score cards were being eaten by the section-103 transport deduplicator
#      (any text containing "score .../N" inside a 10 minute window). The filter
#      is retired here; only byte-identical duplicates within 20s are dropped.
#   2. Topic anchor tail is rebuilt on a reliable source: the actual replied-to
#      message that Telegram returns with every published quiz. Formatting is
#      preserved through PTB's *_html_urled renderers, so nothing breaks.
#   3. AI-written topic cards are never edited any more (left exactly as-is).
#      Only manual topics (plain text, or photo + caption) receive the tail.
#   4. Every new batch on the same topic refreshes the tail (old tail stripped
#      via the invisible marker, new AI line appended).
#
# DO NOT import directly — exec'd in the shared namespace by bot/__main__.py.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a104
import contextlib as _cx104
import hashlib as _hs104
import html as _h104
import time as _t104

import telegram as _tg104


def _log104(message: str, level: str = "info") -> None:
    with _cx104.suppress(Exception):
        getattr(logger, level)("[S104] %s", message)  # type: ignore[name-defined]


def _esc104(value) -> str:
    return _h104.escape(str(value or ""), quote=False)


_QX104_MARK = globals().get("_QX103_MARK", globals().get("_QX102_MARK", "\u2063"))


# ─────────────────────────────────────────────────────────────────────────────
# 1) Retire the score-card suppressor
# ─────────────────────────────────────────────────────────────────────────────
def _qx104_score_dup(_kwargs) -> bool:
    return False


globals()["_qx103_score_dup"] = _qx104_score_dup
with _cx104.suppress(Exception):
    _QX103_SCORE_SEEN.clear()  # type: ignore[name-defined]

_QX104_EXACT: dict = {}
_QX104_EXACT_WINDOW = 20.0


def _qx104_exact_dup(chat_id, text) -> bool:
    """Drop only byte-identical text to the same chat inside a short window."""
    body = str(text or "")
    if not body:
        return False
    now = _t104.time()
    key = (str(chat_id), _hs104.sha1(body.encode("utf-8", "ignore")).hexdigest())
    previous = _QX104_EXACT.get(key)
    _QX104_EXACT[key] = now
    if len(_QX104_EXACT) > 500:
        for stale in [k for k, v in _QX104_EXACT.items() if now - v > _QX104_EXACT_WINDOW]:
            _QX104_EXACT.pop(stale, None)
    return bool(previous and now - previous < _QX104_EXACT_WINDOW)


_qx104_prev_send_message = _tg104.Bot.send_message


async def _qx104_send_message(self, *args, **kwargs):
    merged = dict(kwargs)
    if args:
        for index, name in enumerate(("chat_id", "text")):
            if index < len(args):
                merged.setdefault(name, args[index])
    if _qx104_exact_dup(merged.get("chat_id"), merged.get("text")):
        _log104("identical message suppressed (20s window)")
        return None
    return await _qx104_prev_send_message(self, *args, **kwargs)


if not getattr(_tg104.Bot.send_message, "_qx104", False):
    _qx104_send_message._qx104 = True  # type: ignore[attr-defined]
    _tg104.Bot.send_message = _qx104_send_message


# ─────────────────────────────────────────────────────────────────────────────
# 2) Anchor snapshot straight from the replied-to message
# ─────────────────────────────────────────────────────────────────────────────
def _qx104_anchor_snapshot(bot, message) -> dict:
    """Read the live anchor body from the reply target of a published quiz."""
    anchor = getattr(message, "reply_to_message", None)
    if anchor is None:
        return {}
    sender = getattr(anchor, "from_user", None)
    sender_id = int(getattr(sender, "id", 0) or 0)
    bot_id = int(getattr(bot, "id", 0) or 0)
    if not bot_id:
        with _cx104.suppress(Exception):
            bot_id = int(str(getattr(bot, "token", "")).split(":")[0])
    if sender_id and bot_id and sender_id != bot_id:
        return {}  # foreign message — Telegram forbids editing it
    photo = bool(getattr(anchor, "photo", None))
    body = ""
    with _cx104.suppress(Exception):
        body = str(getattr(anchor, "caption_html_urled", "") or "") if photo \
            else str(getattr(anchor, "text_html_urled", "") or "")
    if not body:
        body = str(getattr(anchor, "caption", "") or getattr(anchor, "text", "") or "")
        body = _esc104(body)
    if not body.strip():
        return {}
    return {"html": body, "photo": photo}


def _qx104_is_ai_anchor(anchor_chat, anchor_msg) -> bool:
    """AI topic cards go out through the rich (markdown) transport — never edit."""
    getter = globals().get("_qx103_cache_get")
    if callable(getter):
        with _cx104.suppress(Exception):
            if bool((getter(anchor_chat, anchor_msg) or {}).get("markdown")):
                return True
    row = globals().get("_qx102_anchor_row")
    if callable(row):
        with _cx104.suppress(Exception):
            _uid, stored, _photo = row(anchor_chat, anchor_msg)
            stored = str(stored or "")
            if stored.strip() and ("**" in stored or stored.lstrip().startswith("#")):
                return True
    return False


async def _qx104_tail_html(link: str, count: int) -> str:
    pair = globals().get("_qx103_tail_pair")
    if callable(pair):
        with _cx104.suppress(Exception):
            _md, html = await pair(link, count)
            if str(html or "").strip():
                return str(html)
    maker = globals().get("_qx102_tail")
    if callable(maker):
        with _cx104.suppress(Exception):
            return str(await maker(link, count))
    return (
        f"\n\n<b>✦ কুইজ শুরু হয়ে গেছে</b>\n"
        f"➤ <a href=\"{_esc104(link)}\">প্রথম কুইজে যান 🔗</a>"
    )


async def _qx104_apply(bot, anchor_chat, anchor_msg, link, count, snapshot) -> None:
    if not link or not snapshot:
        return
    if _qx104_is_ai_anchor(anchor_chat, anchor_msg):
        _log104(f"anchor {anchor_chat}/{anchor_msg} is an AI topic card — left untouched")
        return
    base = str(snapshot.get("html") or "").split(_QX104_MARK)[0].rstrip()
    if not base.strip():
        return
    photo = bool(snapshot.get("photo"))
    tail = await _qx104_tail_html(link, count)
    limit = 950 if photo else 3800
    if len(base) + len(tail) > limit:
        base = base[: max(0, limit - len(tail) - 1)].rstrip()
    body = base + _QX104_MARK + tail
    try:
        if photo:
            await bot.edit_message_caption(
                chat_id=anchor_chat, message_id=anchor_msg,
                caption=body, parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
            )
        else:
            await bot.edit_message_text(
                chat_id=anchor_chat, message_id=anchor_msg, text=body,
                parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                disable_web_page_preview=True,
            )
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return
        _log104(f"anchor {anchor_chat}/{anchor_msg} edit failed: {exc}", "warning")
        return
    putter = globals().get("_qx103_cache_put")
    if callable(putter):
        with _cx104.suppress(Exception):
            putter(anchor_chat, anchor_msg, body, photo=photo, markdown=False)
    _log104(f"anchor {anchor_chat}/{anchor_msg} refreshed with the first-quiz link")


# ─────────────────────────────────────────────────────────────────────────────
# 3) Own batch tracker (replaces the section-102 one)
# ─────────────────────────────────────────────────────────────────────────────
_QX104_SESSIONS: dict = {}
_QX104_SETTLE = 6.0


async def _qx104_settle(key) -> None:
    while True:
        await _a104.sleep(1.5)
        session = _QX104_SESSIONS.get(key)
        if not session:
            return
        if _t104.time() - float(session.get("ts") or 0) < _QX104_SETTLE:
            continue
        _QX104_SESSIONS.pop(key, None)
        try:
            await _qx104_apply(
                session.get("bot"), session.get("anchor_chat"), session.get("anchor_msg"),
                str(session.get("link") or ""), int(session.get("count") or 0),
                session.get("snapshot") or {},
            )
        except Exception as exc:
            reporter = globals().get("qx102_report")
            if callable(reporter):
                with _cx104.suppress(Exception):
                    await reporter(exc, source="topic first-quiz link",
                                   bot_label="Qubix runtime")
        return


def _qx104_track(bot, kwargs: dict, message) -> None:
    anchor_msg = kwargs.get("reply_to_message_id")
    anchor_chat = kwargs.get("chat_id")
    params = kwargs.get("reply_parameters")
    if params is not None:
        anchor_msg = getattr(params, "message_id", None) or anchor_msg
        anchor_chat = getattr(params, "chat_id", None) or anchor_chat
    reply = getattr(message, "reply_to_message", None)
    if reply is not None:
        anchor_msg = anchor_msg or getattr(reply, "message_id", None)
        anchor_chat = anchor_chat if anchor_chat is not None else getattr(
            getattr(reply, "chat", None), "id", None)
    if not anchor_msg or anchor_chat is None:
        return
    linker = globals().get("_qx102_link")
    link = str(linker(message) or "") if callable(linker) else ""
    if not link:
        return
    key = (str(getattr(bot, "token", ""))[:16], str(anchor_chat), int(anchor_msg))
    session = _QX104_SESSIONS.get(key)
    if session is None:
        session = {
            "bot": bot, "link": link, "anchor_chat": anchor_chat,
            "anchor_msg": int(anchor_msg), "count": 0, "ts": _t104.time(),
            "snapshot": _qx104_anchor_snapshot(bot, message),
        }
        _QX104_SESSIONS[key] = session
        with _cx104.suppress(RuntimeError):
            _a104.get_running_loop().create_task(_qx104_settle(key))
    session["count"] = int(session.get("count") or 0) + 1
    session["ts"] = _t104.time()


globals()["_qx102_track"] = _qx104_track

# send_poll is NOT re-wrapped: the section-102 wrapper resolves _qx102_track
# from the shared namespace at call time, so the override above is enough.


_log104("score cards restored; manual-topic anchors refresh every batch, "
        "AI topic cards untouched")

# ===== END SECTION 104 =====
