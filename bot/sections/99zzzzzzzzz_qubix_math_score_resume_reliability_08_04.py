# ──────────────────────────────────────────────────────────────────────────────
# Section 107 — final math, score-template and stop/resume reliability layer.
# Loaded last by bot/__main__.py; do not import directly.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _async107
import contextlib as _cx107
import html as _html107
import json as _json107
import re as _re107
import time as _time107

import telegram  # noqa: F401  (section files run via exec; import explicitly)


def _qx107_log(message, level="info"):
    with _cx107.suppress(Exception):
        getattr(logger, level)("[QX107] %s", message)


# ═════════════════════════════════════════════════════════════════════════════
# 1) Math MCQs: validate and repair every provider path before buffering.
# ═════════════════════════════════════════════════════════════════════════════
_QX107_LABEL = _re107.compile(
    r"^\s*(?:[\(\[【]?\s*(?:[A-Ea-e]|ক|খ|গ|ঘ|ঙ|[১-৫]|[1-5])\s*[\)\]】\.．:：\-]\s*)+"
)
_QX107_PLACEHOLDER = _re107.compile(
    r"^(?:উপরের|নিচের)\s+প্রশ্নের\s+সঠিক\s+উত্তর\s+কোনটি\??$|"
    r"^which\s+(?:of\s+the\s+following\s+)?(?:answer|option)\s+is\s+correct\??$",
    _re107.I,
)
_QX107_MATH_SIGNAL = _re107.compile(
    r"\\(?:frac|sqrt|int|sum|prod|lim|sin|cos|tan|log|ln|theta|pi|circ)\b|"
    r"[√∫∑∏πθ∞±≤≥≠×÷∂²³°]|\^\s*[\{(]?[A-Za-z0-9]",
    _re107.I,
)


def _qx107_clean_math_text(value, *, option=False):
    text = str(value or "").replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n").strip()
    if option:
        text = _QX107_LABEL.sub("", text).strip()
    converter = globals().get("mathify_79")
    if callable(converter):
        with _cx107.suppress(Exception):
            text = str(converter(text) or text)
    text = _re107.sub(r"^\s*\$+|\$+\s*$", "", text)
    text = text.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    text = _re107.sub(r"(?<!\\)\\{2,}", r"\\", text)
    if option:
        text = _re107.sub(r"\s+", " ", text).strip(" \t\n")
    else:
        # Prefix + question is intentionally two lines.  The old global
        # whitespace collapse changed that newline to a space at send_poll.
        lines = [_re107.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line).strip()
    return text


def _qx107_answer(value, options):
    helper = globals().get("_answer_to_int_74")
    if callable(helper):
        with _cx107.suppress(Exception):
            answer = int(helper(value, options))
            if 1 <= answer <= len(options):
                return answer
    with _cx107.suppress(Exception):
        answer = int(value)
        if 1 <= answer <= len(options):
            return answer
        if 0 <= answer < len(options):
            return answer + 1
    return 0


def _qx107_normalise_mcq(item):
    if not isinstance(item, dict):
        return None
    question = _qx107_clean_math_text(
        item.get("question") or item.get("questions") or item.get("q") or item.get("stem")
    )
    if len(question) < 4 or _QX107_PLACEHOLDER.match(question):
        return None
    raw_options = item.get("options") or item.get("choices") or []
    if isinstance(raw_options, dict):
        raw_options = [raw_options[key] for key in sorted(raw_options)]
    if not isinstance(raw_options, list) or len(raw_options) < 2:
        raw_options = [item.get(f"option{i}") for i in range(1, 6)]
    options = []
    option_keys = set()
    for raw in raw_options:
        option = _qx107_clean_math_text(raw, option=True)
        key = _re107.sub(r"\s+", "", option).casefold()
        if not option or key in option_keys:
            continue
        option_keys.add(key)
        options.append(option[:100])
    if len(options) < 2:
        return None
    options = options[:5]
    answer_value = next((item.get(key) for key in (
        "answer", "correct", "correct_answer", "correctOption", "correct_option",
        "correct_option_text", "correct_option_id",
    ) if item.get(key) is not None), None)
    answer = _qx107_answer(answer_value, options)
    if not answer:
        return None
    explanation = _qx107_clean_math_text(
        item.get("explanation") or item.get("solution") or item.get("reason") or ""
    )[:200]
    return {
        "question": question[:300], "options": options, "answer": answer,
        "explanation": explanation,
    }


