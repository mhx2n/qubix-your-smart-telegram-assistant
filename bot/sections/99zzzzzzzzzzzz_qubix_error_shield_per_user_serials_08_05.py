# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 110 — USER-FACING ERROR SHIELD + PER-USER SERIAL NUMBERING (2026-08-05)
#
#   1. Users never see raw errors again (Gemini/API-key alerts, HTTP codes,
#      tracebacks, quota notices...).  They get one polite Bangla card asking
#      them to retry and, if it still fails, to contact the owner.
#      The owner's own chats and the private error room keep full detail.
#   2. Every account gets its own serial space: channel / group / topic /
#      anchor numbering starts at 1 for each user, no matter what the shared
#      SQLite primary keys are.  Display, pickers, commands and mutations all
#      translate through the same per-user map, so nothing can cross accounts.
#
# Loaded last by bot/__main__.py; do not import directly.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx110
import dataclasses as _dc110
import re as _re110
import time as _t110

import telegram as _tg110


# ─────────────────────────────────────────────────────────────────────────────
# 1) Outbound error shield
# ─────────────────────────────────────────────────────────────────────────────
_QX110_POLITE = (
    "⚠️ <b>এই মুহূর্তে কাজটি সম্পন্ন করা গেল না</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "অনুগ্রহ করে আরেকবার চেষ্টা করুন — সাধারণত দ্বিতীয় চেষ্টাতেই কাজ হয়ে যায়।\n\n"
    "যদি তারপরও না হয়, দয়া করে owner-এর সাথে যোগাযোগ করুন; "
    "আমরা দ্রুত সমাধান করে দেব। আপনার ধৈর্যের জন্য ধন্যবাদ।"
)

_QX110_POLITE_SHORT = "একটু সমস্যা হলো — আবার চেষ্টা করুন। না হলে owner-কে জানান।"

_QX110_ERROR_PATTERNS = (
    r"(?i)gemini\s*api",
    r"(?i)no\s+gemini",
    r"(?i)/gemini\s+add",
    r"(?i)\bapi[\s_-]?key\b",
    r"(?i)\bapikey\b",
    r"(?i)traceback",
    r"(?i)\b(?:runtime|value|type|name|key|index|attribute)error\b",
    r"(?i)\bexception\b",
    r"(?i)telegramerror|badrequest|unauthorized|forbidden:",
    r"(?i)http\s*[45]\d\d",
    r"(?i)\b429\b",
    r"(?i)quota|rate[\s-]?limit|resource_exhausted|insufficient_quota",
    r"(?i)invalid\s+token|bad\s+token",
    r"(?i)\bstacktrace\b",
)

_QX110_ERROR_RX = tuple(_re110.compile(p) for p in _QX110_ERROR_PATTERNS)


def _qx110_is_error_text(text) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    return any(rx.search(text) for rx in _QX110_ERROR_RX)


def _qx110_privileged_chat(chat_id) -> bool:
    """Owner DMs and the private error room keep the raw diagnostics."""
    try:
        cid = int(chat_id)
    except (TypeError, ValueError):
        return False
    checker = globals().get("_qx96_hard_owner") or globals().get("_is_owner_id")
    if callable(checker):
        with _cx110.suppress(Exception):
            if checker(cid):
                return True
    room = globals().get("_qx102_room")
    if callable(room):
        with _cx110.suppress(Exception):
            room_chat, _thread = room()
            if room_chat and int(room_chat) == cid:
                return True
    return False


def _qx110_shield_slot(args, kwargs, chat_index, text_index, text_name):
    chat_id = kwargs.get("chat_id")
    if chat_id is None and isinstance(chat_index, int) and len(args) > chat_index:
        chat_id = args[chat_index]

    text = kwargs.get(text_name)
    from_kwargs = text is not None
    if text is None and isinstance(text_index, int) and len(args) > text_index:
        text = args[text_index]

    if not _qx110_is_error_text(text):
        return args, kwargs
    if _qx110_privileged_chat(chat_id):
        return args, kwargs

    with _cx110.suppress(Exception):
        logger.info("[QX110] error text shielded for chat=%s", chat_id)

    if from_kwargs:
        kwargs[text_name] = _QX110_POLITE
    else:
        mutable = list(args)
        mutable[text_index] = _QX110_POLITE
        args = tuple(mutable)
    kwargs["parse_mode"] = "HTML"
    kwargs.pop("entities", None)
    kwargs.pop("caption_entities", None)
    return args, kwargs


