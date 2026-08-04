# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 113 — QUBIX TIER LOCK + AI SPEED (2026-08-05)
#
#   1. Hard panel lock:
#        • Student tier  → ONLY the student panel is ever rendered.
#          Every master card / master button / master command is intercepted
#          BEFORE the older handlers can answer (very early handler groups).
#        • Master tier   → student widgets never appear.
#        • Trial users   → can flip between the two plans any time through the
#          main welcome card (◀️ Plan পরিবর্তন button · /plans command).
#
#   2. AI help reliability:
#        • dedicated thread pool + tighter timeouts + one retry, so the
#          "উত্তর তৈরি হচ্ছে…" card never stays stuck.
#        • edit/send retry without parse_mode when Telegram rejects the HTML.
#
#   Nothing earlier is rewritten — this section only layers over section 112.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx113
import telegram as _tg113
from concurrent.futures import ThreadPoolExecutor as _Pool113

_QX113_POOL = _Pool113(max_workers=6, thread_name_prefix="qx113ai")


# ─────────────────────────────────────────────────────────────────────────────
# 0) helpers
# ─────────────────────────────────────────────────────────────────────────────
def _qx113_uid(update, context) -> int:
    with _cx113.suppress(Exception):
        return int(_qx95_scope_uid(update, context) or 0)
    with _cx113.suppress(Exception):
        return int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    return 0


def _qx113_owner_view(update, context) -> bool:
    with _cx113.suppress(Exception):
        return bool(_qx93_privileged(update)) and not bool(_qx95_is_tenant(context))
    return False


def _qx113_tier(uid: int) -> str:
    with _cx113.suppress(Exception):
        return str(_qx112_tier(int(uid)) or "")
    return "master"


def _qx113_is_trial(uid: int) -> bool:
    with _cx113.suppress(Exception):
        if _qx_real_owner(int(uid)):
            return False
    with _cx113.suppress(Exception):
        return str((_qx_access(int(uid)) or {}).get("mode") or "") == "trial"
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 1) Keyboards — trial users get a "plan পরিবর্তন" door back to the welcome card
# ─────────────────────────────────────────────────────────────────────────────
_qx113_prev_student_kb = globals().get("_qx112_student_menu_kb")
_qx113_prev_master_kb = globals().get("_qx93_menu_kb")


def _qx112_student_menu_kb():  # noqa: F811
    rows = []
    with _cx113.suppress(Exception):
        base = _qx113_prev_student_kb()
        rows = [list(r) for r in (getattr(base, "inline_keyboard", []) or [])]
    if not rows:
        rows = [[InlineKeyboardButton("📜 My Commands", callback_data="qx112:cmds")]]
    uid = 0
    with _cx113.suppress(Exception):
        uid = int(_QX_ACTING_OWNER.get() or 0)
    if uid and _qx113_is_trial(uid):
        rows.append([InlineKeyboardButton("◀️ Plan পরিবর্তন", callback_data="qx112:plans")])
    with _cx113.suppress(Exception):
        return InlineKeyboardMarkup(rows)
    return _qx113_prev_student_kb()


def _qx93_menu_kb():  # noqa: F811
    base = _qx113_prev_master_kb() if callable(_qx113_prev_master_kb) else None
    uid = 0
    with _cx113.suppress(Exception):
        uid = int(_QX_ACTING_OWNER.get() or 0)
    if base is None or not uid or not _qx113_is_trial(uid):
        return base
    with _cx113.suppress(Exception):
        rows = [list(r) for r in (getattr(base, "inline_keyboard", []) or [])]
        rows.append([InlineKeyboardButton("◀️ Plan পরিবর্তন", callback_data="qx112:plans")])
        return InlineKeyboardMarkup(rows)
    return base


globals()["_qx112_student_menu_kb"] = _qx112_student_menu_kb
globals()["_qx93_menu_kb"] = _qx93_menu_kb


# ─────────────────────────────────────────────────────────────────────────────
# 2) Student surface definition (tight)
# ─────────────────────────────────────────────────────────────────────────────
QX113_STUDENT_COMMANDS = {
    "start", "menu", "guide", "help", "cmd", "commands",
    "gen", "g", "buffer", "b", "buffercount", "bc",
    "done", "d", "clear", "c", "myid", "id", "plans", "plan",
    "switchaccess", "switchacsess", "switchasccess", "sa",
}

# Callbacks a student may reach untouched (generation / buffer / export flows).
QX113_STUDENT_CALLBACK_OK = (
    "qx112:", "qx93:gen", "qx93:export", "qx93:ask",
    "pba:csv", "pba:clr", "pba:close",
    "g59:", "genq:", "src59:", "gen:", "buf:",
)

# Master cards that must be re-rendered as their student equivalent.
QX113_STUDENT_CALLBACK_MAP = {
    "qx93:menu": "menu",
    "qx93:access": "menu",
    "qx93:cmds": "cmds",
    "qx93:mybot": "menu",
    "qx94:menu": "menu",
    "qx92:menu": "menu",
}

