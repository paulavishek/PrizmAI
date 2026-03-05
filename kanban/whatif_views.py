"""
What-If Scenario Analyzer Views

Provides the dashboard page, simulation endpoint, and scenario persistence
for the What-If Scenario Analyzer feature.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from kanban.models import Board
from kanban.whatif_models import WhatIfScenario
from kanban.utils.whatif_engine import WhatIfEngine

logger = logging.getLogger(__name__)


@login_required
def whatif_dashboard(request, board_id):
    """Render the What-If Scenario Analyzer page with current board state."""
    board = get_object_or_404(Board, id=board_id)
    engine = WhatIfEngine(board)
    baseline = engine._capture_baseline()

    saved_scenarios = WhatIfScenario.objects.filter(
        board=board,
    ).order_by('-is_starred', '-created_at')[:10]

    context = {
        'board': board,
        'baseline': baseline,
        'baseline_json': json.dumps(baseline),
        'saved_scenarios': saved_scenarios,
    }
    return render(request, 'kanban/whatif_dashboard.html', context)


@login_required
@require_POST
def whatif_simulate(request, board_id):
    """Run a what-if simulation and return JSON results."""
    board = get_object_or_404(Board, id=board_id)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    params = {
        'tasks_added': body.get('tasks_added', 0),
        'team_size_delta': body.get('team_size_delta', 0),
        'deadline_shift_days': body.get('deadline_shift_days', 0),
    }

    engine = WhatIfEngine(board)
    results = engine.simulate(params)

    # Optional AI analysis
    if body.get('include_ai'):
        ai = engine.analyze_with_ai(params, results)
        results['ai_analysis'] = ai

    return JsonResponse({'success': True, 'results': results})


@login_required
@require_POST
def whatif_save(request, board_id):
    """Persist a what-if scenario for later comparison."""
    board = get_object_or_404(Board, id=board_id)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    name = body.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Scenario name is required.'}, status=400)

    # Determine scenario type
    params = body.get('input_parameters', {})
    scenario_type = 'combined'
    changes = [
        params.get('tasks_added', 0) != 0,
        params.get('team_size_delta', 0) != 0,
        params.get('deadline_shift_days', 0) != 0,
    ]
    if sum(changes) == 1:
        if params.get('tasks_added', 0) != 0:
            scenario_type = 'scope_change'
        elif params.get('team_size_delta', 0) != 0:
            scenario_type = 'team_change'
        else:
            scenario_type = 'deadline_change'

    scenario = WhatIfScenario.objects.create(
        board=board,
        created_by=request.user,
        name=name,
        scenario_type=scenario_type,
        input_parameters=params,
        baseline_snapshot=body.get('baseline_snapshot', {}),
        impact_results=body.get('impact_results', {}),
        ai_analysis=body.get('ai_analysis', {}),
    )

    return JsonResponse({
        'success': True,
        'scenario_id': scenario.id,
        'name': scenario.name,
    })


@login_required
def whatif_history(request, board_id):
    """Return saved scenarios for a board as JSON."""
    board = get_object_or_404(Board, id=board_id)

    scenarios = WhatIfScenario.objects.filter(board=board).order_by('-is_starred', '-created_at')[:20]
    data = []
    for s in scenarios:
        params = s.input_parameters or {}
        results = s.impact_results or {}
        projected = results.get('projected', {})
        data.append({
            'id': s.id,
            'name': s.name,
            'scenario_type': s.get_scenario_type_display(),
            'created_at': s.created_at.strftime('%b %d, %Y %H:%M'),
            'is_starred': s.is_starred,
            'input_parameters': params,
            'delay_probability': projected.get('delay_probability', '—'),
            'risk_level': projected.get('risk_level', '—'),
            'feasibility_score': results.get('feasibility_score', '—'),
        })

    return JsonResponse({'success': True, 'scenarios': data})


@login_required
@require_POST
def whatif_delete(request, board_id, scenario_id):
    """Delete a saved what-if scenario."""
    scenario = get_object_or_404(
        WhatIfScenario, id=scenario_id, board_id=board_id,
    )
    scenario.delete()
    return JsonResponse({'success': True})
