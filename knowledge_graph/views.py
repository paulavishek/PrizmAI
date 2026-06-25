import json
import logging
import time

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET

from kanban.models import Board
from kanban.decorators import demo_write_guard
from knowledge_graph.models import MemoryNode, MemoryConnection, OrganizationalMemoryQuery

logger = logging.getLogger(__name__)


def _get_user_boards(user):
    """Return board IDs the user has access to (demo-aware)."""
    from kanban.utils.demo_protection import get_user_boards
    return get_user_boards(user).values_list('id', flat=True)


def _accessible_memory_qs(user):
    """MemoryNodes the user may see: those on boards they can access, plus any
    workspace-wide memories in a workspace they collaborate in.

    A "workspace-wide" memory (``is_org_wide=True``) on a board in workspace W
    is visible to the **formal members of W** — the WorkspaceMembership roster
    managed on the Manage Members page — not to anyone who merely shares a single
    board that happens to live in W. Keying on incidental board membership leaks
    org-wide memories across tenants (a board shared cross-workspace would expose
    every org-wide memory in the owning workspace), so we resolve membership from
    WorkspaceMembership instead.

    In demo mode the demo workspace has no WorkspaceMembership rows (demo is an
    intentionally shared single workspace, isolated via per-user board copies),
    so we retain the board-derived collaborator set there.
    """
    from kanban.utils.demo_protection import get_user_boards
    boards = get_user_boards(user)
    board_ids = list(boards.values_list('id', flat=True))

    profile = getattr(user, 'profile', None)
    if getattr(profile, 'is_viewing_demo', False):
        member_ws_ids = list(boards.values_list('workspace_id', flat=True))
    else:
        from kanban.models import WorkspaceMembership, Workspace
        member_ws_ids = set(
            WorkspaceMembership.objects.filter(user=user)
            .values_list('workspace_id', flat=True)
        )
        # Safety net for any workspace created before the membership backfill
        # (kanban migration 0123) that lacks an explicit creator membership.
        member_ws_ids |= set(
            Workspace.objects.filter(created_by=user).values_list('id', flat=True)
        )

    visibility = Q(board_id__in=board_ids)
    if member_ws_ids:
        visibility |= Q(is_org_wide=True, board__workspace_id__in=member_ws_ids)
    return MemoryNode.objects.filter(visibility).distinct()


# Manual node types a user may pick when logging a memory (value, label).
MANUAL_NODE_TYPES = [
    ('decision', 'Decision'),
    ('lesson', 'Lesson Learned'),
    ('risk_event', 'Risk Event'),
    ('milestone', 'Milestone'),
    ('note', 'Note'),
]
# Types accepted by the create/edit endpoints. Includes 'manual_log' for
# backward compatibility with the existing board-knowledge modal.
ALLOWED_MANUAL_TYPES = {t[0] for t in MANUAL_NODE_TYPES} | {'manual_log'}


def _derive_title(content, limit=120):
    """Produce a clean, human-readable title from free-text content.

    Breaks on the first sentence when reasonable, otherwise cuts at a word
    boundary (never mid-word) and appends an ellipsis. Used when a memory is
    logged with only a 'what happened' field and no explicit title.
    """
    import re as _re
    text = (content or '').strip()
    if not text:
        return ''
    base = (text.split('\n', 1)[0].strip()) or text
    # Prefer the first sentence if it's a sensible length.
    m = _re.match(r'^(.*?[.!?])(\s|$)', base)
    if m and 20 <= len(m.group(1)) <= limit + 20:
        return m.group(1).strip()[:200]
    if len(base) <= limit:
        return base[:200]
    cut = base[:limit]
    last_space = cut.rfind(' ')
    if last_space > limit // 2:
        cut = cut[:last_space]
    return cut.rstrip() + '…'


def gap_analysis_system_prompt(node_type, description):
    """Build the exact system prompt used for Spectra gap analysis.

    Shared by the pre-save review endpoint (Part 1) and the lazy Celery task
    (knowledge_graph.tasks.analyze_memory_gaps) so both ask Gemini the same way.
    """
    return (
        "You are reviewing a memory entry written by a project manager. First "
        "decide whether it is already useful enough for a teammate reading it "
        "months from now; only if it is not, identify the critical context that "
        "is missing. Do not answer questions. Do not make assumptions. Do not "
        "add generic advice.\n\n"
        f"Memory type: {node_type}\n"
        f"Memory entry: {description}\n\n"
        "Sufficiency rule: if the entry already contains a clear description of "
        "WHAT happened, WHO was involved, and at least ONE outcome or follow-up "
        "action, it is good enough — return an empty array, regardless of what "
        "additional detail could theoretically be added. Only flag gaps for "
        "genuinely missing critical information (root cause, decision owner, "
        "impact, timeline, follow-up actions, risks) — never for deeper "
        "elaboration on information that is already present.\n\n"
        "When the entry is NOT sufficient, return up to 5 specific questions, "
        "each targeting information that is actually absent. Be specific to what "
        "was written — do not ask generic project-management questions that "
        "could apply to any situation.\n\n"
        "Return ONLY a JSON array of question strings (which may be empty). No "
        "preamble, no explanation, no markdown. Example:\n"
        '["Question one?", "Question two?"] or []'
    )


# When re-checking a memory after an edit, clear the "Gaps Noted" flag once
# this many or fewer critical gaps remain — the entry is "good enough" even if
# not every original question was answered.
GAP_CLEAR_THRESHOLD = 2

# Hard cap on enrichment rounds. The gap prompt can always invent a deeper
# follow-up question, so a purely AI-driven loop never terminates. After this
# many user edits of an already-flagged memory we clear the flag regardless of
# what Spectra still asks — two rounds of enrichment is enough.
GAP_ENRICHMENT_CAP = 2

# Minimum number of characters a flagged memory's content must grow by for an
# edit to count as a genuine enrichment round. A no-op or near-empty save no
# longer advances GAP_ENRICHMENT_CAP toward auto-clearing the badge — the
# anchored AI recheck stays the authority, so the flag only clears when the
# originally-flagged questions are actually answered.
MIN_ENRICHMENT_CHARS = 40