with _cx113.suppress(Exception):
    globals()["QX112_STUDENT_COMMANDS"] = set(QX113_STUDENT_COMMANDS)
    globals()["QX112_STUDENT_CALLBACK_OK"] = tuple(QX113_STUDENT_CALLBACK_OK)

with _cx113.suppress(Exception):
    _qx113_ws = globals().get("QX_WORKSPACE_COMMANDS")
    if isinstance(_qx113_ws, set):
        _qx113_ws |= {"plans", "plan"}


async def _qx113_send(update, context, text, kb=None):
    with _cx113.suppress(Exception):
        await _qx112_send(update, context, text, kb)


async def _qx113_welcome(update, context, uid: int):
    st = {}
    with _cx113.suppress(Exception):
        st = _qx_access(int(uid)) or {}
    name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")
    await _qx113_send(update, context, _qx112_welcome_text(name, st), _qx112_welcome_kb())


# ─────────────────────────────────────────────────────────────────────────────
# 3) Hard gates (registered in the earliest handler groups)
# ─────────────────────────────────────────────────────────────────────────────
async def qx113_message_gate(update, context):
    if _qx113_owner_view(update, context):
        return
    message = getattr(update, "effective_message", None)
    if message is None:
        return
    chat_type = str(getattr(getattr(update, "effective_chat", None), "type", "") or "")
    if chat_type and chat_type != "private":
        return
    uid = _qx113_uid(update, context)
    if not uid:
        return
    with _cx113.suppress(Exception):
        if not (_qx_access(uid) or {}).get("ok"):
            return
    with _cx113.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))

    text = str(getattr(message, "text", "") or "")
    if text[:1] not in ("/", "."):
        return
    command = re.split(r"[\s@]", text[1:].strip(), 1)[0].lower()
    args_text = text[1:].strip()[len(command):].strip()
    tier = _qx113_tier(uid)

    if command in ("plans", "plan"):
        await _qx113_welcome(update, context, uid)
        raise ApplicationHandlerStop

    if tier == "":
        # trial user who has not chosen a plan yet
        if command in ("start", "menu", "guide") or (command == "help" and not args_text):
            await _qx113_welcome(update, context, uid)
            raise ApplicationHandlerStop
        return

    if tier != "student":
        return

    if command in ("start", "menu", "guide") or (command == "help" and not args_text):
        await _qx112_show_student_menu(update, context, uid)
        raise ApplicationHandlerStop

    if command in ("cmd", "commands"):
        await _qx113_send(update, context, QX112_STUDENT_COMMANDS_CARD, _qx112_back_kb())
        raise ApplicationHandlerStop

    if command in ("switchaccess", "switchacsess", "switchasccess", "sa"):
        await _qx113_send(update, context, _qx112_switch_text(uid), _qx112_switch_kb())
        raise ApplicationHandlerStop

    if command in QX113_STUDENT_COMMANDS:
        return

    await _qx113_send(
        update, context,
        "🎓 <b>Student workspace</b>\n"
        f"{QX112_ROW}\n"
        "এই command আপনার plan-এ নেই। এখানে quiz generate, inbox practice "
        "আর CSV export করা যায়।\n\n"
        "সব command দেখতে <code>/commands</code> · পূর্ণ access নিতে "
        "<code>/switchaccess</code>।",
        _qx112_student_menu_kb(),
    )
    raise ApplicationHandlerStop


async def qx113_callback_gate(update, context):
    query = getattr(update, "callback_query", None)
    if query is None or _qx113_owner_view(update, context):
        return
    uid = _qx113_uid(update, context)
    if not uid:
        return
    with _cx113.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))
    data = str(getattr(query, "data", "") or "")
    tier = _qx113_tier(uid)

    async def _edit(text, kb=None):
        with _cx113.suppress(Exception):
            await query.answer()
        with _cx113.suppress(Exception):
            await query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=kb,
                disable_web_page_preview=True,
            )

    if data.startswith("qx112:"):
        return  # section 112's own router handles these

    if tier == "":
        st = {}
        with _cx113.suppress(Exception):
            st = _qx_access(uid) or {}
        name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")
        await _edit(_qx112_welcome_text(name, st), _qx112_welcome_kb())
        raise ApplicationHandlerStop

    if tier != "student":
        return

    mapped = QX113_STUDENT_CALLBACK_MAP.get(data.split("?")[0])
    if mapped == "cmds":
        await _edit(QX112_STUDENT_COMMANDS_CARD, _qx112_back_kb())
        raise ApplicationHandlerStop
    if mapped == "menu":
        st = {}
        with _cx113.suppress(Exception):
            st = _qx_access(uid) or {}
        name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")
        await _edit(_qx112_student_menu_text(name, uid, st), _qx112_student_menu_kb())
        raise ApplicationHandlerStop

    if data.startswith(tuple(QX113_STUDENT_CALLBACK_OK)):
        return

    with _cx113.suppress(Exception):
        await query.answer("এই feature Master Access-এ পাওয়া যায়।", show_alert=True)
    raise ApplicationHandlerStop


# Section 112 router: add the "plans" action (back to the welcome card).
_qx113_prev_cb112 = globals().get("qx112_on_callback")


