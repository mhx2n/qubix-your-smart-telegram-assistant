# ──────────────────────────────────────────────────────────────────────────────
# Section 108 — strict tenant ownership and final personal-bot callback repair.
# Loaded last by bot/__main__.py; do not import directly.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx108


def _qx108_can_view_all(uid):
    """Only the real owner on the main bot may use cross-owner listings.

    A tenant is intentionally an acting owner for feature permissions, but that
    must never grant access to another account's channels/groups/topics.
    """
    with _cx108.suppress(Exception):
        return bool(_qx_real_owner(int(uid))) and not bool(_qx_acting(int(uid)))
    return False


def channel_list_for_user(requester_id):  # noqa: F811
    conn = db_connect()
    try:
        if _qx108_can_view_all(requester_id):
            rows = conn.execute(
                "SELECT id,channel_chat_id,title,prefix,expl_link,added_by FROM channels ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id,channel_chat_id,title,prefix,expl_link,added_by FROM channels "
                "WHERE added_by=? ORDER BY id", (int(requester_id),),
            ).fetchall()
        return [ChannelRow(
            id=int(row["id"]), channel_chat_id=int(row["channel_chat_id"]),
            title=str(row["title"] or ""), prefix=str(row["prefix"] or ""),
            expl_link=str(row["expl_link"] or ""), added_by=int(row["added_by"] or 0),
        ) for row in rows]
    finally:
        conn.close()


def channel_get_by_id_for_user(requester_id, channel_id):  # noqa: F811
    channel = channel_get_by_id(int(channel_id))
    if channel is None:
        return None
    if _qx108_can_view_all(requester_id) or int(channel.added_by) == int(requester_id):
        return channel
    return None


def _sg_list(requester_id):  # noqa: F811
    conn = db_connect()
    try:
        if _qx108_can_view_all(requester_id):
            rows = conn.execute("SELECT * FROM saved_groups ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM saved_groups WHERE added_by=? ORDER BY id", (int(requester_id),),
            ).fetchall()
        return [SavedGroupRow(
            row["id"], int(row["group_chat_id"]), str(row["title"] or ""),
            int(row["added_by"] or 0), row["created_at"],
        ) for row in rows]
    finally:
        conn.close()


def _sg_get(serial, requester_id):  # noqa: F811
    conn = db_connect()
    try:
        row = conn.execute("SELECT * FROM saved_groups WHERE id=?", (int(serial),)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    if not _qx108_can_view_all(requester_id) and int(row["added_by"] or 0) != int(requester_id):
        return None
    return SavedGroupRow(
        row["id"], int(row["group_chat_id"]), str(row["title"] or ""),
        int(row["added_by"] or 0), row["created_at"],
    )


def _qx108_topic_requester(requester_id=None):
    """Resolve the current inbox owner without trusting patched owner checks."""
    if requester_id is not None:
        with _cx108.suppress(Exception):
            return int(requester_id)
    with _cx108.suppress(Exception):
        return int(_QX_ACTING_OWNER.get() or 0)
    return 0


def _gt_list(group_id, requester_id=None):  # noqa: F811
    """Return only the current user's topics; the real main owner may see all."""
    requester = _qx108_topic_requester(requester_id)
    conn = db_connect()
    try:
        if requester <= 0 or _qx108_can_view_all(requester):
            rows = conn.execute("SELECT * FROM group_topics WHERE group_id=? ORDER BY id", (int(group_id),)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM group_topics WHERE group_id=? AND added_by=? ORDER BY id",
                (int(group_id), requester),
            ).fetchall()
        return [GroupTopicRow(
            row["id"], row["group_id"], row["topic_name"], row["thread_id"],
            row["added_by"], row["created_at"],
        ) for row in rows]
    finally:
        conn.close()


def _gt_get(topic_id, requester_id=None):  # noqa: F811
    """Reject direct topic-id access when the row belongs to another user."""
    requester = _qx108_topic_requester(requester_id)
    conn = db_connect()
    try:
        row = conn.execute("SELECT * FROM group_topics WHERE id=?", (int(topic_id),)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    if requester > 0 and not _qx108_can_view_all(requester) and int(row["added_by"] or 0) != requester:
        return None
    return GroupTopicRow(
        row["id"], row["group_id"], row["topic_name"], row["thread_id"],
        row["added_by"], row["created_at"],
    )


globals()["channel_list_for_user"] = channel_list_for_user
globals()["channel_get_by_id_for_user"] = channel_get_by_id_for_user
globals()["_sg_list"] = _sg_list
globals()["_sg_get"] = _sg_get
globals()["_gt_list"] = _gt_list
globals()["_gt_get"] = _gt_get

with _cx108.suppress(Exception):
    logger.info("[QX108] strict tenant ownership and pre-start menu routing active")

# ===== END SECTION 108 =====