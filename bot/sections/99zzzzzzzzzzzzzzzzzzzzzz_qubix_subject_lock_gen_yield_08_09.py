# ──────────────────────────────────────────────────────────────────────────────
# Section (2026-08-09) — Subject lock + generation yield/latency pass
#
#   1) Physics/Chemistry sources were producing calculus (integration /
#      differentiation) MCQs.  Root cause: the previous overlay treated any
#      formula-ish source (√, ^, "x = 2", fractions) as MATHEMATICS and told the
#      model to build limit/derivative/integration questions.  That instruction
#      is now removed and replaced with a strict SUBJECT LOCK: questions must
#      stay inside the subject(s) actually present in the source.
#   2) ".gen <n>" returned far fewer items than requested (10/28 of 100).
#      The old loop stopped on the first empty batch.  It now uses bigger
#      batches, tolerates a few empty rounds, and keeps going until the target
#      is reached or the bounded round budget ends.
#   3) Math/formula generation took several minutes for a handful of items.
#      Round budget and per-round need are now bounded so worst-case latency
#      stays predictable.
#
# DO NOT import directly — exec'd in the shared namespace by bot/__main__.py.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cxS
import re as _reS


def _logS(message: str, level: str = "info") -> None:
    with _cxS.suppress(Exception):
        getattr(logger, level)("[SUBJ] %s", message)  # type: ignore[name-defined]


# ── 1) Subject lock ───────────────────────────────────────────────────────────

# The exact paragraph injected by the previous overlay.  Removing it by marker
# keeps this section independent of that section's wording drift.
_S_MATH_PUSH_MARKER = "This source is MATHEMATICS."

_S_SUBJECT_HINTS = (
    ("পদার্থবিজ্ঞান / Physics", (
        "মহাকর্ষ", "বেগ", "ত্বরণ", "তরঙ্গ", "ফোটন", "কক্ষ", "তাপমাত্রা", "দোলন",
        "শক্তি", "ভর", "বল", "গ্যাস", "escape", "rms", "eV", "rad/s", "photon",
        "velocity", "gravitation", "thermodynam", "carnot", "bohr",
    )),
    ("রসায়ন / Chemistry", (
        "মৌল", "বিকিরণ", "পরমাণু", "অণু", "যোজনী", "বিক্রিয়া", "অক্সি", "অ্যাসিড",
        "মোল", "isotope", "orbital", "valence", "reaction", "acid", "base",
    )),
    ("জীববিজ্ঞান / Biology", (
        "কোষ", "রক্ত", "জিন", "উদ্ভিদ", "প্রাণী", "এনজাইম", "cell", "enzyme",
        "protein", "dna", "blood",
    )),
    ("গণিত / Mathematics", (
        "সমাকলন", "অন্তরীকরণ", "লিমিট", "ত্রিকোণমিতি", "ম্যাট্রিক্স", "integrat",
        "different", "\\lim", "lim_", "\\int", "∫", "derivative", "matrix",
        "trigonometr",
    )),
    ("উচ্চতর গণিত-বহির্ভূত সাধারণ জ্ঞান / General Knowledge", (
        "সাল", "যুদ্ধ", "রাজধানী", "সংবিধান", "নদী", "capital", "war", "treaty",
    )),
)


def _s_detect_subjects(text: str) -> list:
    blob = str(text or "").lower()
    found = []
    for label, keys in _S_SUBJECT_HINTS:
        for key in keys:
            if key.lower() in blob:
                found.append(label)
                break
    return found


