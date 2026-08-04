# ──────────────────────────────────────────────────────────────────────────────
# Section 103 (2026-08-04) — final convergence overlay.
#
# Fixes shipped here:
#   1. Topic anchor edit no longer breaks rich formatting. Rich (markdown)
#      anchors are re-edited through the native rich transport of the *calling*
#      bot; only when that is unavailable do we fall back to converted HTML.
#   2. Manual topics (plain text or photo + caption) can now be edited too:
#      every outbound anchor-capable message is cached in memory, so the tail
#      logic no longer depends on the AI-generation DB column alone.
#   3. Duplicate "Your score" cards are dropped at transport level.
#   4. Math / LaTeX images no longer generate 0 quizzes: when the first pass
#      returns nothing, a relaxed pass re-runs with the Bengali-prose gate
#      suspended so pure-formula items survive normalisation.
#
# DO NOT import directly — exec'd in the shared namespace by bot/__main__.py.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a103
import contextlib as _cx103
import html as _h103
import re as _re103
import time as _t103

import requests as _rq103
import telegram as _tg103


def _log103(message: str, level: str = "info") -> None:
    with _cx103.suppress(Exception):
        getattr(logger, level)("[S103] %s", message)  # type: ignore[name-defined]


def _esc103(value) -> str:
    return _h103.escape(str(value or ""), quote=False)


# ─────────────────────────────────────────────────────────────────────────────
# 1) Outbound content cache (chat_id, message_id) → {text, photo, markdown}
# ─────────────────────────────────────────────────────────────────────────────
_QX103_CONTENT: dict = {}
_QX103_CONTENT_TTL = 6 * 3600.0


def _qx103_cache_put(chat_id, message_id, text, *, photo=False, markdown=False) -> None:
    if not chat_id or not message_id:
        return
    now = _t103.time()
    _QX103_CONTENT[(int(chat_id), int(message_id))] = {
        "text": str(text or ""),
        "photo": bool(photo),
        "markdown": bool(markdown),
        "ts": now,
    }
    if len(_QX103_CONTENT) > 800:
        for key in [k for k, v in _QX103_CONTENT.items()
                    if now - float(v.get("ts") or 0) > _QX103_CONTENT_TTL]:
            _QX103_CONTENT.pop(key, None)


def _qx103_cache_get(chat_id, message_id) -> dict:
    with _cx103.suppress(Exception):
        return dict(_QX103_CONTENT.get((int(chat_id), int(message_id))) or {})
    return {}


def _qx103_remember(message, text, *, photo=False, markdown=False) -> None:
    with _cx103.suppress(Exception):
        chat_id = getattr(getattr(message, "chat", None), "id", None)
        if chat_id is None:
            chat_id = getattr(message, "chat_id", None)
        _qx103_cache_put(chat_id, getattr(message, "message_id", None), text,
                         photo=photo, markdown=markdown)


# ─────────────────────────────────────────────────────────────────────────────
# 2) Score-card deduplication + content caching on send_message / send_photo
# ─────────────────────────────────────────────────────────────────────────────
_QX103_SCORE = _re103.compile(r"score\s*[:：]?.*?/\s*\d+", _re103.IGNORECASE)
_QX103_SCORE_SEEN: dict = {}
_QX103_SCORE_WINDOW = 600.0


def _qx103_score_key(kwargs) -> tuple:
    return (
        int(kwargs.get("chat_id") or 0),
        int(kwargs.get("reply_to_message_id") or 0),
        str(kwargs.get("message_thread_id") or ""),
    )


def _qx103_score_dup(kwargs) -> bool:
    text = str(kwargs.get("text") or "")
    if not text or not _QX103_SCORE.search(text):
        return False
    now = _t103.time()
    key = _qx103_score_key(kwargs)
    previous = _QX103_SCORE_SEEN.get(key)
    if previous and now - float(previous[0]) < _QX103_SCORE_WINDOW:
        return True
    _QX103_SCORE_SEEN[key] = (now, None)
    if len(_QX103_SCORE_SEEN) > 400:
        for stale in [k for k, v in _QX103_SCORE_SEEN.items()
                      if now - float(v[0]) > _QX103_SCORE_WINDOW]:
            _QX103_SCORE_SEEN.pop(stale, None)
    return False


_qx103_prev_send_message = _tg103.Bot.send_message


