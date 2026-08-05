# ──────────────────────────────────────────────────────────────────────────────
# Section (2026-08-05) — Qubix reliability pass:
#   1) "database is locked" → every SQLite connection is serialized through one
#      process-wide write lock with bounded retry/backoff.
#   2) Decimal options like "2.349" were losing their integer part because
#      several legacy cleaners treat "2." as a list label.
#   3) Generated quizzes must always carry 4 options (2/3-option items rejected
#      so the provider cascade keeps trying).
#   4) Math sources returned "Added: 0" because the Bengali-language guard
#      rejected formula-heavy stems. Math items are now accepted and the prompt
#      is math-aware.
#
# DO NOT import directly — exec'd in the shared namespace by bot/__main__.py.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cxQ
import re as _reQ
import sqlite3 as _sqQ
import threading as _thQ
import time as _tQ


def _logQ(message: str, level: str = "info") -> None:
    with _cxQ.suppress(Exception):
        getattr(logger, level)("[SQX] %s", message)  # type: ignore[name-defined]


# ── 1) SQLite: one global write lock + retry on lock/busy ─────────────────────

_QX_DB_LOCK = _thQ.RLock()
_QX_WRITE_RE = _reQ.compile(
    r"^\s*(insert|update|delete|replace|create|alter|drop|begin|commit|end|savepoint|"
    r"release|vacuum|reindex)\b",
    _reQ.IGNORECASE,
)
_QX_LOCK_WORDS = ("database is locked", "database table is locked", "database is busy")


def _qx_is_lock_error(error: Exception) -> bool:
    text = str(error or "").lower()
    return any(word in text for word in _QX_LOCK_WORDS)


def _qx_run(call, *, serialize: bool):
    delay = 0.05
    last = None
    for _ in range(12):
        try:
            if serialize:
                with _QX_DB_LOCK:
                    return call()
            return call()
        except _sqQ.OperationalError as error:
            if not _qx_is_lock_error(error):
                raise
            last = error
            _tQ.sleep(delay)
            delay = min(delay * 1.7, 1.0)
    raise last if last else RuntimeError("sqlite retry exhausted")


def _qx_needs_lock(sql) -> bool:
    return bool(_QX_WRITE_RE.match(str(sql or "")))


class _QxCursor:
    """Cursor proxy whose write transaction is owned by its connection proxy."""

    def __init__(self, cursor, connection):
        self._qx_cursor = cursor
        self._qx_connection = connection

    def __getattr__(self, name):
        return getattr(self._qx_cursor, name)

    def __iter__(self):
        return iter(self._qx_cursor)

    def execute(self, sql, *args, **kwargs):
        if _qx_needs_lock(sql):
            self._qx_connection._qx_begin_write()
        try:
            _qx_run(lambda: self._qx_cursor.execute(sql, *args, **kwargs), serialize=False)
        except Exception:
            self._qx_connection._qx_abort_write()
            raise
        return self

    def executemany(self, sql, *args, **kwargs):
        self._qx_connection._qx_begin_write()
        try:
            _qx_run(lambda: self._qx_cursor.executemany(sql, *args, **kwargs), serialize=False)
        except Exception:
            self._qx_connection._qx_abort_write()
            raise
        return self

    def executescript(self, sql, *args, **kwargs):
        self._qx_connection._qx_begin_write()
        try:
            _qx_run(lambda: self._qx_cursor.executescript(sql, *args, **kwargs), serialize=False)
        except Exception:
            self._qx_connection._qx_abort_write()
            raise
        return self


