# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 111 — GROUP PREFIX / EXPLINK ACCESS + MENU (2026-08-05)
#
# Fix: inside a user's own (token-added) bot, commands like `.gsp` / `.gsx`
# were not part of QX_WORKSPACE_COMMANDS, so the child gate replied with the
# "Owner infrastructure command" line — which the section-96 shield then
# rewrote into the generic workspace card. Result: no response at all.
#
# This section ONLY:
#   1. whitelists those already-registered user commands for the workspace
#      (main bot + every personal bot),
#   2. adds them to the Telegram "/" command menu list,
#   3. appends them to the user command sheet / fallback card.
# No existing behaviour or handler is modified.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx111

# ── 1) Commands that already exist and are safe for a workspace user ─────────
_QX111_COMMANDS = [
    ("gsp",         "Group quiz prefix সেট"),
    ("gsx",         "Group explanation link সেট"),
    ("gsetprefix",  "Group prefix (long alias)"),
    ("gsetexplink", "Group explanation link (long alias)"),
    ("lg",          "Group list (short)"),
    ("lt",          "Topic list (short)"),
    ("pg",          "Group-এ post"),
    ("ct",          "Topic anchor মুছুন (short)"),
    ("deltopic",    "Saved topic মুছুন"),
    ("scoreon",     "Score reply চালু"),
    ("scoreoff",    "Score reply বন্ধ"),
    ("scon",        "Score reply চালু (short)"),
    ("scoff",       "Score reply বন্ধ (short)"),
    ("scoreformat", "Score card format সেট"),
]

_QX111_NAMES = {name for name, _ in _QX111_COMMANDS}

with _cx111.suppress(Exception):
    _qx111_ws = globals().get("QX_WORKSPACE_COMMANDS")
    if isinstance(_qx111_ws, set):
        _qx111_ws |= _QX111_NAMES          # mutate in place: gates share the set

with _cx111.suppress(Exception):
    _qx111_retired = globals().get("QX_RETIRED_USER_COMMANDS")
    if isinstance(_qx111_retired, set):
        for _qx111_name in _QX111_NAMES:
            _qx111_retired.discard(_qx111_name)


# ── 2) Telegram "/" menu (user + tenant bots share the same list object) ─────
def _qx111_extend_menu(list_name: str) -> None:
    menu = globals().get(list_name)
    if not isinstance(menu, list):
        return
    existing = {str(item[0]) for item in menu if item}
    for name, desc in _QX111_COMMANDS:
        if name in existing:
            continue
        menu.append((name, desc))
        existing.add(name)


for _qx111_list in ("QX97_USER_MENU_COMMANDS", "QX94_USER_MENU_COMMANDS"):
    with _cx111.suppress(Exception):
        _qx111_extend_menu(_qx111_list)


# ── 3) Command sheet / fallback card text ───────────────────────────────────
_QX111_SHEET_BLOCK = (
    "\n\n<b>Group prefix &amp; explanation link</b>\n"
    "<code>.gsp &lt;group#&gt; আপনার প্রিফিক্স</code> — group quiz prefix\n"
    "<code>.gsx &lt;group#&gt; https://t.me/...</code> — explanation link\n"
    "<code>.gsp &lt;group#&gt;</code> / <code>.gsx &lt;group#&gt;</code> — clear\n"
    "<code>.lg</code> · <code>.lt &lt;group#&gt;</code> · "
    "<code>.scon</code> / <code>.scoff</code> — score reply"
)


def _qx111_patch_card(card_name: str) -> None:
    card = globals().get(card_name)
    if not isinstance(card, str) or not card:
        return
    if ".gsp" in card:
        return
    globals()[card_name] = card + _QX111_SHEET_BLOCK


for _qx111_card in (
    "QX95_USER_COMMANDS_CARD",
    "QX94_USER_COMMANDS_CARD",
    "QX93_COMMANDS_CARD",
):
    with _cx111.suppress(Exception):
        _qx111_patch_card(_qx111_card)


# Fallback workspace card (section 96) — mention the new group controls too.
with _cx111.suppress(Exception):
    _qx111_prev_user_card = globals().get("_qx96_user_card")
    if callable(_qx111_prev_user_card):
        def _qx111_user_card(chat_id):
            text = _qx111_prev_user_card(chat_id)
            if isinstance(text, str) and ".gsp" not in text:
                text = text + (
                    "\n🎯 <b>Group prefix/link</b> — "
                    "<code>.gsp &lt;group#&gt; text</code> · "
                    "<code>.gsx &lt;group#&gt; link</code>"
                )
            return text

        globals()["_qx96_user_card"] = _qx111_user_card

with _cx111.suppress(Exception):
    logger.info("[QX111] group prefix/explink commands enabled for user bots + menu")

# ===== END SECTION 111 =====