_qx107_previous_generate = globals().get("_generate_quizzes_from_ocr_sync")


def _generate_quizzes_from_ocr_sync(ocr_ctx, desired, user_id):  # noqa: F811
    desired = max(1, min(int(desired or 1), 200))
    source = str((ocr_ctx or {}).get("clean_text") or (ocr_ctx or {}).get("raw_markdown") or "").strip()
    generated = []
    last_error = None
    if callable(_qx107_previous_generate):
        try:
            generated = list(_qx107_previous_generate(ocr_ctx, desired, user_id) or [])
        except Exception as exc:
            last_error = exc

    result = []
    seen = set()

    def accept(rows):
        for row in rows or []:
            clean = _qx107_normalise_mcq(row)
            if not clean:
                continue
            signature = _re107.sub(r"\W+", "", clean["question"].casefold())
            if not signature or signature in seen:
                continue
            seen.add(signature)
            result.append(clean)
            if len(result) >= desired:
                break

    accept(generated)
    batcher = globals().get("_generate_batch_fast_74")
    rounds = 0
    while len(result) < desired and callable(batcher) and rounds < 8:
        rounds += 1
        need = min(6, desired - len(result))
        avoid = "\n".join("- " + row["question"] for row in result[-20:])
        instruction = (
            "MATH RELIABILITY RULES: output readable Unicode math only; never output $, \\(, \\), "
            "raw LaTeX commands, or A/B/ক/খ labels inside options. Every stem must be self-contained, "
            "not 'which answer is correct'. Recalculate the correct answer. Avoid these questions:\n" + avoid
        )
        try:
            accept(batcher(source, need, avoid_text=instruction) or [])
        except Exception as exc:
            last_error = exc
    if not result:
        raise RuntimeError(str(last_error or "Math quiz validation failed; no safe question was produced."))
    _qx107_log(f"validated quiz generation: requested={desired}, safe={len(result)}")
    return result[:desired]


if callable(_qx107_previous_generate):
    globals()["_generate_quizzes_from_ocr_sync"] = _generate_quizzes_from_ocr_sync


# Retire the old two-message math mode (a separate rich card followed by a poll
# whose stem only said “উপরের প্রশ্ন…”). If the card failed, users saw a useless
# placeholder poll. The final transport below now puts the repaired, complete
# mathematical question and options directly inside the Telegram quiz poll.
def _math_post_on_78():  # noqa: F811
    return False


globals()["_math_post_on_78"] = _math_post_on_78


# Final transport safety: no raw LaTeX delimiters or duplicated option labels
# can reach a Telegram poll, even if a legacy/manual buffer row contains them.
_qx107_previous_send_poll = telegram.Bot.send_poll


async def _qx107_send_poll(self, *args, **kwargs):
    merged = dict(kwargs)
    positional = list(args)
    question = merged.get("question", positional[1] if len(positional) > 1 else "")
    options = merged.get("options", positional[2] if len(positional) > 2 else [])
    clean_question = _qx107_clean_math_text(question)
    clean_options = [_qx107_clean_math_text(getattr(value, "text", value), option=True) for value in (options or [])]
    clean_options = [value[:100] for value in clean_options if value][:10]
    if len(clean_question) < 1 or len(clean_options) < 2:
        raise ValueError("Quiz rejected before delivery: incomplete question/options")
    if "question" in merged or len(positional) <= 1:
        merged["question"] = clean_question[:300]
    else:
        positional[1] = clean_question[:300]
    if "options" in merged or len(positional) <= 2:
        merged["options"] = clean_options
    else:
        positional[2] = clean_options
    return await _qx107_previous_send_poll(self, *positional, **merged)