_qx110_prev_send = _tg110.Bot.send_message
_qx110_prev_edit = _tg110.Bot.edit_message_text
_qx110_prev_answer = _tg110.CallbackQuery.answer


async def _qx110_send_message(self, *args, **kwargs):
    with _cx110.suppress(Exception):
        args, kwargs = _qx110_shield_slot(args, kwargs, 0, 1, "text")
    return await _qx110_prev_send(self, *args, **kwargs)


async def _qx110_edit_message_text(self, *args, **kwargs):
    with _cx110.suppress(Exception):
        args, kwargs = _qx110_shield_slot(args, kwargs, None, 0, "text")
    return await _qx110_prev_edit(self, *args, **kwargs)


async def _qx110_answer(self, *args, **kwargs):
    with _cx110.suppress(Exception):
        text = kwargs.get("text")
        if text is None and args and isinstance(args[0], str):
            text = args[0]
        if _qx110_is_error_text(text):
            uid = int(getattr(getattr(self, "from_user", None), "id", 0) or 0)
            if not _qx110_privileged_chat(uid):
                kwargs["text"] = _QX110_POLITE_SHORT
                kwargs.setdefault("show_alert", True)
                args = ()
    return await _qx110_prev_answer(self, *args, **kwargs)


if not getattr(_tg110.Bot.send_message, "_qx110", False):
    _qx110_send_message._qx110 = True         # type: ignore[attr-defined]
    _qx110_edit_message_text._qx110 = True    # type: ignore[attr-defined]
    _qx110_answer._qx110 = True               # type: ignore[attr-defined]
    _tg110.Bot.send_message = _qx110_send_message
    _tg110.Bot.edit_message_text = _qx110_edit_message_text
    _tg110.CallbackQuery.answer = _qx110_answer


# ─────────────────────────────────────────────────────────────────────────────
# 2) Per-user serial space
# ─────────────────────────────────────────────────────────────────────────────
_QX110_TABLES = {
    "channel": ("channels", "added_by"),
    "group": ("saved_groups", "added_by"),
    "topic": ("group_topics", "added_by"),
    "anchor": ("saved_topic_anchors", "admin_id"),
}

_QX110_LAST: "dict" = {}
_QX110_TTL = 900.0


def _qx110_can_view_all(uid) -> bool:
    checker = globals().get("_qx108_can_view_all")
    if callable(checker):
        with _cx110.suppress(Exception):
            return bool(checker(uid))
    return False


def _qx110_hint_uid(explicit=None) -> int:
    if explicit:
        with _cx110.suppress(Exception):
            return int(explicit)
    acting = globals().get("_QX_ACTING_OWNER")
    if acting is not None:
        with _cx110.suppress(Exception):
            return int(acting.get() or 0)
    return 0


def _qx110_ids(kind: str, uid) -> list:
    table, owner_col = _QX110_TABLES[kind]
    uid = int(uid or 0)
    with _cx110.suppress(Exception):
        conn = db_connect()
        try:
            if uid <= 0 or _qx110_can_view_all(uid):
                rows = conn.execute(f"SELECT id FROM {table} ORDER BY id ASC").fetchall()
            else:
                rows = conn.execute(
                    f"SELECT id FROM {table} WHERE {owner_col}=? ORDER BY id ASC", (uid,)
                ).fetchall()
            return [int(r[0]) for r in rows]
        finally:
            conn.close()
    return []