def gap_recheck_system_prompt(node_type, description):
    """Build the prompt used to re-assess gaps after a memory is edited.

    Unlike gap_analysis_system_prompt (which always asks for 3–5 questions),
    this allows an empty result so a now-thorough memory can clear its flag.
    """
    return (
        "You are reviewing a memory entry that a project manager has just edited "
        "to add more detail. Decide whether it is now good enough. Do not answer "
        "questions. Do not make assumptions.\n\n"
        f"Memory type: {node_type}\n"
        f"Memory entry: {description}\n\n"
        "Sufficiency rule: if the entry now contains a clear description of WHAT "
        "happened, WHO was involved, and at least ONE outcome or follow-up "
        "action, return an empty array — regardless of what further detail could "
        "be added. Only list genuinely critical information that is still ABSENT "
        "(root cause, decision owner, impact, timeline, follow-up actions, "
        "risks); never ask for deeper elaboration on information already "
        "present. Return at most 5 questions.\n\n"
        "Return ONLY a JSON array of question strings (which may be empty). No "
        'preamble, no markdown. Example: ["Question one?"] or []'
    )


def gap_progress_system_prompt(node_type, description, original_questions):
    """Re-check prompt for ANCHORED progressive gap tracking.

    Unlike gap_recheck_system_prompt (which finds gaps freely), this hands Gemini
    a FIXED checklist of the originally-identified questions and asks which of
    THOSE are still unanswered by the current text. It must not invent or
    rephrase questions — it returns a verbatim subset of the provided list.
    """
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(original_questions))
    return (
        "You are checking a project-management memory entry against a FIXED "
        "checklist of questions that were previously identified as missing "
        "context. The memory has just been edited. Decide which checklist "
        "questions are now answered by the text and which are still "
        "unanswered.\n\n"
        f"Memory type: {node_type}\n"
        f"Memory entry: {description}\n\n"
        "Checklist (do NOT add to it, do NOT rephrase it, do NOT invent new "
        "questions):\n"
        f"{numbered}\n\n"
        "Mark a checklist question as ANSWERED only if the entry now contains "
        "specific, relevant information that directly addresses THAT question. Do "
        "NOT count vague, generic, off-topic, or padding text as an answer — if "
        "the added detail does not actually answer the question, the question is "
        "still unanswered. When in doubt, treat it as unanswered.\n\n"
        "Return ONLY the checklist questions that are still NOT answered by the "
        "memory entry, copied VERBATIM from the list above, as a JSON array of "
        "strings. If every question is now genuinely answered, return an empty "
        "array.\n\n"
        "Return ONLY the JSON array. No preamble, no markdown. Example: "
        '["Question two?"] or []'
    )


def parse_gap_questions(raw):
    """Parse Gemini's response into a list of question strings.

    Strips ```` ``` ```` fences (mirroring the other knowledge_graph views) and
    returns a list, or [] if parsing fails or the shape is unexpected.
    """
    cleaned = (raw or '').strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    try:
        parsed = json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(parsed, list):
        return [str(q).strip() for q in parsed if str(q).strip()]
    return []


def _can_manage_memory(request, node):
    """True if the user may edit/delete this memory.

    Rule: demo sandbox has no RBAC, so every board-attached memory is manageable
    there. Outside demo: the creator, or an Owner/Org-Admin-level overseer
    (invite_board_member perm). Auto-captured (system) memories have no creator,
    so they fall through to the overseer check — this lets an Owner/Org-Admin
    enrich a flagged auto-captured memory through the "Gaps Noted -> Expand this
    memory" loop, which is the common case in a real workspace.
    """
    if node.board is None:
        return False
    from kanban.permissions import is_demo_context
    if is_demo_context(request, board=node.board):
        return True
    if node.created_by_id == request.user.id:
        return True
    return request.user.has_perm('prizmai.invite_board_member', node.board)


# ── View 1: Board Knowledge Tab ─────────────────────────────────────────────

@login_required
def board_knowledge(request, board_id):
    """Knowledge page for a specific board — decisions, lessons, auto-captured memories."""
    board = get_object_or_404(Board, id=board_id)

    # RBAC: user must have view permission on the board
    if not request.user.has_perm('prizmai.view_board', board):
        from django.http import Http404
        raise Http404

    nodes = (
        MemoryNode.objects
        .filter(board=board)
        .select_related('created_by')
        .annotate(connection_count=Count('outgoing_connections') + Count('incoming_connections'))
        .order_by('-importance_score', '-created_at')
    )

    manual_nodes = nodes.filter(is_auto_captured=False)
    auto_nodes = nodes.filter(is_auto_captured=True)

    # Serialize all node data + connections as JSON for the interactive detail modal
    node_list = list(nodes)
    all_node_ids = [n.pk for n in node_list]

    nodes_data = {}
    for node in node_list:
        nodes_data[str(node.pk)] = {
            'title': node.title,
            'content': node.content,
            'node_type': node.node_type,
            'node_type_display': node.get_node_type_display(),
            'tags': node.tags if isinstance(node.tags, list) else [],
            'created_at': node.created_at.strftime('%b %d, %Y'),
            'created_by': (
                node.created_by.get_full_name() or node.created_by.username
                if node.created_by else None
            ),
            'is_auto_captured': node.is_auto_captured,
            'is_org_wide': node.is_org_wide,
            'manageable': _can_manage_memory(request, node),
            'importance_score': round(node.importance_score, 2),
        }

    # Build per-node connection map (both incoming and outgoing)
    connections_qs = MemoryConnection.objects.filter(
        Q(from_node_id__in=all_node_ids) | Q(to_node_id__in=all_node_ids)
    ).select_related('from_node', 'to_node')

    node_connections_map = {}
    for conn in connections_qs:
        if conn.from_node_id in all_node_ids:
            node_connections_map.setdefault(str(conn.from_node_id), []).append({
                'direction': 'outgoing',
                'type': conn.connection_type,
                'type_display': conn.get_connection_type_display(),
                'reason': conn.reason,
                'other_title': conn.to_node.title,
                'other_type': conn.to_node.get_node_type_display(),
                'ai_generated': conn.ai_generated,
            })
        if conn.to_node_id in all_node_ids:
            node_connections_map.setdefault(str(conn.to_node_id), []).append({
                'direction': 'incoming',
                'type': conn.connection_type,
                'type_display': conn.get_connection_type_display(),
                'reason': conn.reason,
                'other_title': conn.from_node.title,
                'other_type': conn.from_node.get_node_type_display(),
                'ai_generated': conn.ai_generated,
            })

    context = {
        'board': board,
        'manual_nodes': manual_nodes,
        'auto_nodes': auto_nodes,
        'auto_count': auto_nodes.count(),
        'total_count': nodes.count(),
        'nodes_data': nodes_data,
        'node_connections_data': node_connections_map,
        'manual_node_types': MANUAL_NODE_TYPES,
        'can_mark_org_wide': request.user.has_perm('prizmai.invite_board_member', board),
    }
    return render(request, 'knowledge_graph/board_knowledge.html', context)