async def qx112_on_callback(update, context):  # noqa: F811
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "")
    if data == "qx112:plans":
        uid = _qx113_uid(update, context)
        with _cx113.suppress(Exception):
            _QX_ACTING_OWNER.set(int(uid))
        with _cx113.suppress(Exception):
            await query.answer()
        st = {}
        with _cx113.suppress(Exception):
            st = _qx_access(uid) or {}
        name = str(getattr(getattr(update, "effective_user", None), "full_name", "") or "")
        with _cx113.suppress(Exception):
            await query.edit_message_text(
                _qx112_welcome_text(name, st),
                parse_mode=ParseMode.HTML,
                reply_markup=_qx112_welcome_kb(),
                disable_web_page_preview=True,
            )
        raise ApplicationHandlerStop
    if callable(_qx113_prev_cb112):
        return await _qx113_prev_cb112(update, context)


globals()["qx112_on_callback"] = qx112_on_callback


# ─────────────────────────────────────────────────────────────────────────────
# 4) AI help — never stays stuck
# ─────────────────────────────────────────────────────────────────────────────
QX113_AI_FALLBACK = (
    "এখন উত্তরটি তৈরি করা গেল না। অনুগ্রহ করে আরেকবার চেষ্টা করুন — "
    "সাধারণত দ্বিতীয়বারেই কাজ হয়ে যায়।\n\n"
    "তারপরও না হলে অনুগ্রহ করে owner-এর সাথে যোগাযোগ করুন।"
)


def _qx113_router_call(prompt: str, seconds: int) -> str:
    router = globals().get("_gemini_text_router")
    if not callable(router):
        return ""
    try:
        out = router(prompt, timeout_seconds=seconds)
    except Exception:
        return ""
    if isinstance(out, (tuple, list)):
        out = out[0] if out else ""
    return str(out or "").strip()


async def _qx92_ai_help(question: str) -> str:  # noqa: F811
    prompt = ""
    with _cx113.suppress(Exception):
        prompt = _qx92_help_prompt(question)
    if not prompt:
        prompt = str(question or "").strip()
    if not prompt:
        return QX113_AI_FALLBACK

    loop = asyncio.get_running_loop()
    for seconds, budget in ((14, 17.0), (11, 14.0)):
        text = ""
        try:
            text = await asyncio.wait_for(
                loop.run_in_executor(_QX113_POOL, _qx113_router_call, prompt, seconds),
                timeout=budget,
            )
        except Exception as error:
            _qx_log.warning("[QUBIX-113] ai help attempt failed: %s", error)
            text = ""
        if text:
            with _cx113.suppress(Exception):
                clean = _qx92_sanitize_html(text)
                if clean:
                    return clean
            return str(text)[:3500]
    return QX113_AI_FALLBACK


globals()["_qx92_ai_help"] = _qx92_ai_help


# HTML-safe delivery: retry without parse_mode so a card never stays "thinking".
def _qx113_wrap_html_retry(name: str) -> None:
    original = getattr(_tg113.Bot, name, None)
    if not callable(original) or getattr(original, "_qx113", False):
        return

    async def wrapper(self, *args, **kwargs):
        try:
            return await original(self, *args, **kwargs)
        except Exception as error:
            message = str(error).lower()
            if "parse" not in message and "entity" not in message and "tag" not in message:
                raise
            retry = dict(kwargs)
            retry.pop("parse_mode", None)
            body = retry.get("text")
            if isinstance(body, str):
                retry["text"] = re.sub(r"<[^>]+>", "", body)
            return await original(self, *args, **retry)

    wrapper._qx113 = True  # type: ignore[attr-defined]
    setattr(_tg113.Bot, name, wrapper)


for _qx113_name in ("send_message", "edit_message_text"):
    with _cx113.suppress(Exception):
        _qx113_wrap_html_retry(_qx113_name)


# ─────────────────────────────────────────────────────────────────────────────
# 5) Wiring — earliest groups so no older handler can answer first
# ─────────────────────────────────────────────────────────────────────────────
_qx113_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx113_prev_build_app() if callable(_qx113_prev_build_app) else None
    if app is None:
        return app

    with _cx113.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx112_on_callback, pattern=r"^qx112:"), group=-30002
        )
    with _cx113.suppress(Exception):
        app.add_handler(CallbackQueryHandler(qx113_callback_gate), group=-30001)
    with _cx113.suppress(Exception):
        app.add_handler(MessageHandler(filters.ALL, qx113_message_gate), group=-30000)

    register = globals().get("_register_dual_command")
    for command in ("plans", "plan"):
        with _cx113.suppress(Exception):
            if callable(register):
                register(app, command, qx113_cmd_plans, group=-29999)
            else:
                app.add_handler(CommandHandler(command, qx113_cmd_plans), group=-29999)

    _qx_log.info("[QUBIX-113] tier lock + AI speed wired.")
    return app


async def qx113_cmd_plans(update, context):
    uid = _qx113_uid(update, context)
    if not uid:
        raise ApplicationHandlerStop
    with _cx113.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))
    await _qx113_welcome(update, context, uid)
    raise ApplicationHandlerStop


_qx_log.info("[SECTION 113] Qubix tier lock + AI speed loaded.")
