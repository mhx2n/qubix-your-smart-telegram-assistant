# ──────────────────────────────────────────────────────────────────────────────
# Section 102 (2026-08-04) — Real rich quiz output · prefix header · identity fix
#
# Fixes:
#   1) Quiz cards leaked raw Python reprs (["প্রশ্ন"], ["(ক) ", "S²"]) in personal
#      bots and channels.  Cause: section 98 flattened rich blocks with
#      str(block["text"]) where "text" is a LIST of parts.  Now blocks are sent
#      as real Bot API rich blocks with the CALLING bot token, then as proper
#      Markdown (with $…$ math), then as clean HTML — never a repr.
#   2) The "প্রশ্ন" / "Question" label is removed from the card; that first line
#      now carries the quiz prefix instead.
#   3) "নিজের bot & identity" was empty because the outbound scrubber deleted the
#      only line in that section.  The section now has real content, and any
#      header left without a body is dropped automatically.
#
# DO NOT import directly — exec'd in the shared namespace by bot/__main__.py.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a102
import contextlib as _cx102
import re as _re102

import requests as _rq102
import telegram as _tg102


def _log102(msg: str) -> None:
    with _cx102.suppress(Exception):
        logger.info("[S102] %s", msg)  # type: ignore[name-defined]


# ═════════════════════════════════════════════════════════════════════════════
# 1) Blocks → text renderers (never a Python repr)
# ═════════════════════════════════════════════════════════════════════════════
def _qx102_part_text(part, *, math_fence: str = "$") -> str:
    if isinstance(part, dict):
        kind = str(part.get("type") or "")
        if kind == "mathematical_expression":
            expr = str(part.get("expression") or "").strip()
            if not expr:
                return ""
            if not math_fence:
                mathify = globals().get("mathify_79")
                if callable(mathify):
                    with _cx102.suppress(Exception):
                        return str(mathify(expr) or expr)
                return expr
            return math_fence + expr + math_fence
        for key in ("text", "markdown", "expression", "caption"):
            value = part.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, list):
                return "".join(_qx102_part_text(p, math_fence=math_fence) for p in value)
        return ""
    if isinstance(part, list):
        return "".join(_qx102_part_text(p, math_fence=math_fence) for p in part)
    return str(part or "")


def _qx102_blocks_text(blocks, *, math_fence: str = "$") -> str:
    lines = []
    for block in blocks or []:
        if not isinstance(block, dict):
            lines.append(str(block or ""))
            continue
        kind = str(block.get("type") or "paragraph")
        if kind == "divider":
            lines.append("───────────────")
            continue
        body = _qx102_part_text(block.get("text", ""), math_fence=math_fence).strip()
        if body:
            lines.append(body)
    out = "\n\n".join(lines)
    return _re102.sub(r"\n{3,}", "\n\n", out).strip()


globals()["_qx102_blocks_text"] = _qx102_blocks_text


# ═════════════════════════════════════════════════════════════════════════════
# 2) Rich block transport that honours the calling bot's own token
# ═════════════════════════════════════════════════════════════════════════════
_qx102_prev_blocks = globals().get("rich_send_blocks_77")


async def _qx102_post_blocks(bot, chat_id, blocks, *, reply_to=None, thread_id=None,
                             silent=False, reply_markup=None):
    """POST real rich blocks with this bot's token. Returns shim or None."""
    token = str(getattr(bot, "token", "") or "").strip()
    if not token or not isinstance(blocks, list) or not blocks:
        return None
    payload = {
        "chat_id": chat_id,
        "rich_message": {"blocks": blocks},
        "disable_notification": bool(silent),
    }
    if thread_id:
        with _cx102.suppress(Exception):
            payload["message_thread_id"] = int(thread_id)
    if reply_to:
        with _cx102.suppress(Exception):
            payload["reply_parameters"] = {"message_id": int(reply_to)}

    def _send():
        return _rq102.post(
            "https://api.telegram.org/bot%s/sendRichMessage" % token,
            json=payload, timeout=20,
        )

    try:
        response = await _a102.wait_for(_a102.to_thread(_send), timeout=22)
        data = response.json()
        message_id = int((data.get("result") or {}).get("message_id") or 0)
        if response.ok and data.get("ok") and message_id:
            shim = globals().get("_RichSentMessage77")
            sent = shim(bot, chat_id, message_id, "") if callable(shim) else None
            if reply_markup is not None:
                with _cx102.suppress(Exception):
                    await bot.edit_message_reply_markup(
                        chat_id=chat_id, message_id=message_id,
                        reply_markup=reply_markup,
                    )
            return sent
        _log102("blocks rejected [%s]: %s" % (response.status_code, str(data)[:200]))
    except Exception as e:
        _log102("blocks post failed: %s" % e)
    return None