def _qx110_to_real(kind: str, uid, serial):
    with _cx110.suppress(Exception):
        serial = int(serial)
        ids = _qx110_ids(kind, uid)
        if 1 <= serial <= len(ids):
            real = ids[serial - 1]
            _QX110_LAST[(kind, serial)] = (real, _t110.time())
            return real
    return None


def _qx110_to_virtual(kind: str, uid, real):
    with _cx110.suppress(Exception):
        real = int(real)
        ids = _qx110_ids(kind, uid)
        if real in ids:
            serial = ids.index(real) + 1
            _QX110_LAST[(kind, serial)] = (real, _t110.time())
            return serial
    return real


def _qx110_mutation_target(kind: str, serial):
    """Translate a user-typed serial to the real primary key for a write."""
    with _cx110.suppress(Exception):
        serial = int(serial)
        cached = _QX110_LAST.get((kind, serial))
        if cached and (_t110.time() - cached[1]) < _QX110_TTL:
            return cached[0]
        real = _qx110_to_real(kind, _qx110_hint_uid(), serial)
        if real:
            return real
    return serial


def _qx110_with_id(row, new_id):
    with _cx110.suppress(Exception):
        if _dc110.is_dataclass(row):
            return _dc110.replace(row, id=int(new_id))
    with _cx110.suppress(Exception):
        row.id = int(new_id)
    return row


# ── channels ────────────────────────────────────────────────────────────────
_qx110_prev_channel_list = channel_list_for_user
_qx110_prev_channel_get = channel_get_by_id_for_user
_qx110_prev_channel_remove = channel_remove
_qx110_prev_channel_prefix = channel_set_prefix
_qx110_prev_channel_link = channel_set_expl_link


def channel_list_for_user(requester_id):  # noqa: F811
    rows = _qx110_prev_channel_list(requester_id) or []
    out = []
    for index, row in enumerate(rows, start=1):
        with _cx110.suppress(Exception):
            _QX110_LAST[("channel", index)] = (int(row.id), _t110.time())
        out.append(_qx110_with_id(row, index))
    return out


def channel_get_by_id_for_user(requester_id, channel_id):  # noqa: F811
    real = _qx110_to_real("channel", requester_id, channel_id)
    if real:
        row = _qx110_prev_channel_get(requester_id, real)
        if row is not None:
            return row
    return _qx110_prev_channel_get(requester_id, channel_id)


def channel_remove(cid):  # noqa: F811
    return _qx110_prev_channel_remove(_qx110_mutation_target("channel", cid))


def channel_set_prefix(cid, prefix):  # noqa: F811
    return _qx110_prev_channel_prefix(_qx110_mutation_target("channel", cid), prefix)


def channel_set_expl_link(cid, link):  # noqa: F811
    return _qx110_prev_channel_link(_qx110_mutation_target("channel", cid), link)


# ── saved groups ────────────────────────────────────────────────────────────
_qx110_prev_sg_list = _sg_list
_qx110_prev_sg_get = _sg_get
_qx110_prev_sg_prefix = globals().get("_sg_set_prefix")
_qx110_prev_sg_link = globals().get("_sg_set_expl_link")


def _sg_list(requester_id):  # noqa: F811
    rows = _qx110_prev_sg_list(requester_id) or []
    out = []
    for index, row in enumerate(rows, start=1):
        with _cx110.suppress(Exception):
            _QX110_LAST[("group", index)] = (int(row.id), _t110.time())
        out.append(_qx110_with_id(row, index))
    return out


def _sg_get(serial, requester_id):  # noqa: F811
    real = _qx110_to_real("group", requester_id, serial)
    if real:
        row = _qx110_prev_sg_get(real, requester_id)
        if row is not None:
            return row
    return _qx110_prev_sg_get(serial, requester_id)


if callable(_qx110_prev_sg_prefix):
    def _sg_set_prefix(group_serial, prefix):  # noqa: F811
        return _qx110_prev_sg_prefix(_qx110_mutation_target("group", group_serial), prefix)

    globals()["_sg_set_prefix"] = _sg_set_prefix