# ── View 2: Add Manual Memory ───────────────────────────────────────────────

@login_required
@require_POST
@demo_write_guard
def add_manual_memory(request, board_id):
    """Add a manual decision or lesson memory node to a board."""
    board = get_object_or_404(Board, id=board_id)

    # RBAC: user must have edit permission on the board to add memories
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    node_type = data.get('node_type', 'decision')
    tags_raw = (data.get('tags') or '').strip()

    if not content:
        return JsonResponse({'error': 'Please describe what happened.'}, status=400)
    # Title is optional — derive a clean one from the content when omitted.
    if not title:
        title = _derive_title(content)

    if node_type not in ALLOWED_MANUAL_TYPES:
        node_type = 'decision'

    # Org-wide visibility is a privileged act — only Owners/Org Admins may set it.
    is_org_wide = bool(data.get('is_org_wide')) and \
        request.user.has_perm('prizmai.invite_board_member', board)

    tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    # ── Spectra gap review (Part 1) ───────────────────────────────────────────
    # The client sends the questions Spectra raised plus the description length
    # at the moment of review.
    gap_questions = data.get('gap_questions') or []
    if not isinstance(gap_questions, list):
        gap_questions = []
    try:
        review_desc_len = int(data.get('review_desc_len') or 0)
    except (ValueError, TypeError):
        review_desc_len = 0

    if gap_questions:
        # Author ran Spectra's review. Gaps remain open unless they then
        # substantially expanded the entry (> 30 chars) in response.
        expanded = (len(content) - review_desc_len) > 30
        has_gaps = not expanded
        gaps_analyzed = True
        saved_questions = gap_questions if has_gaps else None
    else:
        # Saved without reviewing — treat as a thin, unreviewed record: flag it
        # and leave gaps_analyzed=False so lazy analysis can fill in specific
        # questions (real workspaces). In demo, the badge popover shows a generic
        # prompt to open it and ask Spectra.
        has_gaps = True
        gaps_analyzed = False
        saved_questions = None

    node = MemoryNode.objects.create(
        board=board,
        mission=board.strategy.mission if board.strategy else None,
        node_type=node_type,
        title=title[:200],
        content=content,
        tags=tags,
        created_by=request.user,
        is_auto_captured=False,
        is_org_wide=is_org_wide,
        importance_score=0.6,
        gap_questions=saved_questions,
        gap_questions_original=saved_questions,
        has_gaps=has_gaps,
        gaps_analyzed=gaps_analyzed,
    )

    try:
        from kanban.audit_utils import log_audit
        log_audit(
            action_type='memory.created',
            user=request.user,
            request=request,
            object_type='MemoryNode',
            object_id=node.pk,
            object_repr=title[:80],
            message=f"Manual memory node created: {title[:80]}",
            additional_data={'board_id': board_id, 'node_type': node_type},
        )
    except Exception:
        pass

    return JsonResponse({
        'status': 'success',
        'node': {
            'id': node.pk,
            'title': node.title,
            'content': node.content,
            'node_type': node.node_type,
            'node_type_display': node.get_node_type_display(),
            'tags': node.tags,
            'created_at': node.created_at.strftime('%b %d, %Y'),
            'created_by': request.user.get_full_name() or request.user.username,
        }
    })


# ── View 2b: Edit Manual Memory ─────────────────────────────────────────────