async def rich_send_blocks_77(bot, chat_id, blocks, **kwargs):  # noqa: F811
    """Real rich blocks → rich Markdown → clean HTML. Never leaks a repr."""
    reply_to = kwargs.get("reply_to")
    thread_id = kwargs.get("thread_id")
    silent = bool(kwargs.get("silent"))
    reply_markup = kwargs.get("reply_markup")

    sent = await _qx102_post_blocks(
        bot, chat_id, blocks, reply_to=reply_to, thread_id=thread_id,
        silent=silent, reply_markup=reply_markup,
    )
    if sent is not None:
        return sent

    markdown = _qx102_blocks_text(blocks, math_fence="$")
    native = globals().get("_qx98_native_rich")
    if markdown and callable(native):
        with _cx102.suppress(Exception):
            sent = await native(
                bot, chat_id, markdown, reply_to=reply_to, thread_id=thread_id,
                silent=silent, reply_markup=reply_markup,
            )
            if sent is not None:
                return sent

    visible = _qx102_blocks_text(blocks, math_fence="")
    plain = globals().get("_qx98_plain_send")
    to_html = globals().get("_qx98_html_fallback")
    body = to_html(visible) if callable(to_html) else visible
    if body and callable(plain):
        with _cx102.suppress(Exception):
            return await plain(
                bot, chat_id, body, reply_to=reply_to, thread_id=thread_id,
                silent=silent, reply_markup=reply_markup,
            )
    return None


globals()["rich_send_blocks_77"] = rich_send_blocks_77


# ═════════════════════════════════════════════════════════════════════════════
# 3) Card header: drop the "প্রশ্ন" label, promote the quiz prefix
# ═════════════════════════════════════════════════════════════════════════════
_QX102_TITLES = {"প্রশ্ন", "প্রশ্ন:", "question", "question:", "প্রশ্নঃ"}
_qx102_prev_math_blocks = (globals().get("_rich_math_blocks_88")
                           or globals().get("_rich_math_blocks_83")
                           or globals().get("_rich_math_blocks_79"))


def _qx102_is_title_block(block) -> bool:
    if not isinstance(block, dict) or str(block.get("type") or "") != "paragraph":
        return False
    body = _qx102_part_text(block.get("text", ""), math_fence="").strip()
    return body.lower().strip(" :\u200b") in {t.lower().strip(" :\u200b")
                                             for t in _QX102_TITLES}


def _qx102_split_prefix(block):
    """Give the prefix line its own paragraph so it heads the card."""
    if not isinstance(block, dict) or str(block.get("type") or "") != "paragraph":
        return [block]
    parts = block.get("text")
    parts = parts if isinstance(parts, list) else [parts]
    if not parts or not isinstance(parts[0], str) or "\n" not in parts[0]:
        return [block]
    head, _, tail = parts[0].partition("\n")
    head = head.replace("\u200b", "").strip()
    tail_parts = ([tail.lstrip("\u200b")] if tail.strip() else []) + list(parts[1:])
    if not head or len(head) > 120 or not tail_parts:
        return [block]
    return [
        {"type": "paragraph", "text": [head]},
        {"type": "paragraph", "text": tail_parts},
    ]


def _qx102_math_blocks(question, options, lang="bn"):
    blocks = []
    if callable(_qx102_prev_math_blocks):
        with _cx102.suppress(Exception):
            blocks = list(_qx102_prev_math_blocks(question, options, lang) or [])
    if not blocks:
        return blocks
    blocks = [b for b in blocks if not _qx102_is_title_block(b)]
    if blocks:
        blocks = _qx102_split_prefix(blocks[0]) + blocks[1:]
    return blocks


for _name in ("_rich_math_blocks_79", "_rich_math_blocks_83",
              "_rich_math_blocks_88", "_rich_math_blocks_102"):
    globals()[_name] = _qx102_math_blocks


