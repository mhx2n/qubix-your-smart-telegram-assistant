# ──────────────────────────────────────────────────────────────────────────────
# Section: 105_qubix_mongo_durability_08_04
# Purpose (owner-reported bugs):
#   1. "Backup Now" said saved, but nothing really landed in the cloud →
#      full-mirror backup (wipe collection, insert sanitised docs) + read-back
#      verification, so the reported count is the real cloud count.
#   2. After a redeploy the bot showed 0 rows and everything had to be added
#      again → per-table auto-restore on startup (any table that is empty
#      locally but has cloud docs is restored, no global "users" gate).
#   3. Owner can now wipe the mirror and start fresh: /qpurge (cloud only or
#      cloud + local), with a confirmation step.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx105
import datetime as _dt105

from telegram import InlineKeyboardButton as _IKB105, InlineKeyboardMarkup as _IKM105
from telegram.constants import ParseMode as _PM105
from telegram.ext import ApplicationHandlerStop as _AHS105


def _qx105_log(msg, level="info"):
    with _cx105.suppress(Exception):
        getattr(logger, level)("[QX105] %s", msg)


def _qx105_tables():
    """[(sqlite_table, mongo_collection, label)] — mirror scope."""
    scoped = globals().get("QX100_BACKUP_TABLES")
    if scoped:
        return [(str(t[0]), str(t[1]), str(t[3])) for t in scoped]
    plain = globals().get("_MONGO_TABLES") or []
    return [(str(t[0]), str(t[1]), str(t[0])) for t in plain]


# ═════════════════════════════════════════════════════════════════════════════
# 1) SQLite helpers
# ═════════════════════════════════════════════════════════════════════════════
def _qx105_columns(table: str):
    cols = []
    with _cx105.suppress(Exception):
        conn = db_connect()
        try:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info([{table}])")
            cols = [str(r[1]) for r in cur.fetchall()]
        finally:
            with _cx105.suppress(Exception):
                conn.close()
    return cols


def _qx105_rows(table: str):
    rows = []
    with _cx105.suppress(Exception):
        conn = db_connect()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM [{table}]")  # noqa: S608
            names = [d[0] for d in cur.description]
            rows = [dict(zip(names, r)) for r in cur.fetchall()]
        finally:
            with _cx105.suppress(Exception):
                conn.close()
    return rows


def _qx105_count(table: str) -> int:
    counter = globals().get("_qx99_local_count")
    if callable(counter):
        with _cx105.suppress(Exception):
            return int(counter(table))
    with _cx105.suppress(Exception):
        conn = db_connect()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM [{table}]")  # noqa: S608
            return int(cur.fetchone()[0])
        finally:
            with _cx105.suppress(Exception):
                conn.close()
    return -1