@login_required
@require_POST
@demo_write_guard
def edit_manual_memory(request, node_id):
    """Edit a logged memory. Creator or Owner/Org-Admin only. Auto-captured
    (system) memories are editable by an Owner/Org-Admin so they can enrich a
    flagged memory via the "Gaps Noted -> Expand this memory" loop."""
    node = get_object_or_404(MemoryNode, id=node_id)

    if not _can_manage_memory(request, node):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    node_type = data.get('node_type', node.node_type)
    tags_raw = (data.get('tags') or '').strip()

    if not content:
        return JsonResponse({'error': 'Please describe what happened.'}, status=400)
    # Title is optional. On edit, keep the memory's existing title so enriching a
    # flagged memory never silently renames it; only derive from content when
    # there is no prior title (legacy rows). Create (add_manual_memory) still
    # derives from content.
    if not title:
        title = node.title or _derive_title(content)

    # Preserve the node's existing type when the submitted one isn't a valid
    # manual type (e.g. editing an auto-captured 'ai_recommendation' in demo) so
    # editing never silently reclassifies a system memory.
    if node_type not in ALLOWED_MANUAL_TYPES:
        node_type = node.node_type

    # Capture how much the content grew BEFORE overwriting it, so a trivial edit
    # can't advance the enrichment cap (see MIN_ENRICHMENT_CHARS below).
    content_growth = len(content) - len(node.content or '')

    node.title = title[:200]
    node.content = content
    node.node_type = node_type
    node.tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    # Org-wide visibility is privileged — only Owners/Org Admins may change it.
    if request.user.has_perm('prizmai.invite_board_member', node.board):
        node.is_org_wide = bool(data.get('is_org_wide'))

    # Re-assess gaps against the edited content (anchored progressive tracking).
    # Editing is the user's chance to fill in missing context, so re-check which
    # of the ORIGINAL gap questions are still unanswered — never invent new ones.
    # On any AI failure, fall back to clearing the flag.
    node.gaps_analyzed = True

    # Backfill the canonical checklist for memories flagged before anchored
    # tracking existed: adopt the current remaining questions as the original.
    if not node.gap_questions_original and node.gap_questions:
        node.gap_questions_original = node.gap_questions

    # Count this edit as a round of enrichment only if the memory was flagged AND
    # the user actually added a meaningful amount of new context. A no-op or
    # near-empty save must not march the memory toward the auto-clear cap.
    was_flagged = node.has_gaps
    is_real_enrichment = was_flagged and content_growth >= MIN_ENRICHMENT_CHARS
    if is_real_enrichment:
        node.gap_enrichment_count = (node.gap_enrichment_count or 0) + 1

    original = node.gap_questions_original or []

    # The FREE-FORM recheck (no fixed checklist) can surface endless new
    # questions, so a hard edit-count cap is the only guaranteed terminator.
    # The ANCHORED recheck can't run away — its checklist only ever shrinks — so
    # there the AI relevance check is the sole authority; a blind cap would clear
    # the badge even for irrelevant edits, which is exactly what we must not do.
    if was_flagged and not original and node.gap_enrichment_count >= GAP_ENRICHMENT_CAP:
        node.has_gaps = False
        node.gap_questions = None
    else:
        ai_failed = False
        try:
            from ai_assistant.utils.ai_router import AIRouter
            if original:
                # Anchored: which of the FIXED original questions remain unanswered.
                system_prompt = gap_progress_system_prompt(node.node_type, content, original)
            else:
                # No anchored checklist yet (e.g. saved-without-review memory not
                # yet lazily analysed). Find gaps freely and adopt the result as
                # the canonical checklist for future edits.
                system_prompt = gap_recheck_system_prompt(node.node_type, content)
            resp = AIRouter().complete(
                prompt='Return the JSON array of remaining gap questions now.',
                user=request.user,
                system_prompt=system_prompt,
                complexity='simple',
            )
            remaining = parse_gap_questions(resp.get('text', ''))
        except Exception as exc:
            logger.warning(f"Gap re-check on edit failed for node {node.pk}: {exc}")
            remaining = []
            ai_failed = True

        if original:
            # Defensive: keep only real checklist items so Gemini can't smuggle
            # in new questions; the checklist can only shrink.
            original_set = set(original)
            remaining = [q for q in remaining if q in original_set]

            if ai_failed:
                # Never clear an anchored memory on an AI outage — keep the
                # unanswered questions standing so they can't vanish silently.
                node.has_gaps = True
                node.gap_questions = node.gap_questions or original
            else:
                # Clear ONLY when the user genuinely answered the flagged
                # questions. "Made progress" (answered at least one) gates the
                # good-enough threshold so that irrelevant additions — which
                # answer nothing, leaving the full checklist — can never clear the
                # badge, even for a one- or two-question checklist.
                made_progress = len(remaining) < len(original)
                good_enough = made_progress and len(remaining) <= GAP_CLEAR_THRESHOLD
                if not remaining or good_enough:
                    node.has_gaps = False
                    node.gap_questions = None
                else:
                    node.has_gaps = True
                    node.gap_questions = remaining
        else:
            # First-time anchor: freeze whatever was found as the checklist.
            if remaining:
                node.gap_questions_original = remaining
            if remaining and len(remaining) > GAP_CLEAR_THRESHOLD:
                node.has_gaps = True
                node.gap_questions = remaining
            else:
                node.has_gaps = False
                node.gap_questions = None
    node.save()

    try:
        from kanban.audit_utils import log_audit
        log_audit(
            action_type='memory.updated',
            user=request.user,
            request=request,
            object_type='MemoryNode',
            object_id=node.pk,
            object_repr=node.title[:80],
            message=f"Manual memory node updated: {node.title[:80]}",
            additional_data={'board_id': node.board_id, 'node_type': node.node_type},
        )
    except Exception:
        pass

    return JsonResponse({
        'status': 'success',
        'node': {
            'id': node.pk,
            'title': node.title,
            'content': node.content,
            'node_type': node.node_type,
            'node_type_display': node.get_node_type_display(),
            'tags': node.tags,
            'is_org_wide': node.is_org_wide,
            'created_at': node.created_at.strftime('%b %d, %Y'),
            'created_by': (
                node.created_by.get_full_name() or node.created_by.username
                if node.created_by else None
            ),
        }
    })


# ── View 2c: Delete Manual Memory ───────────────────────────────────────────

@login_required
@require_POST
@demo_write_guard
def delete_manual_memory(request, node_id):
    """Delete a manually-logged memory. Creator or Owner/Org-Admin only;
    never auto-captured (system) memories."""
    node = get_object_or_404(MemoryNode, id=node_id)

    if not _can_manage_memory(request, node):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    title = node.title
    board_id = node.board_id

    try:
        from kanban.audit_utils import log_audit
        log_audit(
            action_type='memory.deleted',
            user=request.user,
            request=request,
            object_type='MemoryNode',
            object_id=node.pk,
            object_repr=title[:80],
            message=f"Manual memory node deleted: {title[:80]}",
            additional_data={'board_id': board_id, 'node_type': node.node_type},
        )
    except Exception:
        pass

    node.delete()
    return JsonResponse({'status': 'success'})


# ── View 2d: Pre-Save Spectra Gap Review ────────────────────────────────────