# ═════════════════════════════════════════════════════════════════════════════
# 4) Identity section is never empty again
# ═════════════════════════════════════════════════════════════════════════════
with _cx102.suppress(Exception):
    _QX97_DROP_LINE = tuple(  # type: ignore[name-defined]
        marker for marker in _QX97_DROP_LINE  # type: ignore[name-defined]
        if "mybot" not in marker
    )
    globals()["_QX97_DROP_LINE"] = _QX97_DROP_LINE

_QX102_IDENTITY = (
    "<b>6 · নিজের bot &amp; identity</b>\n"
    "<code>/addbot &lt;token&gt;</code> — নিজের নামে bot চালু\n"
    "<code>/mybot</code> — bot status · <code>/myid</code> — আপনার User ID\n\n"
)

_QX102_TENANT_IDENTITY = (
    "<b>6 · আপনার identity</b>\n"
    "🤖 এই bot আপনার নিজের নামেই চলছে — আলাদা setup লাগবে না।\n\n"
)

_QX102_HEADER_RX = _re102.compile(r"^<b>\s*\d+\s*·")


def _qx102_fill_identity(text: str, tenant: bool) -> str:
    """Replace an empty/partial identity section and drop bodiless headers."""
    source = str(text or "")
    if not source:
        return source
    lines = source.split("\n")
    out = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if _QX102_HEADER_RX.match(line.strip()):
            body = []
            cursor = index + 1
            while cursor < len(lines) and not _QX102_HEADER_RX.match(lines[cursor].strip()):
                body.append(lines[cursor])
                cursor += 1
            joined = "\n".join(body)
            has_body = bool(_re102.sub(r"<[^>]+>|\s", "", joined))
            identity = ("identity" in line) or ("নিজের bot" in line)
            if identity:
                block = _QX102_TENANT_IDENTITY if tenant else _QX102_IDENTITY
                out.append(block.rstrip("\n"))
                out.append("")
            elif has_body:
                out.append(line)
                out.extend(body)
            index = cursor
            continue
        out.append(line)
        index += 1
    return _re102.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _qx102_tenant() -> bool:
    flag = globals().get("_QX97_TENANT")
    if flag is not None:
        with _cx102.suppress(Exception):
            return bool(flag.get())
    return False


_qx102_prev_send = _tg102.Bot.send_message
_qx102_prev_edit = _tg102.Bot.edit_message_text


def _qx102_polish(value):
    if not isinstance(value, str) or "<b>" not in value:
        return value
    if "identity" not in value and "নিজের bot" not in value:
        return value
    with _cx102.suppress(Exception):
        return _qx102_fill_identity(value, _qx102_tenant())
    return value


def _qx102_slot(args, kwargs, index, name):
    if name in kwargs:
        kwargs[name] = _qx102_polish(kwargs[name])
        return args, kwargs
    if isinstance(index, int) and len(args) > index and isinstance(args[index], str):
        items = list(args)
        items[index] = _qx102_polish(items[index])
        return tuple(items), kwargs
    return args, kwargs


async def _qx102_send_message(self, *args, **kwargs):
    with _cx102.suppress(Exception):
        args, kwargs = _qx102_slot(args, kwargs, 1, "text")
    return await _qx102_prev_send(self, *args, **kwargs)


async def _qx102_edit_message_text(self, *args, **kwargs):
    with _cx102.suppress(Exception):
        args, kwargs = _qx102_slot(args, kwargs, 0, "text")
    return await _qx102_prev_edit(self, *args, **kwargs)


if not getattr(_tg102.Bot.send_message, "_qx102", False):
    _qx102_send_message._qx102 = True       # type: ignore[attr-defined]
    _qx102_edit_message_text._qx102 = True  # type: ignore[attr-defined]
    _tg102.Bot.send_message = _qx102_send_message
    _tg102.Bot.edit_message_text = _qx102_edit_message_text


# Keep the static user sheet correct at the source as well.
with _cx102.suppress(Exception):
    for _card_name in ("QX95_USER_COMMANDS_CARD", "QX94_USER_COMMANDS_CARD",
                       "QX93_COMMANDS_CARD"):
        _card = globals().get(_card_name)
        if isinstance(_card, str) and _card:
            globals()[_card_name] = _qx102_fill_identity(_card, False)

_log102("rich quiz blocks fixed (no reprs), prefix heads the card, identity filled")