telegram.Bot.send_poll = _qx107_send_poll


# Tenant callbacks are cloned from the finished main app, but older workspace
# gates only allow the original generation prefixes.  Keep every current rich
# control valid and install a final, earliest dispatcher for the menu shown in
# token-added bots.  This also repairs already-restored runners consistently.
with _cx107.suppress(Exception):
    _qx107_prefixes = tuple(globals().get("QX_WORKSPACE_CALLBACK_PREFIXES") or ())
    for _qx107_prefix in (
        "qx92:", "qx93:", "qx94:", "qx95:", "qx97:", "qx99:",
        "qx101:", "qx105:", "solve:", "genquiz:", "genm:", "eq:",
        "req:verify", "imgreact:", "tutorial:show", "master_dl_log:",
        "adv:tog:", "adv:del:", "adv:ref:",
    ):
        if _qx107_prefix not in _qx107_prefixes:
            _qx107_prefixes += (_qx107_prefix,)
    QX_WORKSPACE_CALLBACK_PREFIXES = _qx107_prefixes
    globals()["QX_WORKSPACE_CALLBACK_PREFIXES"] = QX_WORKSPACE_CALLBACK_PREFIXES

with _cx107.suppress(Exception):
    QX_WORKSPACE_COMMANDS |= {"scoreformat", "score", "scoreon", "scoreoff", "scon", "scoff"}


async def _qx107_tenant_menu_callback(update, context):
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "")
    if query is None or not data.startswith("qx93:"):
        return
    tenant = int(context.application.bot_data.get("qx_tenant_uid") or 0)
    actor = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not tenant or actor != tenant:
        with _cx107.suppress(Exception):
            await query.answer("This personal bot is private.", show_alert=True)
        raise ApplicationHandlerStop
    handler = globals().get("qx93_on_callback")
    if callable(handler):
        return await handler(update, context)
    with _cx107.suppress(Exception):
        await query.answer("Menu is refreshing—send /menu once.", show_alert=True)
    raise ApplicationHandlerStop


_qx107_previous_runner_start = QxRunner.start


async def _qx107_runner_start(self):
    ok_started, info = await _qx107_previous_runner_start(self)
    if ok_started and self.app is not None and not self.app.bot_data.get("qx107_callbacks"):
        self.app.bot_data["qx107_callbacks"] = True
        self.app.add_handler(
            CallbackQueryHandler(_qx107_tenant_menu_callback, pattern=r"^qx93:"),
            group=-6000,
        )
        _qx107_log(f"tenant callback bridge active uid={self.uid}")
    return ok_started, info


QxRunner.start = _qx107_runner_start


# ═════════════════════════════════════════════════════════════════════════════
# 2) Stop/resume: keep exact progress, restore full buffer for `keep`, total score.
# ═════════════════════════════════════════════════════════════════════════════
def _qx99_snapshot(uid):  # noqa: F811
    state = _QX99_ACTIVE.get(uid)
    if state is None or state.get("rows") is not None:
        return
    items = []
    with _cx107.suppress(Exception):
        items = list(buffer_list(uid, limit=MAX_BUFFERED_QUESTIONS) or [])
    state["items"] = items
    state["rows"] = [int(row_id) for row_id, _payload in items]
    state["total"] = len(items)


globals()["_qx99_snapshot"] = _qx99_snapshot


def _qx107_restore_rows(uid, rows):
    if not rows:
        return
    conn = db_connect()
    try:
        for row_id, payload in rows:
            conn.execute(
                "INSERT OR IGNORE INTO quiz_buffer(id,user_id,payload_json,created_at) VALUES (?,?,?,?)",
                (int(row_id), int(uid), _json107.dumps(payload, ensure_ascii=False), now_iso()),
            )
        conn.commit()
    finally:
        conn.close()


