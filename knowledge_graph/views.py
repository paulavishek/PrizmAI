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
    org-wide memories within their own organization.

    Org-wide scoping goes through board → workspace → organization so it never
    leaks across tenants.
    """
    board_ids = _get_user_boards(user)
    visibility = Q(board_id__in=board_ids)
    org_id = getattr(getattr(user, 'profile', None), 'organization_id', None)
    if org_id:
        visibility |= Q(is_org_wide=True, board__workspace__organization_id=org_id)
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


def _can_manage_memory(request, node):
    """True if the user may edit/delete this manual memory.

    Rule: never auto-captured (system) memories; then creator, or an
    Owner/Org-Admin-level overseer (invite_board_member perm), or demo sandbox.
    """
    if node.is_auto_captured or node.board is None:
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
    """Edit a manually-logged memory. Creator or Owner/Org-Admin only;
    never auto-captured (system) memories."""
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
    # Title is optional — derive a clean one from the content when omitted.
    if not title:
        title = _derive_title(content)

    if node_type not in ALLOWED_MANUAL_TYPES:
        node_type = 'decision'

    node.title = title[:200]
    node.content = content
    node.node_type = node_type
    node.tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    # Org-wide visibility is privileged — only Owners/Org Admins may change it.
    if request.user.has_perm('prizmai.invite_board_member', node.board):
        node.is_org_wide = bool(data.get('is_org_wide'))
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
    nodes = nodes_qs[offset:offset + PER_PAGE]
    has_more = (offset + PER_PAGE) < total

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
    past_nodes = (
        MemoryNode.objects
        .filter(
            board_id__in=board_ids,
            node_type__in=['outcome', 'lesson', 'risk_event', 'scope_change'],
            importance_score__gte=0.6,
        )
        .exclude(board_id=board_id)
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