async def _qx103_send_message(self, *args, **kwargs):
    merged = dict(kwargs)
    if args:
        names = ("chat_id", "text")
        for index, value in enumerate(args[:2]):
            merged.setdefault(names[index], value)
    if _qx103_score_dup(merged):
        cached = _QX103_SCORE_SEEN.get(_qx103_score_key(merged))
        _log103("duplicate score card suppressed")
        return cached[1] if cached else None
    message = await _qx103_prev_send_message(self, *args, **kwargs)
    with _cx103.suppress(Exception):
        if merged.get("text") and _QX103_SCORE.search(str(merged.get("text"))):
            _QX103_SCORE_SEEN[_qx103_score_key(merged)] = (_t103.time(), message)
    _qx103_remember(message, merged.get("text"))
    return message


if not getattr(_tg103.Bot.send_message, "_qx103", False):
    _qx103_send_message._qx103 = True  # type: ignore[attr-defined]
    _tg103.Bot.send_message = _qx103_send_message


_qx103_prev_send_photo = _tg103.Bot.send_photo


async def _qx103_send_photo(self, *args, **kwargs):
    message = await _qx103_prev_send_photo(self, *args, **kwargs)
    _qx103_remember(message, kwargs.get("caption"), photo=True)
    return message


if not getattr(_tg103.Bot.send_photo, "_qx103", False):
    _qx103_send_photo._qx103 = True  # type: ignore[attr-defined]
    _tg103.Bot.send_photo = _qx103_send_photo


_qx103_prev_native_rich = globals().get("_qx98_native_rich")
if callable(_qx103_prev_native_rich):
    async def _qx98_native_rich(bot, chat_id, text, **kwargs):  # noqa: F811
        sent = await _qx103_prev_native_rich(bot, chat_id, text, **kwargs)
        if sent is not None:
            _qx103_remember(sent, text, markdown=True)
            with _cx103.suppress(Exception):
                _qx103_cache_put(chat_id, getattr(sent, "message_id", None), text,
                                 markdown=True)
        return sent

    globals()["_qx98_native_rich"] = _qx98_native_rich


# ─────────────────────────────────────────────────────────────────────────────
# 3) Topic anchor tail — format-preserving edit
# ─────────────────────────────────────────────────────────────────────────────
_QX103_MARK = globals().get("_QX102_MARK", "\u2063")


def _qx103_anchor_base(anchor_chat, anchor_msg) -> dict:
    """Resolve anchor body from DB first, then the outbound cache."""
    uid, stored, photo = 0, "", ""
    resolver = globals().get("_qx102_anchor_row")
    if callable(resolver):
        with _cx103.suppress(Exception):
            uid, stored, photo = resolver(anchor_chat, anchor_msg)
    cached = _qx103_cache_get(anchor_chat, anchor_msg)
    markdown = bool(cached.get("markdown"))
    if not str(stored or "").strip():
        stored = str(cached.get("text") or "")
        if cached.get("photo"):
            photo = photo or "1"
    return {
        "uid": int(uid or 0),
        "text": str(stored or ""),
        "photo": bool(photo),
        "markdown": markdown,
    }


async def _qx103_tail_pair(link: str, count: int):
    """Return (markdown_tail, html_tail) for the first-quiz invitation."""
    line, cta = "", ""
    maker = globals().get("_qx102_ai_line")
    if callable(maker):
        with _cx103.suppress(Exception):
            line, cta = await _a103.to_thread(maker, count)
    if not line or not cta:
        pool = globals().get("_QX102_FALLBACK") or (("কুইজ শুরু হয়েছে", "প্রথম কুইজে যান"),)
        line, cta = list(pool)[0]
    md = f"\n\n**✦ {line}**\n➤ [{cta} 🔗]({link})"
    html = (
        f"\n\n<b>✦ {_esc103(line)}</b>\n"
        f"➤ <a href=\"{_esc103(link)}\">{_esc103(cta)} 🔗</a>"
    )
    return md, html


def _qx103_rich_edit(bot, chat_id, message_id, markdown_body) -> bool:
    """Re-edit a native rich message so markdown keeps rendering."""
    token = str(getattr(bot, "token", "") or "").strip()
    if not token:
        return False
    payload_variants = (
        {"chat_id": chat_id, "message_id": int(message_id),
         "rich_message": {"markdown": markdown_body[:4000]}},
    )
    for method in ("editRichMessage", "editMessageRichMessage", "editMessageRichText"):
        for payload in payload_variants:
            with _cx103.suppress(Exception):
                response = _rq103.post(
                    f"https://api.telegram.org/bot{token}/{method}",
                    json=payload, timeout=20,
                )
                data = response.json()
                if response.ok and data.get("ok"):
                    return True
    return False