@login_required
@require_POST
def review_memory_gaps(request):
    """Ask Spectra what context is missing from a draft memory entry.

    This backs the "Ask Spectra what's missing" button and is intentionally
    DIFFERENT from the re-check that runs on save (edit_manual_memory):

    - Here (preview): a pre-save, frontend-only review. No DB writes, and it does
      NOT touch has_gaps. It surfaces what's currently missing using
      gap_analysis_system_prompt (sufficiency rule → 0–5 questions), so it can
      keep listing items even when the entry is close to good enough.
    - On save (commit): edit_manual_memory re-checks the ANCHORED original
      checklist (gap_progress_system_prompt) and decides has_gaps using
      GAP_CLEAR_THRESHOLD + GAP_ENRICHMENT_CAP. That is why the badge can clear on
      save even though this preview still shows a question or two — the preview
      informs, the save commits.

    Returns a JSON array of questions (possibly empty), or [] on any failure
    (silent graceful fallback — never surfaces an error to the user)."""
    try:
        # Check AI quota
        from api.ai_usage_utils import check_ai_quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)

        data = json.loads(request.body)
        description = (data.get('description') or '').strip()
        node_type = (data.get('node_type') or 'note').strip()
        if not description:
            return JsonResponse({'questions': [], 'sufficient': False})

        # When previewing an EDIT of an already-flagged memory, anchor the review
        # to that memory's ORIGINAL gap checklist (same prompt the save-time
        # re-check uses) so the preview verdict matches what Save will actually
        # do. Otherwise (create, or no anchored checklist yet) fall back to the
        # free-form sufficiency review.
        original = []
        node_id = data.get('node_id')
        if node_id:
            anchored = (
                MemoryNode.objects
                .filter(id=node_id)
                .values_list('gap_questions_original', flat=True)
                .first()
            )
            original = anchored or []

        from ai_assistant.utils.ai_router import AIRouter
        if original:
            system_prompt = gap_progress_system_prompt(node_type, description, original)
        else:
            system_prompt = gap_analysis_system_prompt(node_type, description)
        response = AIRouter().complete(
            prompt='Return the JSON array of questions now.',
            user=request.user,
            system_prompt=system_prompt,
            complexity='simple',
        )
        questions = parse_gap_questions(response.get('text', ''))
        if original:
            # Defensive: anchored review can only return a subset of the checklist.
            original_set = set(original)
            questions = [q for q in questions if q in original_set]
        # "Sufficient" mirrors the save-time clear rule. For an anchored edit the
        # badge clears only when every flagged question is answered, or the user
        # answered all but a small remainder (good-enough net gated on real
        # progress so irrelevant additions never read as sufficient). For a
        # free-form create review it just means nothing critical is missing.
        if original:
            made_progress = len(questions) < len(original)
            sufficient = (
                len(questions) == 0
                or (made_progress and len(questions) <= GAP_CLEAR_THRESHOLD)
            )
        else:
            sufficient = len(questions) == 0
        return JsonResponse({'questions': questions, 'sufficient': sufficient})
    except Exception as exc:
        logger.warning(f"review_memory_gaps failed, returning no questions: {exc}")
        return JsonResponse({'questions': [], 'sufficient': False})


# ── View 3: Organizational Memory Page ──────────────────────────────────────

@login_required
def organizational_memory(request):
    """Organizational Memory page — the global search interface."""
    board_ids = _get_user_boards(request.user)
    accessible = _accessible_memory_qs(request.user)

    total_nodes = accessible.count()

    boards_count = Board.objects.filter(id__in=board_ids).count()

    oldest = accessible.order_by('created_at').values_list(
        'created_at', flat=True
    ).first()

    recent_queries = (
        OrganizationalMemoryQuery.objects.filter(
            asked_by=request.user
        ).order_by('-asked_at')[:5]
        if total_nodes > 0 else []
    )

    # Fetch more than 5 then deduplicate by title so repeated auto-captured
    # memories with identical titles don't fill all slots.
    _raw_nodes = (
        accessible
        .select_related('board', 'created_by')
        .order_by('-created_at')[:30]
    )
    _seen_titles = set()
    recent_nodes = []
    for _n in _raw_nodes:
        if _n.title not in _seen_titles:
            _seen_titles.add(_n.title)
            # Flag whether the current user may edit/delete this memory.
            _n.manageable = _can_manage_memory(request, _n)
            recent_nodes.append(_n)
            if len(recent_nodes) >= 5:
                break

    # ── Lazy gap analysis (Part 3B) ───────────────────────────────────────────
    # Dispatch Spectra gap analysis for up to 5 not-yet-analysed memories.
    # Fully async via .delay(); wrapped so a down broker never breaks the page.
    # Skipped in demo/sandbox so the curated demo badges stay meaningful and we
    # don't spend Gemini quota flagging every demo memory on each page view.
    from kanban.permissions import is_demo_context
    if not is_demo_context(request):
        try:
            from knowledge_graph.tasks import analyze_memory_gaps
            unanalyzed_ids = list(
                accessible.filter(gaps_analyzed=False).values_list('id', flat=True)[:5]
            )
            for _node_id in unanalyzed_ids:
                analyze_memory_gaps.delay(_node_id)
        except Exception as exc:
            logger.warning(f"Could not dispatch lazy gap analysis: {exc}")

    # Boards the user can log a memory against (edit access), plus whether they
    # may mark any of them organization-wide (Owner/Org Admin level).
    editable_boards = [
        b for b in Board.objects.filter(id__in=board_ids).order_by('name')
        if request.user.has_perm('prizmai.edit_board', b)
    ]
    can_mark_org_wide = any(
        request.user.has_perm('prizmai.invite_board_member', b)
        for b in editable_boards
    )

    context = {
        'total_nodes': total_nodes,
        'boards_count': boards_count,
        'oldest_memory_date': oldest,
        'recent_queries': recent_queries,
        'recent_nodes': recent_nodes,
        'editable_boards': editable_boards,
        'manual_node_types': MANUAL_NODE_TYPES,
        'can_mark_org_wide': can_mark_org_wide,
    }
    try:
        from ai_assistant.utils.ai_router import AIRouter
        _provider, _, _, _ = AIRouter()._resolve_provider(request.user)  # display-only, not for routing
        context['active_provider_name'] = AIRouter.get_provider_display_name(_provider)
    except Exception:
        context['active_provider_name'] = 'Google Gemini'
    return render(request, 'knowledge_graph/organizational_memory.html', context)


# ── View 3b: Memory Browse (AJAX offcanvas panel) ────────────────────────────