class _QxConnection:
    """Connection proxy so existing call sites keep working unchanged."""

    def __init__(self, conn):
        object.__setattr__(self, "_qx_conn", conn)
        object.__setattr__(self, "_qx_write_locked", False)

    def __getattr__(self, name):
        return getattr(self._qx_conn, name)

    def __setattr__(self, name, value):
        if name in ("_qx_conn", "_qx_write_locked"):
            object.__setattr__(self, name, value)
            return
        setattr(self._qx_conn, name, value)

    def _qx_begin_write(self):
        if self._qx_write_locked:
            return
        _QX_DB_LOCK.acquire()
        object.__setattr__(self, "_qx_write_locked", True)

    def _qx_release_write(self):
        if not self._qx_write_locked:
            return
        object.__setattr__(self, "_qx_write_locked", False)
        _QX_DB_LOCK.release()

    def _qx_abort_write(self):
        try:
            self._qx_conn.rollback()
        finally:
            self._qx_release_write()

    def cursor(self, *args, **kwargs):
        return _QxCursor(self._qx_conn.cursor(*args, **kwargs), self)

    def execute(self, sql, *args, **kwargs):
        if _qx_needs_lock(sql):
            self._qx_begin_write()
        try:
            return _qx_run(lambda: self._qx_conn.execute(sql, *args, **kwargs), serialize=False)
        except Exception:
            self._qx_abort_write()
            raise

    def executemany(self, sql, *args, **kwargs):
        self._qx_begin_write()
        try:
            return _qx_run(lambda: self._qx_conn.executemany(sql, *args, **kwargs), serialize=False)
        except Exception:
            self._qx_abort_write()
            raise

    def executescript(self, sql, *args, **kwargs):
        self._qx_begin_write()
        try:
            return _qx_run(lambda: self._qx_conn.executescript(sql, *args, **kwargs), serialize=False)
        except Exception:
            self._qx_abort_write()
            raise

    def commit(self):
        try:
            return _qx_run(self._qx_conn.commit, serialize=False)
        finally:
            self._qx_release_write()

    def rollback(self):
        try:
            return self._qx_conn.rollback()
        finally:
            self._qx_release_write()

    def close(self):
        try:
            if self._qx_write_locked:
                with _cxQ.suppress(Exception):
                    self._qx_conn.rollback()
            return self._qx_conn.close()
        finally:
            self._qx_release_write()

    def __enter__(self):
        self._qx_conn.__enter__()
        return self

    def __exit__(self, *exc):
        try:
            return self._qx_conn.__exit__(*exc)
        finally:
            self._qx_release_write()


_qx_prev_db_connect = globals().get("db_connect")

if callable(_qx_prev_db_connect):
    def db_connect():  # noqa: F811
        conn = _qx_prev_db_connect()
        if isinstance(conn, _QxConnection):
            return conn
        with _cxQ.suppress(Exception):
            # Keep SQLite's internal wait short.  The bounded Python retry loop
            # owns backoff; a 20s C-level wait can exhaust Telegram worker pools
            # and make every main/tenant command appear offline.
            conn.execute("PRAGMA busy_timeout=200;")
        with _cxQ.suppress(Exception):
            conn.execute("PRAGMA journal_mode=WAL;")
        with _cxQ.suppress(Exception):
            conn.execute("PRAGMA synchronous=NORMAL;")
        return _QxConnection(conn)

    globals()["db_connect"] = db_connect
    _logQ("sqlite write transactions serialized through commit (global lock + retry)")


# ── 2) Decimal-safe option/question cleaning ─────────────────────────────────

_QX_DEC_RE = _reQ.compile(r"^\s*\(?\s*[-−+]?\s*[0-9০-৯]+\s*[.．]\s*[0-9০-৯]")
_QX_LABEL_RE = _reQ.compile(r"^\(?\s*[-−+]?\s*[0-9০-৯]+\s*[.．)]\s*")


def _qx_decimal_guard(fn):
    """Undo label-stripping when the text actually starts with a decimal."""

    def inner(text, *args, **kwargs):
        out = fn(text, *args, **kwargs)
        try:
            source = str(text or "")
            if not _QX_DEC_RE.match(source):
                return out
            result = str(out or "")
            if _QX_DEC_RE.match(result):
                return out
            head = source.strip()
            match = _QX_LABEL_RE.match(head)
            if match and result.strip() == head[match.end():].strip():
                return head
        except Exception:
            return out
        return out

    inner.__name__ = getattr(fn, "__name__", "cleaner")
    return inner