def _qx105_bson(value):
    """Make any SQLite value BSON-safe."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        with _cx105.suppress(Exception):
            return bytes(value).decode("utf-8", "replace")
        return ""
    return str(value)


def _qx105_doc(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        name = str(key)
        if name == "_id":
            name = "sqlite_id"
        out[name] = _qx105_bson(value)
    return out


def _qx105_client():
    factory = globals().get("_qx99_client")
    if callable(factory):
        return factory()
    return None


def _qx105_dbname() -> str:
    return str(globals().get("QX99_MONGO_DB") or "qubix_db")


# ═════════════════════════════════════════════════════════════════════════════
# 2) Truthful full-mirror backup (with read-back verification)
# ═════════════════════════════════════════════════════════════════════════════
def mongo_backup_now(requester: str = "auto"):  # noqa: F811
    client = _qx105_client()
    if client is None:
        return 0, 0, "MongoDB not configured or unreachable."

    stamp = _dt105.datetime.utcnow().isoformat() + "Z"
    ok_n = fail_n = 0
    details = []
    try:
        db = client[_qx105_dbname()]
        for table, coll_name, label in _qx105_tables():
            try:
                if not _qx105_columns(table):
                    details.append(f"- {label}: table missing (skipped)")
                    continue
                rows = _qx105_rows(table)
                coll = db[coll_name]
                coll.delete_many({})
                if rows:
                    coll.insert_many([_qx105_doc(r) for r in rows], ordered=False)
                stored = int(coll.count_documents({}))
                if stored == len(rows):
                    ok_n += 1
                    details.append(f"- {label}: {stored} saved")
                else:
                    fail_n += 1
                    details.append(f"- {label}: {stored}/{len(rows)} mismatch")
            except Exception as error:  # noqa: BLE001
                fail_n += 1
                details.append(f"- {label}: {error}")
                _qx105_log(f"backup failed for {table}: {error}", "warning")

        with _cx105.suppress(Exception):
            db["_meta"].replace_one(
                {"_id": "backup_info"},
                {
                    "_id": "backup_info",
                    "last_backup_at": stamp,
                    "requester": str(requester),
                    "tables_ok": ok_n,
                    "tables_failed": fail_n,
                },
                upsert=True,
            )
    finally:
        with _cx105.suppress(Exception):
            client.close()

    summary = f"Backup {stamp}\n" + "\n".join(details)
    _qx105_log(f"backup by {requester}: ok={ok_n} fail={fail_n}")
    return ok_n, fail_n, summary


# ═════════════════════════════════════════════════════════════════════════════
# 3) Schema-safe restore
# ═════════════════════════════════════════════════════════════════════════════
def _qx105_restore_table(conn, db, table: str, coll_name: str):
    """Return (restored_rows, error_or_None)."""
    local_cols = _qx105_columns(table)
    if not local_cols:
        return 0, "table missing locally"
    docs = list(db[coll_name].find({}, {"_id": 0}))
    if not docs:
        return 0, None
    allowed = set(local_cols)
    written = 0
    for doc in docs:
        payload = {k: v for k, v in doc.items() if k in allowed}
        if "sqlite_id" in doc and "id" in allowed and "id" not in payload:
            payload["id"] = doc["sqlite_id"]
        if not payload:
            continue
        names = list(payload.keys())
        sql = (
            f"INSERT OR REPLACE INTO [{table}] "  # noqa: S608
            f"({', '.join('[' + c + ']' for c in names)}) "
            f"VALUES ({', '.join('?' for _ in names)})"
        )
        try:
            conn.execute(sql, tuple(payload[c] for c in names))
            written += 1
        except Exception:  # noqa: BLE001
            continue
    conn.commit()
    return written, None


def mongo_restore_now():  # noqa: F811
    client = _qx105_client()
    if client is None:
        return 0, 0, "MongoDB not configured or unreachable."

    ok_n = fail_n = 0
    details = []
    conn = None
    try:
        db = client[_qx105_dbname()]
        conn = db_connect()
        for table, coll_name, label in _qx105_tables():
            try:
                written, problem = _qx105_restore_table(conn, db, table, coll_name)
                if problem:
                    fail_n += 1
                    details.append(f"- {label}: {problem}")
                elif written:
                    ok_n += 1
                    details.append(f"- {label}: {written} restored")
                else:
                    details.append(f"- {label}: nothing in cloud")
            except Exception as error:  # noqa: BLE001
                fail_n += 1
                details.append(f"- {label}: {error}")
                _qx105_log(f"restore failed for {table}: {error}", "warning")
    finally:
        if conn is not None:
            with _cx105.suppress(Exception):
                conn.close()
        with _cx105.suppress(Exception):
            client.close()

    stamp = _dt105.datetime.utcnow().isoformat() + "Z"
    summary = f"Restore {stamp}\n" + "\n".join(details)
    _qx105_log(f"restore done: ok={ok_n} fail={fail_n}")
    return ok_n, fail_n, summary


# ═════════════════════════════════════════════════════════════════════════════
# 4) Per-table auto-restore on startup (fixes "everything is 0 after redeploy")
# ═════════════════════════════════════════════════════════════════════════════
def _try_restore_on_startup() -> None:  # noqa: F811
    if not str(globals().get("QX99_MONGO_URI") or ""):
        _qx105_log("MONGODB_URI not set — startup restore skipped")
        return
    client = _qx105_client()
    if client is None:
        _qx105_log("cloud unreachable — startup restore skipped", "warning")
        return

    restored_total = 0
    conn = None
    try:
        db = client[_qx105_dbname()]
        conn = db_connect()
        for table, coll_name, label in _qx105_tables():
            try:
                local = _qx105_count(table)
                if local > 0:
                    continue  # live data already present — never overwrite
                remote = 0
                with _cx105.suppress(Exception):
                    remote = int(db[coll_name].count_documents({}))
                if remote <= 0:
                    continue
                written, problem = _qx105_restore_table(conn, db, table, coll_name)
                if problem:
                    _qx105_log(f"startup restore {label}: {problem}", "warning")
                    continue
                restored_total += written
                _qx105_log(f"startup restore {label}: {written} rows")
            except Exception as error:  # noqa: BLE001
                _qx105_log(f"startup restore {label} failed: {error}", "warning")
    finally:
        if conn is not None:
            with _cx105.suppress(Exception):
                conn.close()
        with _cx105.suppress(Exception):
            client.close()

    _qx105_log(f"startup restore complete — {restored_total} row(s) recovered")


# ═════════════════════════════════════════════════════════════════════════════
# 5) Purge — owner wipes the mirror and starts fresh
# ═════════════════════════════════════════════════════════════════════════════
QX105_PURGE_PROTECT = {"users"}  # local wipe never removes user accounts


def _qx105_purge(scope: str):
    """scope: 'cloud' | 'all'. Returns (cloud_removed, local_removed, report)."""
    cloud_removed = local_removed = 0
    lines = []
    client = _qx105_client()
    if client is not None:
        try:
            db = client[_qx105_dbname()]
            for _table, coll_name, label in _qx105_tables():
                with _cx105.suppress(Exception):
                    result = db[coll_name].delete_many({})
                    removed = int(getattr(result, "deleted_count", 0))
                    cloud_removed += removed
                    lines.append(f"- {label}: cloud {removed} মুছে ফেলা হয়েছে")
            with _cx105.suppress(Exception):
                db["_meta"].delete_many({})
        finally:
            with _cx105.suppress(Exception):
                client.close()
    else:
        lines.append("- Cloud: সংযোগ করা যায়নি")

    if scope == "all":
        conn = None
        with _cx105.suppress(Exception):
            conn = db_connect()
        if conn is not None:
            try:
                for table, _coll, label in _qx105_tables():
                    if table in QX105_PURGE_PROTECT or not _qx105_columns(table):
                        continue
                    with _cx105.suppress(Exception):
                        before = max(0, _qx105_count(table))
                        conn.execute(f"DELETE FROM [{table}]")  # noqa: S608
                        local_removed += before
                        lines.append(f"- {label}: local {before} মুছে ফেলা হয়েছে")
                with _cx105.suppress(Exception):
                    conn.commit()
            finally:
                with _cx105.suppress(Exception):
                    conn.close()

    return cloud_removed, local_removed, "\n".join(lines)


def _qx105_confirm_kb():
    return _IKM105([
        [_IKB105("☁️ শুধু Cloud মুছুন", callback_data="qx105:pc")],
        [_IKB105("🧨 Cloud + Local মুছুন", callback_data="qx105:pa")],
        [_IKB105("✖ বাতিল", callback_data="qx105:cl")],
    ])


def _qx105_box(title, body, emoji="🧹"):
    box = globals().get("ui_box_html")
    if callable(box):
        return box(title, body, emoji=emoji)
    return f"{emoji} <b>{title}</b>\n\n{body}"


async def qx105_cmd_purge(update, context):
    message = getattr(update, "effective_message", None)
    uid = globals()["_qx99_uid"](update)
    if message is None or not globals()["_qx99_is_owner"](uid):
        raise _AHS105
    token = globals()["_QX99_BYPASS"].set(True)
    try:
        with _cx105.suppress(Exception):
            await message.delete()
        body = (
            "⚠️ এই কাজটি <b>ফিরিয়ে আনা যায় না</b>।\n\n"
            "☁️ <b>শুধু Cloud</b> — MongoDB মিরর খালি হবে, বটের local ডাটা থাকবে।\n"
            "🧨 <b>Cloud + Local</b> — মিরর ও local access / token / channel / "
            "group / topic সব মুছে একদম নতুন করে শুরু হবে "
            "(user account তালিকা সুরক্ষিত থাকবে)।"
        )
        with _cx105.suppress(Exception):
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=_qx105_box("Database Purge", body)[:4000],
                parse_mode=_PM105.HTML,
                reply_markup=_qx105_confirm_kb(),
                disable_web_page_preview=True,
            )
    finally:
        globals()["_QX99_BYPASS"].reset(token)
    raise _AHS105


async def qx105_cb_purge(update, context):
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    uid = 0
    with _cx105.suppress(Exception):
        uid = int(query.from_user.id)
    if not globals()["_qx99_is_owner"](uid):
        with _cx105.suppress(Exception):
            await query.answer("Owner only.", show_alert=True)
        raise _AHS105

    action = (query.data or "").split(":")[-1]
    token = globals()["_QX99_BYPASS"].set(True)
    try:
        if action == "cl":
            with _cx105.suppress(Exception):
                await query.answer("বাতিল")
            with _cx105.suppress(Exception):
                await query.message.delete()
            raise _AHS105

        if action == "pg":
            with _cx105.suppress(Exception):
                await query.answer()
            with _cx105.suppress(Exception):
                await query.edit_message_text(
                    _qx105_box(
                        "Database Purge",
                        "⚠️ কোনটি মুছতে চান তা বেছে নিন।",
                    )[:4000],
                    parse_mode=_PM105.HTML, reply_markup=_qx105_confirm_kb(),
                )
            raise _AHS105

        scope = "all" if action == "pa" else "cloud"
        with _cx105.suppress(Exception):
            await query.answer("মুছে ফেলা হচ্ছে…")
        loop = asyncio.get_event_loop()
        cloud_n, local_n, report = await loop.run_in_executor(
            None, lambda: _qx105_purge(scope)
        )
        body = (
            f"☁️ Cloud rows removed: <b>{cloud_n}</b>\n"
            f"💾 Local rows removed: <b>{local_n}</b>\n\n"
            f"<pre>{h(report[:1200])}</pre>\n"
            "এখন <code>/qbackup</code> → <b>Backup Now</b> দিয়ে নতুন করে "
            "মিরর শুরু করতে পারেন।"
        )
        with _cx105.suppress(Exception):
            await query.edit_message_text(
                _qx105_box("Purge Complete", body, emoji="✅")[:4000],
                parse_mode=_PM105.HTML,
                reply_markup=globals()["_qx99_console_kb"](),
                disable_web_page_preview=True,
            )
    finally:
        globals()["_QX99_BYPASS"].reset(token)
    raise _AHS105


# Purge button inside the backup console keyboard.
def _qx99_console_kb():  # noqa: F811
    return _IKM105([
        [_IKB105("🗄 Backup Now", callback_data="qx99:bk"),
         _IKB105("🔄 Refresh", callback_data="qx99:rf")],
        [_IKB105("⬇️ Restore from Cloud", callback_data="qx99:rs")],
        [_IKB105("🧹 Purge Database", callback_data="qx105:pg")],
        [_IKB105("✖ Close", callback_data="qx99:cl")],
    ])


globals()["_qx99_console_kb"] = _qx99_console_kb


# ═════════════════════════════════════════════════════════════════════════════
# 6) Wiring
# ═════════════════════════════════════════════════════════════════════════════
_qx105_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx105_prev_build_app() if callable(_qx105_prev_build_app) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    for name in ("qpurge", "qreset"):
        with _cx105.suppress(Exception):
            if callable(register):
                register(app, name, qx105_cmd_purge, group=-1061)
            else:
                app.add_handler(CommandHandler(name, qx105_cmd_purge), group=-1061)
    with _cx105.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx105_cb_purge, pattern=r"^qx105:"), group=-1061
        )
    _qx105_log("durability layer wired (/qpurge, verified backup, auto-restore)")
    return app


with _cx105.suppress(Exception):
    _menu105 = list(globals().get("QX94_OWNER_MENU_COMMANDS") or [])
    if _menu105 and not any(n == "qpurge" for n, _ in _menu105):
        _menu105.append(("qpurge", "Database purge / নতুন শুরু"))
        globals()["QX94_OWNER_MENU_COMMANDS"] = _menu105[:99]

with _cx105.suppress(Exception):
    if "/qpurge" not in QX94_OWNER_CARD:
        globals()["QX94_OWNER_CARD"] = QX94_OWNER_CARD + (
            "\n<code>/qpurge</code> — cloud (বা cloud + local) ডাটা মুছে "
            "একদম নতুন করে শুরু করুন।"
        )

_qx105_log("section 105 loaded (verified mirror, per-table startup restore, purge)")