def _s_subject_lock_block(source_text: str) -> str:
    subjects = _s_detect_subjects(source_text)
    if subjects:
        listed = " · ".join(subjects)
        scope = (
            f"• SUBJECT LOCK — এই source-এর বিষয়: {listed}. প্রতিটি প্রশ্ন কেবল এই "
            "বিষয়ের ভেতরের topic/concept থেকে হবে।\n"
        )
    else:
        scope = (
            "• SUBJECT LOCK — source-এ যে বিষয়ের প্রশ্ন আছে, প্রতিটি নতুন প্রশ্ন ঠিক "
            "সেই বিষয়ের ভেতরেই থাকবে।\n"
        )
    return (
        "\n\nSTRICT TOPIC SCOPE (must obey):\n"
        + scope
        + "• source-এ না থাকলে calculus (integration, differentiation, limit), "
        "matrix, ত্রিকোণমিতিক identity বা অন্য কোনো গণিতের প্রশ্ন একটিও তৈরি করবে না।\n"
        "• কোনো নতুন subject, chapter বা প্রশ্নধরন নিজে থেকে যোগ করবে না; "
        "source-এর প্রতিটি প্রশ্ন/সমাধানকে ভিত্তি ধরে সেই একই chapter-এর ভেতরে "
        "নতুন exam-quality প্রশ্ন বানাবে।\n"
        "• সংখ্যা/সূত্র থাকলেই সেটাকে গণিত ধরবে না — পদার্থ/রসায়নের সংখ্যাভিত্তিক "
        "প্রশ্ন সেই বিষয়েরই প্রশ্ন হিসেবেই লিখবে।\n"
        "• প্রতিটি item-এ ঠিক ৪টি option, সম্পূর্ণ দশমিক সংখ্যা (2.349, কখনো .349 নয়), "
        "কোনো option-এর আগে number/letter label নয়।\n"
    )


_s_prev_prompt = globals().get("_make_fast_new_mcq_prompt_74")

if callable(_s_prev_prompt):
    def _make_fast_new_mcq_prompt_74(source_text, n, *, easy=0, medium=0, hard=0,
                                     avoid_text=""):  # noqa: F811
        base = str(_s_prev_prompt(source_text, n, easy=easy, medium=medium, hard=hard,
                                  avoid_text=avoid_text) or "")
        # Drop the legacy "build calculus MCQs" push if any earlier overlay added it.
        if _S_MATH_PUSH_MARKER in base:
            lines = [ln for ln in base.splitlines()
                     if _S_MATH_PUSH_MARKER not in ln
                     and "limits, derivatives, integration" not in ln
                     and "topics. Write formulas in readable Unicode" not in ln
                     and "one-line numeric-step explanation" not in ln
                     and "number of items." not in ln]
            base = "\n".join(lines)
        return base + _s_subject_lock_block(str(source_text or ""))

    globals()["_make_fast_new_mcq_prompt_74"] = _make_fast_new_mcq_prompt_74
    _logS("subject lock installed on generation prompt (calculus drift removed)")


# ── 2 & 3) Yield + bounded latency for OCR generation ────────────────────────

_s_batch_fast = globals().get("_generate_batch_fast_74")
_s_avoid_text = globals().get("_source_avoid_text_74")

if callable(_s_batch_fast):
    def _generate_quizzes_from_ocr_sync(ocr_ctx, desired, user_id):  # noqa: F811
        source_text = str((ocr_ctx or {}).get("clean_text")
                          or (ocr_ctx or {}).get("raw_markdown") or "").strip()
        if not source_text:
            raise RuntimeError("No readable OCR text found on this page.")

        desired = max(1, min(int(desired or 1), 200))
        avoid = ""
        if callable(_s_avoid_text):
            with _cxS.suppress(Exception):
                avoid = str(_s_avoid_text(ocr_ctx) or "")

        batch = 10 if desired > 10 else desired
        # Enough rounds to actually reach the target, plus a small allowance for
        # rejected/duplicate batches, but still bounded so latency stays sane.
        rounds = max(2, min(18, (desired + batch - 1) // batch + 4))

        out, seen = [], set()
        empty_streak = 0
        for _round in range(rounds):
            if len(out) >= desired:
                break
            need = min(batch, desired - len(out))
            recent = "\n".join("- " + x["question"][:140] for x in out[-20:])
            items = []
            with _cxS.suppress(Exception):
                items = _s_batch_fast(
                    source_text, need,
                    avoid_text=(avoid + "\n" + recent).strip(),
                ) or []
            if not items:
                empty_streak += 1
                # Tolerate transient truncated/invalid provider responses instead
                # of ending the whole command with a partial set.
                if empty_streak >= 3:
                    break
                continue
            empty_streak = 0
            for it in items:
                sig = _reS.sub(r"\s+", " ", str(it.get("question") or "")).lower()[:100]
                if not sig or sig in seen:
                    continue
                seen.add(sig)
                out.append(it)
                if len(out) >= desired:
                    break

        if not out:
            raise RuntimeError("All active AI providers returned invalid/empty quiz JSON.")
        return out[:desired]

    globals()["_generate_quizzes_from_ocr_sync"] = _generate_quizzes_from_ocr_sync
    _logS("OCR generation loop: larger batches, empty-round tolerance, bounded rounds")


_logS("subject lock + yield pass loaded")
