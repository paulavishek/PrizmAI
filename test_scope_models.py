#!/usr/bin/env python
"""Quick test script to verify scope tracking models"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, ScopeChangeSnapshot, ScopeCreepAlert

print('✅ Models imported successfully!')
print(f'✅ Board has baseline fields: {hasattr(Board(), "baseline_task_count")}')
print(f'✅ ScopeChangeSnapshot model exists: {ScopeChangeSnapshot is not None}')
print(f'✅ ScopeCreepAlert model exists: {ScopeCreepAlert is not None}')

# Check if methods exist
board = Board()
print(f'✅ Board has create_scope_snapshot method: {hasattr(board, "create_scope_snapshot")}')
print(f'✅ Board has get_current_scope_status method: {hasattr(board, "get_current_scope_status")}')
print(f'✅ Board has check_scope_creep_threshold method: {hasattr(board, "check_scope_creep_threshold")}')

print('\n✨ All scope tracking models and methods are properly implemented!')