def _qx107_context_offset(context):
    with _cx107.suppress(Exception):
        return max(0, int(context.__dict__.get("_qx107_resume_offset") or 0))
    return 0


_qx107_previous_score = globals().get("_send_score_msg")


async def _send_score_msg(context, admin_id, chat_id, ok_count, first_post_msg_id, thread_id=None):  # noqa: F811
    total = int(ok_count or 0) + _qx107_context_offset(context)
    if callable(_qx107_previous_score):
        return await _qx107_previous_score(
            context, admin_id, chat_id, total, first_post_msg_id, thread_id=thread_id
        )


globals()["_send_score_msg"] = _send_score_msg


async def _qx107_delete_status(context, entries):
    for chat_id, message_id in list(entries or []):
        with _cx107.suppress(Exception):
            await context.bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))


def _qx107_status_add(uid, message):
    if message is None:
        return
    state = _QX99_ACTIVE.get(uid) or _QX99_PENDING.get(uid)
    if isinstance(state, dict):
        state.setdefault("status", []).append((message.chat_id, message.message_id))


async def _qx99_notify(update, context, text, keyboard=None):  # noqa: F811
    token = _QX99_BYPASS.set(True)
    try:
        sent = await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, parse_mode=_PM99.HTML,
            reply_markup=keyboard, disable_web_page_preview=True,
        )
        _qx107_status_add(_qx99_uid(update), sent)
        return sent
    finally:
        _QX99_BYPASS.reset(token)


globals()["_qx99_notify"] = _qx99_notify


def _qx99_shield(callback):  # noqa: F811
    if getattr(callback, "_qx107_shielded", False) or not callable(callback):
        return callback

    async def shielded(update, context, _cb=callback):
        uid = _qx99_uid(update)
        word = _qx99_cmd_word(update)
        run_mode = bool(uid) and word in _QX99_POST_CMDS
        token = None
        resumed = bool(context.__dict__.get("_qx99_resumed"))
        if run_mode:
            if not resumed:
                _QX99_STOP.discard(uid)
            _QX99_ACTIVE[uid] = {
                "sent": 0, "rows": None, "items": None, "status": [],
                "emoji": word in ("postemoji", "pe"),
            }
            token = _QX99_RUN_UID.set(uid)
        try:
            return await _cb(update, context)
        except _QX99Stop:
            state = _QX99_ACTIVE.get(uid) or {}
            sent = int(state.get("sent") or 0)
            items = list(state.get("items") or [])
            removed = items[:sent]
            with _cx107.suppress(Exception):
                if removed:
                    buffer_remove_ids(uid, [int(row[0]) for row in removed])
            args = list(getattr(context, "args", []) or [])
            keep = any(str(arg).strip().lower() == "keep" for arg in args)
            pending = {
                "update": update, "context": context, "args": args, "word": word,
                "ts": _time107.time(), "sent": sent, "total": len(items),
                "restore": removed if keep else [], "status": list(state.get("status") or []),
            }
            _QX99_PENDING[uid] = pending
            if token is not None:
                _QX99_RUN_UID.reset(token)
                token = None
            remaining = int(buffer_count(uid))
            halted = await _qx99_notify(update, context, _qx99_stop_card(sent, remaining))
            if halted is not None:
                pending.setdefault("status", []).append((halted.chat_id, halted.message_id))
            _qx107_log(f"run halted uid={uid} sent={sent} remaining={remaining} keep={keep}")
            raise _AHS99
        finally:
            if token is not None:
                _QX99_RUN_UID.reset(token)
            if run_mode:
                _QX99_ACTIVE.pop(uid, None)

    shielded._qx99_shielded = True
    shielded._qx99_shielded = True
    shielded._qx107_shielded = True
    with _cx107.suppress(Exception):
        shielded.__name__ = getattr(callback, "__name__", "shielded")
    return shielded


globals()["_qx99_shield"] = _qx99_shield