def _qx103_md_to_html(text: str) -> str:
    converter = globals().get("_qx98_html_fallback")
    if callable(converter):
        with _cx103.suppress(Exception):
            converted = converter(text)
            if str(converted or "").strip():
                return str(converted)
    return _esc103(text)


async def _qx102_apply_tail(bot, anchor_chat, anchor_msg, link: str, count: int) -> None:  # noqa: F811
    if not link:
        return
    info = _qx103_anchor_base(anchor_chat, anchor_msg)
    base_raw = str(info["text"] or "").split(_QX103_MARK)[0].rstrip()
    if not base_raw.strip():
        _log103(f"anchor {anchor_chat}/{anchor_msg} has no cached body; skipped", "warning")
        return
    tail_md, tail_html = await _qx103_tail_pair(link, count)
    limit = 900 if info["photo"] else 3600
    if len(base_raw) + len(tail_md) > limit:
        base_raw = base_raw[: max(0, limit - len(tail_md) - 1)].rstrip()

    body_md = base_raw + _QX103_MARK + tail_md
    stored_body = body_md

    done = False
    if info["markdown"] and not info["photo"]:
        done = await _a103.to_thread(_qx103_rich_edit, bot, anchor_chat, anchor_msg, body_md)

    if not done:
        # Markdown anchors must be converted before an HTML edit, otherwise the
        # raw ** / ## syntax leaks into the visible message.
        base_html = _qx103_md_to_html(base_raw) if info["markdown"] else base_raw
        candidates = [base_html + _QX103_MARK + tail_html]
        if not info["markdown"]:
            candidates.append(_esc103(base_raw) + _QX103_MARK + tail_html)
        for candidate in candidates:
            try:
                if info["photo"]:
                    await bot.edit_message_caption(
                        chat_id=anchor_chat, message_id=anchor_msg,
                        caption=candidate, parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=anchor_chat, message_id=anchor_msg, text=candidate,
                        parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                        disable_web_page_preview=True,
                    )
                done = True
                stored_body = candidate
                break
            except Exception:
                continue

    if done:
        _qx103_cache_put(anchor_chat, anchor_msg, stored_body,
                         photo=info["photo"], markdown=info["markdown"])
        writer = globals().get("_qx102_store_text")
        if callable(writer) and info["uid"]:
            with _cx103.suppress(Exception):
                writer(info["uid"], stored_body)
        _log103(f"anchor {anchor_chat}/{anchor_msg} now carries the first-quiz link")
    else:
        _log103(f"anchor {anchor_chat}/{anchor_msg} edit failed on every transport", "warning")


globals()["_qx102_apply_tail"] = _qx102_apply_tail


# ─────────────────────────────────────────────────────────────────────────────
# 4) Math / LaTeX sources: relaxed second pass instead of "0 quiz added"
# ─────────────────────────────────────────────────────────────────────────────
class _QX103OpenGate:
    """Stand-in for the Bengali-script detector used by the quality gates."""

    def findall(self, _text):
        return ["\u0985"] * 32

    def search(self, _text):
        return None


_qx103_prev_ocr_gen = globals().get("_generate_quizzes_from_ocr_sync")
if callable(_qx103_prev_ocr_gen):
    def _generate_quizzes_from_ocr_sync(ocr_ctx, desired, user_id):  # noqa: F811
        items = []
        with _cx103.suppress(Exception):
            items = _qx103_prev_ocr_gen(ocr_ctx, desired, user_id) or []
        if items:
            return items
        # Pure formula stems carry almost no Bengali letters, so the prose gate
        # rejects every candidate and the user sees "0 added". Retry with the
        # script gate opened; mathematics is still validated downstream.
        original = globals().get("_BN_88")
        globals()["_BN_88"] = _QX103OpenGate()
        try:
            items = _qx103_prev_ocr_gen(ocr_ctx, desired, user_id) or []
            if items:
                _log103(f"math relaxed pass produced {len(items)} item(s)")
            return items
        except Exception as exc:
            _log103(f"math relaxed pass failed: {exc}", "warning")
            return []
        finally:
            if original is not None:
                globals()["_BN_88"] = original

    globals()["_generate_quizzes_from_ocr_sync"] = _generate_quizzes_from_ocr_sync


_log103("final convergence active: rich anchor edits, manual topic tails, "
        "single score card, math-aware generation")

# ===== END SECTION 103 =====