for _qx_name in ("clean_common", "clean_option_text", "_strip_leading_serials",
                 "_strip_leading_quiz_noise"):
    _qx_fn = globals().get(_qx_name)
    if callable(_qx_fn) and not getattr(_qx_fn, "_qx_dec_guarded", False):
        _qx_wrapped = _qx_decimal_guard(_qx_fn)
        _qx_wrapped._qx_dec_guarded = True  # type: ignore[attr-defined]
        globals()[_qx_name] = _qx_wrapped
        _logQ(f"decimal guard installed on {_qx_name}")


# ── 3 & 4) Generation quality: 4 options always, math sources accepted ───────

_QX_BN_RE = _reQ.compile(r"[\u0980-\u09FF]")
_QX_MATH_RE = _reQ.compile(
    r"(\$|\\frac|\\int|\\sqrt|\\sin|\\cos|\\tan|\\lim|\\log|√|∫|∑|π|θ|≤|≥|≠|∞|"
    r"[0-9A-Za-z\)\}]\s*\^\s*[0-9A-Za-z\{\-]|\d\s*/\s*\d|[a-zA-Z]\s*=\s*[-0-9])"
)


def _qx_is_mathy(text: str) -> bool:
    return bool(_QX_MATH_RE.search(str(text or "")))


_qx_base_normalise = globals().get("_old_normalise_88") or globals().get("_normalise_mcq_74")

if callable(_qx_base_normalise):
    def _normalise_mcq_74(item):  # noqa: F811
        row = _qx_base_normalise(item)
        if not isinstance(row, dict):
            return None
        options = [str(o or "").strip() for o in (row.get("options") or []) if str(o or "").strip()]
        # Never store a 2 or 3-option MCQ: returning None keeps the provider
        # cascade running instead of persisting a broken quiz.
        if len(options) < 4:
            return None
        row["options"] = options[:4] if len(options) > 4 else options
        answer = int(row.get("answer") or 1)
        if not (1 <= answer <= len(row["options"])):
            return None

        question = str(row.get("question") or "")
        explanation = str(row.get("explanation") or "")
        blob = question + " " + " ".join(row["options"]) + " " + explanation
        lang = "bn"
        with _cxQ.suppress(Exception):
            lang = _generation_lang_88(question)  # type: ignore[name-defined]

        # Math stems are mostly symbols; the old strict Bengali counter rejected
        # every valid item and produced "Added: 0" for math sources.
        if _qx_is_mathy(blob):
            return row
        if lang == "bn" and len(_QX_BN_RE.findall(blob)) < 3:
            return None
        if lang == "en" and len(_QX_BN_RE.findall(question + " " + explanation)) > 5:
            return None
        return row

    globals()["_normalise_mcq_74"] = _normalise_mcq_74
    _logQ("MCQ normaliser: 4-option rule + math-safe language check")


_qx_prev_prompt = globals().get("_make_fast_new_mcq_prompt_74")

if callable(_qx_prev_prompt):
    def _make_fast_new_mcq_prompt_74(source_text, n, *, easy=0, medium=0, hard=0,
                                     avoid_text=""):  # noqa: F811
        base = str(_qx_prev_prompt(source_text, n, easy=easy, medium=medium, hard=hard,
                                   avoid_text=avoid_text) or "")
        extra = (
            "\n\nHARD OUTPUT RULES:\n"
            "• Every item MUST contain exactly 4 options — never 2 or 3.\n"
            "• Write numeric options completely (e.g. 2.349, not .349 or 349); "
            "never drop the integer part of a decimal.\n"
            "• Never prefix an option with a number, letter or bullet label.\n"
        )
        if _qx_is_mathy(str(source_text or "")):
            extra += (
                "• This source is MATHEMATICS. Build solvable calculation MCQs "
                "(limits, derivatives, integration, trigonometry, algebra) on the same "
                "topics. Write formulas in readable Unicode (√, ², ₁, π, θ) or simple "
                "LaTeX inside $...$, keep each stem short and self-contained, and give a "
                "one-line numeric-step explanation. Output valid JSON even if the source "
                "text is partly unclear — infer the topic and still return the requested "
                "number of items.\n"
            )
        return base + extra

    globals()["_make_fast_new_mcq_prompt_74"] = _make_fast_new_mcq_prompt_74
    _logQ("fast MCQ prompt hardened (4 options, decimals, math topics)")


_logQ("reliability pass loaded")