@login_required
@require_GET
def memory_browse(request):
    """AJAX: return HTML partial for the browse-memories offcanvas panel."""
    board_ids = _get_user_boards(request.user)
    base_qs = _accessible_memory_qs(request.user).select_related('board')

    sort = request.GET.get('sort', 'newest')
    project_id = request.GET.get('project', '').strip()
    cards_only = request.GET.get('cards_only') == '1'
    try:
        page = max(1, int(request.GET.get('page') or 1))
    except (ValueError, TypeError):
        page = 1

    PER_PAGE = 20
    nodes_qs = base_qs
    if project_id:
        try:
            nodes_qs = nodes_qs.filter(board_id=int(project_id))
        except (ValueError, TypeError):
            pass

    if sort == 'oldest':
        nodes_qs = nodes_qs.order_by('created_at')
    else:
        nodes_qs = nodes_qs.order_by('-created_at')

    total = nodes_qs.count()
    offset = (page - 1) * PER_PAGE
    nodes = list(nodes_qs[offset:offset + PER_PAGE])
    has_more = (offset + PER_PAGE) < total

    # Flag whether the current user may edit each node so the "Gaps Noted"
    # popover can show the "Expand this memory" button conditionally.
    for _n in nodes:
        _n.manageable = _can_manage_memory(request, _n)

    projects_qs = (
        Board.objects.filter(id__in=board_ids)
        .annotate(memory_count=Count('memory_nodes'))
        .filter(memory_count__gt=0)
        .order_by('-memory_count', 'name')
    )

    context = {
        'nodes': nodes,
        'projects': projects_qs,
        'has_more': has_more,
        'next_page': page + 1,
        'total': total,
        'sort': sort,
        'active_project': project_id,
        'cards_only': cards_only,
    }
    return render(request, 'knowledge_graph/_memory_browse_panel.html', context)


# ── View 4: Organizational Memory Search (AJAX) ─────────────────────────────