async def qx99_cmd_stopquiz(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    uid = _qx99_uid(update)
    if message is None or not _qx99_may_run(uid):
        raise _AHS99
    _QX99_STOP.add(uid)
    with _cx107.suppress(Exception):
        globals()["_stop_request_81"](uid)
    with _cx107.suppress(Exception):
        await message.delete()
    if uid not in _QX99_ACTIVE:
        sent = await _qx99_notify(
            update, context,
            ui_box_html("Stop Ready", "পরবর্তী active publish run থামানো হবে।\n▶️ বাতিল: <code>/resumequiz</code>", emoji="⏹"),
        )
        _QX99_PENDING.setdefault(uid, {"status": []}).setdefault("status", []).append(
            (sent.chat_id, sent.message_id)
        )
    raise _AHS99


async def qx99_cmd_resumequiz(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    uid = _qx99_uid(update)
    if message is None or not _qx99_may_run(uid):
        raise _AHS99
    _QX99_STOP.discard(uid)
    with _cx107.suppress(Exception):
        globals()["_stop_clear_81"](uid)
    job = _QX99_PENDING.pop(uid, None)
    with _cx107.suppress(Exception):
        await message.delete()
    if not job or int(buffer_count(uid)) <= 0:
        if job:
            await _qx107_delete_status(context, job.get("status"))
        raise _AHS99

    await _qx107_delete_status(context, job.get("status"))
    status = await _qx99_notify(
        update, context,
        ui_box_html(
            "Resuming Run",
            f"যেখান থেকে থেমেছিল, সেখান থেকে বাকি <b>{buffer_count(uid)}</b>টি quiz যাচ্ছে…",
            emoji="▶️",
        ),
    )
    old_update = job.get("update")
    old_context = job.get("context")
    callback = _QX99_RESUME_TARGETS.get(job.get("word") or "")
    if callable(callback) and old_update is not None and old_context is not None:
        old_context.args = list(job.get("args") or [])
        old_context.__dict__["_qx99_resumed"] = True
        old_context.__dict__["_qx107_resume_offset"] = int(job.get("sent") or 0)
        try:
            with _cx107.suppress(_AHS99):
                await callback(old_update, old_context)
        finally:
            with _cx107.suppress(Exception):
                _qx107_restore_rows(uid, job.get("restore") or [])
            old_context.__dict__.pop("_qx99_resumed", None)
            old_context.__dict__.pop("_qx107_resume_offset", None)
            await _qx107_delete_status(context, [(status.chat_id, status.message_id)])
    raise _AHS99


globals()["qx99_cmd_stopquiz"] = qx99_cmd_stopquiz
globals()["qx99_cmd_resumequiz"] = qx99_cmd_resumequiz
globals()["cmd_stopquiz_81"] = qx99_cmd_stopquiz
globals()["cmd_resumequiz_81"] = qx99_cmd_resumequiz


# ═════════════════════════════════════════════════════════════════════════════
# 3) Score format: reply-rich or convenient inline plain template.
# ═════════════════════════════════════════════════════════════════════════════
_qx107_previous_scoreformat = globals().get("qx106_cmd_scoreformat")


async def qx106_cmd_scoreformat(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    args = list(getattr(context, "args", None) or [])
    if message is None or user is None or not _qx106_allowed(user.id):
        raise _AHS106
    if not args:
        await message.reply_text(
            "🎨 <b>AI Score Card Studio</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "<b>AI দিয়ে বানান:</b>\n"
            "<code>/scoreformat 1 ai</code>\n"
            "<code>/scoreformat 1 ai নীল-সাদা professional result card</code>\n\n"
            "<b>নিজে customize করুন:</b>\n"
            "<code>/scoreformat 1 🏆 মোট {count}টি প্রশ্ন · {channel}</code>\n\n"
            "Placeholder: <code>{count}</code> · <code>{channel}</code>\n"
            "কোনো format save না করলে default score card-ই যাবে।\n"
            "Default ফেরাতে: <code>/scoreformat 1 reset</code>\n"
            "Channel number: <code>/listchannels</code>",
            parse_mode=_PM106.HTML,
        )
        raise _AHS106
    channel = _qx106_channel_for(user.id, args[0])
    if channel is None:
        await message.reply_text("⚠️ Channel পাওয়া যায়নি। /listchannels থেকে channel# নিন।")
        raise _AHS106
    reset = len(args) > 1 and str(args[1]).lower() in ("reset", "default", "off")
    ai_mode = len(args) > 1 and str(args[1]).lower() in ("ai", "generate", "make")
    reply = getattr(message, "reply_to_message", None)
    rich = ""
    if ai_mode:
        instructions = " ".join(str(arg) for arg in args[2:]).strip()
        status = await message.reply_text("✨ AI score card তৈরি হচ্ছে…")
        try:
            rich = await _async107.wait_for(
                _async107.to_thread(
                    _qx107_generate_score_template,
                    str(channel.title or ""),
                    instructions,
                ),
                timeout=45,
            )
        except Exception as exc:
            with _cx107.suppress(Exception):
                await status.edit_text(
                    "⚠️ AI score card তৈরি হয়নি। আবার চেষ্টা করুন।\n"
                    f"<code>{_html107.escape(str(exc)[:180])}</code>",
                    parse_mode=_PM106.HTML,
                )
            raise _AHS106
        with _cx107.suppress(Exception):
            await status.delete()
    elif len(args) > 1 and not reset:
        rich = _html107.escape(" ".join(str(arg) for arg in args[1:]).strip())
    if not reset and not rich:
        await message.reply_text(
            "⚠️ AI দিয়ে বানাতে <code>/scoreformat "
            f"{channel.id} ai</code>, অথবা command-এর পরেই custom text লিখুন।",
            parse_mode=_PM106.HTML,
        )
        raise _AHS106
    conn = db_connect()
    try:
        conn.execute("UPDATE channels SET score_template=? WHERE id=?", ("" if reset else rich[:3900], int(channel.id)))
        conn.commit()
    finally:
        conn.close()
    preview = _qx106_render_score("" if reset else rich, 25, channel.title)
    await message.reply_text(
        ("✅ <b>AI score format generated &amp; saved</b>\n" if ai_mode else
         "✅ <b>Score format saved</b>\n")
        + "━━━━━━━━━━━━━━━━━━━━\n" + preview
        + "\n━━━━━━━━━━━━━━━━━━━━\n"
          "পছন্দ না হলে নতুন instruction দিয়ে <code>/scoreformat "
        + str(channel.id) + " ai ...</code> দিন, অথবা সরাসরি custom text লিখুন।",
        parse_mode=_PM106.HTML, disable_web_page_preview=True,
    )
    raise _AHS106


globals()["qx106_cmd_scoreformat"] = qx106_cmd_scoreformat


def _qx107_generate_score_template(channel_title, instructions):
    prompt = (
        "Create one polished Telegram score/result card in concise Markdown. "
        "It is sent after a quiz set and replies to the first quiz. Use tasteful emoji, "
        "a strong heading, clean separators and short Bengali copy. The literal placeholder "
        "{count} MUST appear exactly once. The literal placeholder {channel} may appear once. "
        "Do not invent a numeric score, links, buttons, rankings, or user names. "
        "Return only the card, no code fence and no explanation.\n\n"
        f"CHANNEL: {str(channel_title or '')[:200]}\n"
        f"CUSTOMIZATION: {str(instructions or 'professional premium educational style')[:1000]}"
    )
    last_error = ""
    caller = globals().get("_adv_call_text")
    if callable(caller):
        try:
            result = caller(prompt, force_json=False, timeout=28)
            text = result[0] if isinstance(result, tuple) else result
            text = str(text or "").strip()
            if text:
                return _qx107_score_ai_to_html(text)
        except Exception as exc:
            last_error = str(exc)
    builtin = globals().get("call_gemini_text_rest")
    if callable(builtin):
        try:
            text = str(builtin(prompt, timeout_seconds=32, force_json=False) or "").strip()
            if text:
                return _qx107_score_ai_to_html(text)
        except Exception as exc:
            last_error = str(exc)
    raise RuntimeError(last_error or "No working AI provider is configured")


def _qx107_score_ai_to_html(text):
    clean = _re107.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", str(text or "").strip(), flags=_re107.I)
    if "{count}" not in clean:
        clean += "\n\nমোট প্রশ্ন: **{count}টি**"
    # Keep the AI card rich, using the same converter already proven for topic tails.
    converter = globals().get("_qx103_md_to_html") or globals().get("md_to_html_basic")
    if callable(converter):
        with _cx107.suppress(Exception):
            converted = str(converter(clean) or "").strip()
            if converted:
                return converted[:3900]
    return _html107.escape(clean)[:3900]


# The legacy direct channel publisher created its own plain score text and never
# reached the final rich/custom score function. Route it through the common
# publisher so normal, stopped and resumed runs all share one count and template.
@require_admin
async def cmd_post(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        return
    admin_id = int(user.id)
    args = list(getattr(context, "args", None) or [])
    if not args or not str(args[0]).isdigit():
        await safe_reply(update, usage_box(
            "post", "<channel#> [keep]",
            "Buffer-এর quiz channel-এ publish করুন; keep দিলে পুরো buffer অক্ষত থাকবে.",
        ))
        return
    channel = channel_get_by_id_for_user(admin_id, int(args[0]))
    if channel is None:
        await warn_html(update, "Channel Not Found", "<code>/listchannels</code> থেকে channel# নিন।")
        return
    items = list(buffer_list(admin_id, limit=MAX_BUFFERED_QUESTIONS) or [])
    if not items:
        await warn(update, "Buffer Empty", "Publish করার মতো quiz নেই।")
        return
    keep = any(str(arg).strip().lower() == "keep" for arg in args[1:])
    await info_html(
        update, "Posting to Channel",
        f"<code>{_html107.escape(str(channel.title))}</code>\n\n"
        f"মোট <code>{len(items)}</code>টি quiz publish হচ্ছে…",
    )
    ok_count, fail_count, first_id = await _post_buffer_to_chat(
        context, admin_id, int(channel.channel_chat_id), items,
        group_prefix=str(channel.prefix or ""),
        group_expl_link=str(channel.expl_link or ""),
    )
    total_ok = int(ok_count or 0) + _qx107_context_offset(context)
    if ok_count:
        await _send_score_msg(
            context, admin_id, int(channel.channel_chat_id), int(ok_count), first_id,
        )
    inc_admin_post(admin_id, int(ok_count or 0))
    if ok_count and not keep:
        successful_ids = [int(row_id) for row_id, _payload in items[:int(ok_count)]]
        buffer_remove_ids(admin_id, successful_ids)
    await ok(
        update, "Posting Complete",
        f"Posted: {total_ok}\nFailed: {int(fail_count or 0)}\n"
        f"Remaining in Buffer: {buffer_count(admin_id)}",
    )
    raise _AHS99


globals()["cmd_post"] = cmd_post


_qx107_previous_build = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx107_previous_build() if callable(_qx107_previous_build) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    if callable(register):
        with _cx107.suppress(Exception):
            register(app, "scoreformat", qx106_cmd_scoreformat, filters.ChatType.PRIVATE, group=-5000)
            post_handler = _qx99_shield(cmd_post)
            register(app, "post", post_handler, filters.ChatType.PRIVATE, group=-5000)
            register(app, "p", post_handler, filters.ChatType.PRIVATE, group=-5000)
            _QX99_RESUME_TARGETS["post"] = post_handler
            _QX99_RESUME_TARGETS["p"] = post_handler
    return app


_qx107_log("final reliability active: safe math MCQs, cumulative resume score, keep-buffer restore, clean statuses")

# ===== END SECTION 107 =====