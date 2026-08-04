# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 116 — QUBIX TRANSPORT SCRUB GUARD (2026-08-05)
#
# python-telegram-bot normally sends through ExtBot. Patch that concrete
# transport as well as the Bot-level wrappers from section 114 so no legacy
# Master text can bypass Student workspace isolation.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx116
import telegram.ext as _tgext116


def _qx116_scrub_args(args, kwargs, text_index: int, chat_index: int):
    call_args = list(args)
    call_kwargs = dict(kwargs)
    chat_id = call_kwargs.get("chat_id")
    if chat_id is None and len(call_args) > chat_index:
        chat_id = call_args[chat_index]
    try:
        student = int(chat_id or 0) > 0 and _qx114_is_student(int(chat_id))
    except Exception:
        student = False
    if not student:
        return tuple(call_args), call_kwargs

    scrubber = globals().get("_qx114_scrub")
    if not callable(scrubber):
        return tuple(call_args), call_kwargs
    if "text" in call_kwargs and isinstance(call_kwargs.get("text"), str):
        call_kwargs["text"] = scrubber(call_kwargs["text"])
    elif len(call_args) > text_index and isinstance(call_args[text_index], str):
        call_args[text_index] = scrubber(call_args[text_index])
    return tuple(call_args), call_kwargs


def _qx116_wrap_extbot(name: str, text_index: int, chat_index: int) -> None:
    original = getattr(_tgext116.ExtBot, name, None)
    if not callable(original) or getattr(original, "_qx116", False):
        return

    async def wrapper(self, *args, **kwargs):
        with _cx116.suppress(Exception):
            args, kwargs = _qx116_scrub_args(args, kwargs, text_index, chat_index)
        return await original(self, *args, **kwargs)

    wrapper._qx116 = True  # type: ignore[attr-defined]
    setattr(_tgext116.ExtBot, name, wrapper)


with _cx116.suppress(Exception):
    # send_message(chat_id, text, ...)
    _qx116_wrap_extbot("send_message", text_index=1, chat_index=0)
with _cx116.suppress(Exception):
    # edit_message_text(text, chat_id=None, ...)
    _qx116_wrap_extbot("edit_message_text", text_index=0, chat_index=1)


_qx_log.info("[SECTION 116] Qubix ExtBot Student transport scrub guard loaded.")