@login_required
@require_POST
def organizational_memory_search(request):
    """Search organizational memory using Gemini AI."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    query_text = (data.get('query') or '').strip()
    if not query_text:
        return JsonResponse({'error': 'Query is required.'}, status=400)
    if len(query_text) > 500:
        return JsonResponse({'error': 'Query too long (max 500 characters).'}, status=400)

    from api.ai_usage_utils import check_ai_quota, track_ai_request
    has_quota, _, remaining = check_ai_quota(request.user)
    if not has_quota:
        return JsonResponse({'error': 'AI quota exceeded. Try again later.'}, status=429)

    accessible = _accessible_memory_qs(request.user)

    # Step 1: Always include the top 80 nodes by importance score.
    top_nodes = list(
        accessible
        .select_related('board')
        .order_by('-importance_score', '-created_at')[:80]
    )
    top_ids = {n.pk for n in top_nodes}

    # Step 2: Keyword augmentation — find up to 20 additional nodes whose
    # title or content matches terms from the query.  This ensures lower-
    # importance nodes that are directly relevant to the search are never
    # silently excluded by the rank-based cutoff.
    import re as _re
    raw_keywords = _re.findall(r'[a-zA-Z]{4,}', query_text)[:6]
    if raw_keywords:
        from django.db.models import Q as DQ
        kw_q = DQ()
        for kw in raw_keywords:
            kw_q |= DQ(title__icontains=kw) | DQ(content__icontains=kw)
        extra_nodes = list(
            accessible
            .filter(kw_q)
            .exclude(pk__in=top_ids)
            .select_related('board')
            .order_by('-importance_score', '-created_at')[:20]
        )
    else:
        extra_nodes = []

    nodes = top_nodes + extra_nodes

    if not nodes:
        result = {
            'answer': 'Your organizational memory is empty. Memories are captured automatically as your team works — complete tasks, resolve conflicts, and archive projects to build your knowledge base.',
            'confidence': 'Low',
            'source_node_ids': [],
            'no_data_found': True,
        }
        query_record = OrganizationalMemoryQuery.objects.create(
            asked_by=request.user,
            query_text=query_text,
            response_json=result,
        )
        return JsonResponse({**result, 'query_id': query_record.pk})

    memory_lines = []
    for n in nodes:
        board_name = n.board.name if n.board else 'N/A'
        date_str = n.created_at.strftime('%Y-%m-%d')
        memory_lines.append(
            f"NODE {n.pk}: [{n.node_type}] {n.title} | Project: {board_name} | Date: {date_str}\n{n.content[:500]}"
        )
    memories_text = "\n\n".join(memory_lines)

    # ── Few-shot examples from past helpful answers ───────────────────────────
    # Fetch up to 3 recent queries that the user rated as helpful.  Their Q+A
    # pairs are injected into the system prompt so Gemini can calibrate its
    # answer style and depth to what this team actually found useful.
    good_examples = list(
        OrganizationalMemoryQuery.objects.filter(
            asked_by=request.user,
            was_helpful=True,
        )
        .exclude(query_text=query_text)
        .order_by('-asked_at')[:3]
    )
    few_shot_block = ''
    if good_examples:
        pairs = []
        for ex in good_examples:
            ex_answer = (ex.response_json or {}).get('answer', '').strip()
            if ex.query_text and ex_answer:
                pairs.append(
                    f"Q: {ex.query_text}\nA: {ex_answer[:300]}"
                )
        if pairs:
            few_shot_block = (
                "\n\nExamples of answers your team previously rated as helpful "
                "(use these to calibrate tone and depth — do NOT cite them as sources):\n"
                + "\n\n".join(pairs)
            )

    system_prompt = (
        "You are PrizmAI's organizational memory. You have access to a company's "
        "complete project history — decisions made, lessons learned, outcomes achieved, "
        "risks encountered. Answer questions by finding relevant memories and synthesizing "
        "them into a clear, useful response.\n\n"
        "Rules:\n"
        "- Only use the memory nodes provided. Do not invent information.\n"
        "- Always cite which specific memory nodes your answer draws from (by ID).\n"
        "- If no relevant memories exist, say so honestly — do not make up an answer.\n"
        "- Speak like a knowledgeable colleague, not a database.\n"
        "- Keep answers concise — maximum 4 sentences of synthesis, then list sources.\n"
        + few_shot_block + "\n\n"
        "Return ONLY valid JSON. No markdown, no explanation outside JSON."
    )

    user_prompt = (
        f"Question: {query_text}\n\n"
        f"Available memories:\n{memories_text}\n\n"
        'Return JSON:\n'
        '{\n'
        '  "answer": "Your synthesized answer here",\n'
        '  "confidence": "High" or "Medium" or "Low",\n'
        '  "source_node_ids": [1, 5, 12],\n'
        '  "no_data_found": false\n'
        '}'
    )

    from ai_assistant.utils.ai_router import AIRouter, AIProviderError
    import hashlib

    # Cache the synthesized answer per user+query for an hour. Opening a recent
    # memory re-runs this search; without a cache that re-hits Gemini and burns
    # quota every click. The short TTL bounds staleness if new memories arrive,
    # and also makes repeated identical questions answer consistently.
    cache_key = 'orgmem_search:%s:%s' % (
        request.user.id,
        hashlib.md5(query_text.strip().lower().encode('utf-8')).hexdigest(),
    )
    result = cache.get(cache_key)

    if result is None:
        start_time = time.time()
        router = AIRouter()
        try:
            response = router.complete(
                prompt=user_prompt,
                user=request.user,
                system_prompt=system_prompt,
                complexity='complex',
            )
        except AIProviderError as exc:
            logger.error(f"Organizational memory search AI call failed: {exc}")
            return JsonResponse(
                {'error': 'The AI service is temporarily unavailable. Please try again in a moment.'},
                status=503,
            )
        elapsed_ms = int((time.time() - start_time) * 1000)
        raw_content = response.get('text', '')
        tokens = response.get('tokens_used', 0)

        track_ai_request(
            user=request.user,
            feature='organizational_memory',
            request_type='search',
            ai_model=response.get('model', 'gemini'),
            tokens_used=tokens,
            response_time_ms=elapsed_ms,
        )

        try:
            cleaned = raw_content.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            result = json.loads(cleaned)
        except (json.JSONDecodeError, IndexError):
            result = {
                'answer': raw_content or 'Unable to process your question. Please try rephrasing.',
                'confidence': 'Low',
                'source_node_ids': [],
                'no_data_found': False,
            }

        cache.set(cache_key, result, 3600)

    from django.utils import timezone as tz
    today = tz.now().date()
    existing_query = OrganizationalMemoryQuery.objects.filter(
        asked_by=request.user,
        query_text=query_text,
        asked_at__date=today,
    ).first()
    if existing_query:
        existing_query.response_json = result
        existing_query.asked_at = tz.now()
        existing_query.save(update_fields=['response_json', 'asked_at'])
        query_record = existing_query
    else:
        query_record = OrganizationalMemoryQuery.objects.create(
            asked_by=request.user,
            query_text=query_text,
            response_json=result,
        )

    source_ids = result.get('source_node_ids', [])
    if source_ids:
        referenced_nodes = MemoryNode.objects.filter(pk__in=source_ids)
        query_record.nodes_referenced.set(referenced_nodes)

    source_details = []
    if source_ids:
        for n in MemoryNode.objects.filter(pk__in=source_ids).select_related('board'):
            source_details.append({
                'id': n.pk,
                'title': n.title,
                'board_name': n.board.name if n.board else 'N/A',
                'date': n.created_at.strftime('%b %d, %Y'),
                'node_type': n.get_node_type_display(),
                'has_gaps': n.has_gaps,
            })

    try:
        from kanban.audit_utils import log_audit
        log_audit(
            action_type='memory.search',
            user=request.user,
            request=request,
            message=f"Organizational memory search: {query_text[:80]}",
            additional_data={'query_id': query_record.pk, 'query_text': query_text[:200]},
        )
    except Exception:
        pass

    return JsonResponse({
        'answer': result.get('answer', ''),
        'confidence': result.get('confidence', 'Low'),
        'source_node_ids': source_ids,
        'source_details': source_details,
        'no_data_found': result.get('no_data_found', False),
        'query_id': query_record.pk,
        'remaining_quota': remaining - 1,
    })


# ── View 5: Memory Feedback ─────────────────────────────────────────────────

@login_required
@require_POST
@demo_write_guard
def memory_feedback(request, query_id):
    """Submit feedback (thumbs up/down) on a memory search result.

    Three real effects:
    1. Importance score nudge — cited nodes get +0.03 on thumbs-up, -0.02 on
       thumbs-down (clamped to [0, 1]).  Higher-scored nodes surface earlier in
       future searches, lower-scored ones move down.
    2. Flagging — thumbs-down marks the query as flagged_for_review in its
       response_json so admins / future analysis can audit poor answers.
    3. Few-shot examples — thumbs-up marks the query as a good_example so its
       Q+A pair is injected into the Gemini prompt on future similar searches.
    """
    query_record = get_object_or_404(OrganizationalMemoryQuery, pk=query_id)

    # Tenant isolation: query_id is not covered by the board-access middleware.
    # Feedback nudges cited memory-node importance scores and flags few-shot
    # examples, so only the user who ran the query may submit feedback on it —
    # otherwise a user could enumerate query ids and poison another tenant's
    # memory ranking.
    if query_record.asked_by_id != request.user.id:
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    was_helpful = data.get('was_helpful')
    if was_helpful is None:
        return JsonResponse({'error': 'was_helpful is required.'}, status=400)

    was_helpful = bool(was_helpful)
    query_record.was_helpful = was_helpful

    # ── 1. Importance score nudge on cited nodes ──────────────────────────────
    cited_nodes = list(query_record.nodes_referenced.all())
    delta = 0.03 if was_helpful else -0.02
    for node in cited_nodes:
        new_score = round(min(1.0, max(0.0, node.importance_score + delta)), 4)
        MemoryNode.objects.filter(pk=node.pk).update(importance_score=new_score)

    # ── 2 & 3. Mark query as good example (few-shot) or flagged for review ───
    meta = dict(query_record.response_json) if query_record.response_json else {}
    if was_helpful:
        meta['good_example'] = True
        meta.pop('flagged_for_review', None)
    else:
        meta['flagged_for_review'] = True
        meta['good_example'] = False
    query_record.response_json = meta

    query_record.save(update_fields=['was_helpful', 'response_json'])

    try:
        from kanban.audit_utils import log_audit
        cited_ids = [n.pk for n in cited_nodes]
        log_audit(
            action_type='memory.feedback',
            user=request.user,
            request=request,
            message=f"Memory feedback: {'helpful' if was_helpful else 'not helpful'}",
            additional_data={
                'query_id': query_id,
                'was_helpful': was_helpful,
                'nodes_nudged': cited_ids,
                'importance_delta': delta,
            },
        )
    except Exception:
        pass

    return JsonResponse({'status': 'success'})


# ── View 6: Déjà Vu Check ───────────────────────────────────────────────────

@login_required
@require_GET
def deja_vu_check(request, board_id):
    """Check if similar past projects exist — returns max 3 relevant memories."""
    board = get_object_or_404(Board, id=board_id)

    # RBAC: user must have view permission on the board
    if not request.user.has_perm('prizmai.view_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    cache_key = f'deja_vu_{board_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)

    # Check within user's accessible boards only (not global)
    user_board_ids = _get_user_boards(request.user)
    archived_exists = Board.objects.filter(id__in=user_board_ids, is_archived=True).exists()
    if not archived_exists:
        result = {'results': [], 'reason': 'no_archived_boards'}
        cache.set(cache_key, result, 86400)
        return JsonResponse(result)

    board_ids = _get_user_boards(request.user)

    # Exclude the current board AND its same-name "twins" — boards with the same
    # name that share this board's owner or workspace (e.g. an accidental duplicate
    # or a per-user sandbox copy). Otherwise a board would match its own duplicate
    # and Déjà Vu would surface the project against itself.
    twin_filter = Q()
    if board.owner_id:
        twin_filter |= Q(owner_id=board.owner_id)
    if board.workspace_id:
        twin_filter |= Q(workspace_id=board.workspace_id)
    exclude_board_ids = {board_id}
    if twin_filter:
        exclude_board_ids.update(
            Board.objects.filter(name__iexact=board.name)
            .filter(twin_filter)
            .values_list('id', flat=True)
        )

    past_nodes = (
        MemoryNode.objects
        .filter(
            board_id__in=board_ids,
            node_type__in=['outcome', 'lesson', 'risk_event', 'scope_change'],
            importance_score__gte=0.6,
        )
        .exclude(board_id__in=exclude_board_ids)
        .select_related('board')
        .order_by('-importance_score', '-created_at')[:50]
    )

    if not past_nodes:
        result = {'results': [], 'reason': 'no_past_memories'}
        cache.set(cache_key, result, 86400)
        return JsonResponse(result)

    from api.ai_usage_utils import check_ai_quota, track_ai_request
    has_quota, _, _ = check_ai_quota(request.user)
    if not has_quota:
        result = {'results': [], 'reason': 'quota_exceeded'}
        cache.set(cache_key, result, 3600)
        return JsonResponse(result)

    board_desc = f"Board: {board.name}\nDescription: {board.description or 'No description'}"
    if board.strategy:
        board_desc += f"\nStrategy: {board.strategy.name}"
        if board.strategy.mission:
            board_desc += f"\nMission: {board.strategy.mission.name}"

    nodes_text = "\n".join(
        f"NODE {n.pk}: [{n.node_type}] {n.title} | Project: {n.board.name if n.board else 'N/A'} | {n.created_at.strftime('%Y-%m-%d')}\n{n.content[:200]}"
        for n in past_nodes
    )

    system_prompt = (
        "You are a project similarity analyst. Given a new project description and a list of "
        "past project memories, identify the most relevant past experiences. Only return matches "
        "that would genuinely help the project manager — not superficial word matches.\n\n"
        "Return ONLY valid JSON. No markdown, no explanation outside JSON."
    )
    user_prompt = (
        f"NEW PROJECT:\n{board_desc}\n\n"
        f"PAST PROJECT MEMORIES:\n{nodes_text}\n\n"
        "Return JSON:\n"
        '{\n'
        '  "similar_nodes": [\n'
        '    {"node_id": 123, "relevance_reason": "One sentence why this is relevant"}\n'
        '  ]\n'
        '}\n'
        "Return maximum 3 matches. Return empty array if nothing is truly relevant."
    )

    from ai_assistant.utils.ai_router import AIRouter, AIProviderError
    start_time = time.time()

    router = AIRouter()
    try:
        response = router.complete(
            prompt=user_prompt,
            user=request.user,
            system_prompt=system_prompt,
            complexity='simple',
        )
    except AIProviderError as exc:
        logger.error(f"Deja Vu similarity check AI call failed: {exc}")
        # Don't cache transient AI outages — let the next check retry.
        return JsonResponse({'results': [], 'reason': 'ai_unavailable'})
    elapsed_ms = int((time.time() - start_time) * 1000)

    track_ai_request(
        user=request.user,
        feature='deja_vu',
        request_type='similarity_check',
        board_id=board_id,
        ai_model=response.get('model', 'gemini'),
        tokens_used=response.get('tokens_used', 0),
        response_time_ms=elapsed_ms,
    )

    raw = response.get('text', '')
    try:
        cleaned = raw.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
    except (json.JSONDecodeError, IndexError):
        parsed = {'similar_nodes': []}

    similar = parsed.get('similar_nodes', [])[:3]

    results = []
    for match in similar:
        node_id = match.get('node_id')
        if not node_id:
            continue
        try:
            node = MemoryNode.objects.select_related('board').get(pk=node_id)
            results.append({
                'id': node.pk,
                'title': node.title,
                'content': node.content[:300],
                'board_name': node.board.name if node.board else 'N/A',
                'date': node.created_at.strftime('%b %d, %Y'),
                'node_type': node.get_node_type_display(),
                'relevance_reason': match.get('relevance_reason', ''),
            })
        except MemoryNode.DoesNotExist:
            continue

    result = {'results': results}
    cache.set(cache_key, result, 86400)
    return JsonResponse(result)
