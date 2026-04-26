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

    if not title or not content:
        return JsonResponse({'error': 'Title and content are required.'}, status=400)

    if node_type not in ('decision', 'manual_log'):
        node_type = 'decision'

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


# ── View 3: Organizational Memory Page ──────────────────────────────────────

@login_required
def organizational_memory(request):
    """Organizational Memory page — the global search interface."""
    board_ids = _get_user_boards(request.user)

    total_nodes = MemoryNode.objects.filter(
        Q(board__isnull=True) | Q(board_id__in=board_ids)
    ).count()

    boards_count = Board.objects.filter(id__in=board_ids).count()

    oldest = MemoryNode.objects.filter(
        Q(board__isnull=True) | Q(board_id__in=board_ids)
    ).order_by('created_at').values_list('created_at', flat=True).first()

    recent_queries = OrganizationalMemoryQuery.objects.filter(
        asked_by=request.user
    ).order_by('-asked_at')[:5]

    context = {
        'total_nodes': total_nodes,
        'boards_count': boards_count,
        'oldest_memory_date': oldest,
        'recent_queries': recent_queries,
    }
    return render(request, 'knowledge_graph/organizational_memory.html', context)


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

    board_ids = _get_user_boards(request.user)
    nodes = (
        MemoryNode.objects
        .filter(Q(board__isnull=True) | Q(board_id__in=board_ids))
        .select_related('board')
        .order_by('-importance_score', '-created_at')[:100]
    )

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
            f"NODE {n.pk}: [{n.node_type}] {n.title} | Project: {board_name} | Date: {date_str}\n{n.content[:300]}"
        )
    memories_text = "\n\n".join(memory_lines)

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
        "- Keep answers concise — maximum 4 sentences of synthesis, then list sources.\n\n"
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

    from ai_assistant.utils.ai_clients import GeminiClient
    start_time = time.time()

    client = GeminiClient()
    response = client.get_response(
        prompt=user_prompt,
        system_prompt=system_prompt,
        task_complexity='complex',
        temperature=0.3,
    )

    elapsed_ms = int((time.time() - start_time) * 1000)
    raw_content = response.get('content', '')
    tokens = response.get('tokens', 0)

    track_ai_request(
        user=request.user,
        feature='organizational_memory',
        request_type='search',
        ai_model=response.get('model_used', 'gemini'),
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
    """Submit feedback (thumbs up/down) on a memory search result."""
    query_record = get_object_or_404(OrganizationalMemoryQuery, pk=query_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    was_helpful = data.get('was_helpful')
    if was_helpful is None:
        return JsonResponse({'error': 'was_helpful is required.'}, status=400)

    query_record.was_helpful = bool(was_helpful)
    query_record.save(update_fields=['was_helpful'])

    try:
        from kanban.audit_utils import log_audit
        log_audit(
            action_type='memory.feedback',
            user=request.user,
            request=request,
            message=f"Memory feedback: {'helpful' if was_helpful else 'not helpful'}",
            additional_data={'query_id': query_id, 'was_helpful': was_helpful},
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
            Q(board__isnull=True) | Q(board_id__in=board_ids),
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

    from ai_assistant.utils.ai_clients import GeminiClient
    start_time = time.time()

    client = GeminiClient(default_model='gemini-2.5-flash-lite')
    response = client.get_response(
        prompt=user_prompt,
        system_prompt=system_prompt,
        task_complexity='simple',
        temperature=0.3,
    )

    elapsed_ms = int((time.time() - start_time) * 1000)

    track_ai_request(
        user=request.user,
        feature='deja_vu',
        request_type='similarity_check',
        board_id=board_id,
        ai_model=response.get('model_used', 'gemini'),
        tokens_used=response.get('tokens', 0),
        response_time_ms=elapsed_ms,
    )

    raw = response.get('content', '')
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
