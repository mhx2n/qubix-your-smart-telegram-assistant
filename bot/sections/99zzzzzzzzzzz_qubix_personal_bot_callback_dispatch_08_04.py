# ──────────────────────────────────────────────────────────────────────────────
# Section 109 — final callback dispatcher for /addbot personal bots.
# Loaded last by bot/__main__.py; do not import directly.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx109
import inspect as _inspect109
import logging as _logging109


_qx109_logger = _logging109.getLogger("qubix.personal_callbacks")
_QX109_INTERNAL_CALLBACKS = {
    "_qx_child_menu_router",
    "_qx_child_gate",
    "qx91_callback_gate",
    "qx91_child_gate",
    "qx93_pre_gate",
    "qx93_child_pre_gate",
    "_qx107_tenant_menu_callback",
    "_qx109_dispatch_callback",
}


def _qx109_is_internal(handler):
    callback = getattr(handler, "callback", None)
    name = str(getattr(callback, "__name__", "") or "")
    return (
        not callable(callback)
        or name in _QX109_INTERNAL_CALLBACKS
        or "gate" in name.lower()
        or "shield" in name.lower()
        or "router" in name.lower()
        or "bridge" in name.lower()
    )


def _qx109_callback_candidates(update, tenant):
    """Yield real matching callback handlers from the finished main app.

    Personal bots clone a very large handler graph.  Several historical
    catch-all gates occupy an earlier PTB group and can stop dispatch before the
    button's real handler is reached.  Looking up the finished template here
    keeps every current/future callback namespace working without maintaining a
    fragile allow-list.
    """
    template = globals().get("_QX_MAIN_APP")
    if template is None:
        return
    callback_type = globals().get("CallbackQueryHandler")
    for group, handlers in sorted(getattr(template, "handlers", {}).items()):
        for handler in handlers:
            if callback_type is not None and not isinstance(handler, callback_type):
                continue
            if _qx109_is_internal(handler):
                continue
            callback = getattr(handler, "callback", None)
            callback_name = str(getattr(callback, "__name__", "") or "")
            # This handler deliberately matches qx93:ask for every tier and
            # returns without doing anything for non-Student users.  Exclude it
            # before dispatch so the generic qx93 handler remains reachable.
            if callback_name == "qx115_student_ask_callback":
                tier_getter = globals().get("_qx112_tier")
                try:
                    if not callable(tier_getter) or str(tier_getter(int(tenant)) or "") != "student":
                        continue
                except Exception:
                    continue
            # A pattern-less CallbackQueryHandler is normally an access gate,
            # telemetry observer or compatibility hook.  It may legitimately
            # return without handling the button.  Treating it as a concrete
            # destination swallowed every callback after section 114 added its
            # pattern-less bot-name observer.  Such handlers are already cloned
            # on the child app and still run in PTB's normal handler graph.
            pattern = getattr(handler, "pattern", None)
            if pattern is None:
                continue
            try:
                check = handler.check_update(update)
            except Exception:
                continue
            if _inspect109.isawaitable(check):
                # PTB CallbackQueryHandler checks are synchronous.  Never leave
                # an unexpected coroutine dangling or guess its result.
                with _cx109.suppress(Exception):
                    check.close()
                continue
            if check:
                yield group, handler, check


async def _qx109_dispatch_callback(update, context):
    query = getattr(update, "callback_query", None)
    if query is None:
        return

    app = context.application
    tenant = int(app.bot_data.get("qx_tenant_uid") or 0)
    actor = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    if not tenant:
        return
    if actor != tenant:
        with _cx109.suppress(Exception):
            await query.answer("This personal bot is private.", show_alert=True)
        raise ApplicationHandlerStop

    access = _qx_access(tenant)
    if not access.get("ok"):
        with _cx109.suppress(Exception):
            await query.answer("Your Qubix access has expired.", show_alert=True)
        raise ApplicationHandlerStop

    _QX_ACTING_OWNER.set(tenant)
    app.bot_data["qx_last_active"] = time.time()

    for group, handler, check in _qx109_callback_candidates(update, tenant) or ():
        try:
            await handler.handle_update(update, app, check, context)
            raise ApplicationHandlerStop
        except ApplicationHandlerStop:
            raise
        except Exception as error:
            _qx109_logger.exception(
                "personal callback failed uid=%s data=%r group=%s handler=%s",
                tenant,
                str(getattr(query, "data", "") or "")[:120],
                group,
                getattr(getattr(handler, "callback", None), "__name__", type(handler).__name__),
            )
            with _cx109.suppress(Exception):
                await query.answer(
                    "এই বাটনটি এখন কাজ করতে পারেনি। আবার চাপুন বা /menu দিন।",
                    show_alert=True,
                )
            raise ApplicationHandlerStop

    _qx109_logger.warning(
        "unhandled personal callback uid=%s data=%r",
        tenant,
        str(getattr(query, "data", "") or "")[:120],
    )
    with _cx109.suppress(Exception):
        await query.answer("এই control-টি refresh করতে /menu দিন।", show_alert=True)
    raise ApplicationHandlerStop


_qx109_previous_runner_start = QxRunner.start


async def _qx109_runner_start(self):
    ok_started, info = await _qx109_previous_runner_start(self)
    if ok_started and self.app is not None and not self.app.bot_data.get("qx109_dispatcher"):
        # Fallback for runners created by an older base start implementation.
        # Always choose a group earlier than every existing handler instead of
        # relying on a magic negative number that a future gate can overtake.
        dispatcher_group = min(
            getattr(self.app, "handlers", {}).keys(),
            default=0,
        ) - 1
        self.app.add_handler(
            CallbackQueryHandler(_qx109_dispatch_callback),
            group=dispatcher_group,
        )
        self.app.bot_data["qx109_dispatcher"] = True
        self.app.bot_data["qx109_dispatcher_group"] = dispatcher_group
        _qx109_logger.info("personal callback dispatcher active uid=%s", self.uid)
    return ok_started, info


QxRunner.start = _qx109_runner_start

with _cx109.suppress(Exception):
    logger.info("[QX109] universal personal-bot callback dispatcher active")

# ===== END SECTION 109 =====