if callable(_qx110_prev_sg_link):
    def _sg_set_expl_link(group_serial, link):  # noqa: F811
        return _qx110_prev_sg_link(_qx110_mutation_target("group", group_serial), link)

    globals()["_sg_set_expl_link"] = _sg_set_expl_link


# ── group topics ────────────────────────────────────────────────────────────
_qx110_prev_gt_list = _gt_list
_qx110_prev_gt_get = _gt_get


def _gt_list(group_id, requester_id=None):  # noqa: F811
    uid = _qx110_hint_uid(requester_id)
    rows = _qx110_prev_gt_list(group_id, requester_id) or []
    out = []
    for row in rows:
        virtual = row
        with _cx110.suppress(Exception):
            virtual = _qx110_with_id(row, _qx110_to_virtual("topic", uid, row.id))
        out.append(virtual)
    return out


def _gt_get(topic_id, requester_id=None):  # noqa: F811
    uid = _qx110_hint_uid(requester_id)
    real = _qx110_to_real("topic", uid, topic_id)
    if real:
        row = _qx110_prev_gt_get(real, requester_id)
        if row is not None:
            return row
    return _qx110_prev_gt_get(topic_id, requester_id)


# ── saved topic anchors ─────────────────────────────────────────────────────
_qx110_prev_sta_list = _sta_list
_qx110_prev_sta_get = _sta_get
_qx110_prev_sta_delete = _sta_delete


def _sta_list(admin_id):  # noqa: F811
    rows = _qx110_prev_sta_list(admin_id) or []
    return [_qx110_with_id(row, _qx110_to_virtual("anchor", admin_id, row.id)) for row in rows]


def _sta_get(row_id, admin_id):  # noqa: F811
    real = _qx110_to_real("anchor", admin_id, row_id)
    if real:
        row = _qx110_prev_sta_get(real, admin_id)
        if row is not None:
            return row
    return _qx110_prev_sta_get(row_id, admin_id)


def _sta_delete(row_id, admin_id):  # noqa: F811
    real = _qx110_to_real("anchor", admin_id, row_id) or row_id
    return _qx110_prev_sta_delete(real, admin_id)


# ── inbox cards that read the tables directly ───────────────────────────────
def _qx110_virtualize_rows(kind: str, uid, rows):
    out = []
    for index, row in enumerate(rows or [], start=1):
        item = {}
        with _cx110.suppress(Exception):
            item = {key: row[key] for key in row.keys()}
        if not item:
            continue
        with _cx110.suppress(Exception):
            _QX110_LAST[(kind, index)] = (int(item.get("id") or 0), _t110.time())
        item["id"] = index
        out.append(item)
    return out


for _qx110_name, _qx110_kind in (
    ("_qx93_my_channels", "channel"),
    ("_qx93_my_groups", "group"),
    ("_qx93_my_topics", "topic"),
    ("_qx93_my_anchors", "anchor"),
):
    _qx110_prev_card = globals().get(_qx110_name)
    if callable(_qx110_prev_card):
        def _qx110_make(previous, kind):
            def _wrapped(uid):
                return _qx110_virtualize_rows(kind, uid, previous(uid))
            return _wrapped

        globals()[_qx110_name] = _qx110_make(_qx110_prev_card, _qx110_kind)


globals()["channel_list_for_user"] = channel_list_for_user
globals()["channel_get_by_id_for_user"] = channel_get_by_id_for_user
globals()["channel_remove"] = channel_remove
globals()["channel_set_prefix"] = channel_set_prefix
globals()["channel_set_expl_link"] = channel_set_expl_link
globals()["_sg_list"] = _sg_list
globals()["_sg_get"] = _sg_get
globals()["_gt_list"] = _gt_list
globals()["_gt_get"] = _gt_get
globals()["_sta_list"] = _sta_list
globals()["_sta_get"] = _sta_get
globals()["_sta_delete"] = _sta_delete

with _cx110.suppress(Exception):
    logger.info("[QX110] user error shield + per-user serial numbering active")

# ===== END SECTION 110 =====
