#!/usr/bin/env python
"""
Remove all board-level access restrictions from the codebase.
This script removes permission checks that restrict users based on board membership.

After this change, all authenticated users can access all features.
"""
import os
import re

# Files to process
FILES_TO_FIX = [
    'kanban/api_views.py',
    'kanban/views.py',
    'kanban/budget_views.py',
    'kanban/burndown_views.py',
    'kanban/coach_views.py',
    'kanban/forecasting_views.py',
    'messaging/views.py',
    'webhooks/views.py',
    'wiki/api_views.py',
    'wiki/views.py',
    'api/v1/views.py',
]

# Patterns to find and comment out (board membership checks)
PATTERNS_TO_REMOVE = [
    # Pattern 1: if not (board.created_by == request.user or request.user in board.members.all()):
    #     return JsonResponse({'error': 'Access denied'}, status=403)
    (
        r"(\s*)if not \(board\.created_by == request\.user or request\.user in board\.members\.all\(\)\):\s*\n\s*return JsonResponse\(\{'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 2: if not (board.created_by == request.user or request.user in board.members.all()):
    #     return HttpResponseForbidden(...)
    (
        r"(\s*)if not \(board\.created_by == request\.user or request\.user in board\.members\.all\(\)\):\s*\n\s*return HttpResponseForbidden\([^)]+\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 3: if request.user not in board.members.all() and board.created_by != request.user:
    #     return JsonResponse({'error': 'Access denied'}, status=403)
    (
        r"(\s*)if request\.user not in board\.members\.all\(\) and board\.created_by != request\.user:\s*\n\s*return JsonResponse\(\{'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 4: if not request.user in board.members.all() and board.created_by != request.user:
    (
        r"(\s*)if not request\.user in board\.members\.all\(\) and board\.created_by != request\.user:\s*\n\s*return JsonResponse\(\{'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 5: if not (request.user in board.members.all() or board.created_by == request.user):
    (
        r"(\s*)if not \(request\.user in board\.members\.all\(\) or board\.created_by == request\.user\):\s*\n\s*return JsonResponse\(\{'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 6: task.column.board.members.all() checks
    (
        r"(\s*)if not request\.user in task\.column\.board\.members\.all\(\) and task\.column\.board\.created_by != request\.user:\s*\n\s*return JsonResponse\(\{'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: task board membership check removed"
    ),
    # Pattern 7: if request.user not in task.column.board.members.all():
    (
        r"(\s*)if request\.user not in task\.column\.board\.members\.all\(\):\s*\n\s*return JsonResponse\(\{'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: task board membership check removed"
    ),
    # Pattern 8: if request.user not in board.members.all():
    (
        r"(\s*)if request\.user not in board\.members\.all\(\):\s*\n\s*return JsonResponse\(\{'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 9: JsonResponse with success: False
    (
        r"(\s*)if not \(board\.created_by == request\.user or request\.user in board\.members\.all\(\)\):\s*\n\s*return JsonResponse\(\{'success': False, 'error': 'Access denied'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 10: board.created_by != request.user check alone
    (
        r"(\s*)if board\.created_by != request\.user:\s*\n\s*return JsonResponse\(\{'error': '[^']+'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board creator check removed"
    ),
    # Pattern 11: webhooks pattern with board.members.filter
    (
        r"(\s*)if not \(board\.created_by == request\.user or board\.members\.filter\(id=request\.user\.id\)\.exists\(\)\):\s*\n\s*return JsonResponse\(\{'error': '[^']+'\}, status=403\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 12: messaging views pattern
    (
        r"(\s*)if request\.user not in board\.members\.all\(\):\s*\n\s*return redirect\('board_list'\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 13: messaging views with != board.created_by
    (
        r"(\s*)if request\.user != board\.created_by and request\.user not in board\.members\.all\(\):\s*\n\s*return redirect\('board_list'\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 14: HttpResponseForbidden
    (
        r"(\s*)if not \(board\.created_by == request\.user or request\.user in board\.members\.all\(\)\):\s*\n\s*return HttpResponseForbidden\(\"[^\"]+\"\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
    # Pattern 15: with messages.error
    (
        r"(\s*)if request\.user not in board\.members\.all\(\) and board\.created_by != request\.user:\s*\n\s*messages\.error\([^)]+\)\s*\n\s*return redirect\([^)]+\)",
        r"\1# Access restriction removed - all authenticated users can access\n\1pass  # Original: board membership check removed"
    ),
]

def process_file(filepath):
    """Process a single file to remove access restrictions."""
    if not os.path.exists(filepath):
        print(f"  ⚠️  File not found: {filepath}")
        return 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = 0
    
    for pattern, replacement in PATTERNS_TO_REMOVE:
        new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if count > 0:
            content = new_content
            changes_made += count
    
    if changes_made > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ {filepath}: {changes_made} access checks removed")
    else:
        print(f"  ℹ️  {filepath}: No matching patterns found (may need manual review)")
    
    return changes_made

def main():
    print("=" * 70)
    print("REMOVING BOARD-LEVEL ACCESS RESTRICTIONS")
    print("=" * 70)
    print("\nThis will remove all board membership checks from the codebase.")
    print("All authenticated users will be able to access all features.\n")
    
    total_changes = 0
    
    for filepath in FILES_TO_FIX:
        changes = process_file(filepath)
        total_changes += changes
    
    print("\n" + "=" * 70)
    print(f"COMPLETED: {total_changes} access restrictions removed")
    print("=" * 70)
    print("\nNote: Some files may need manual review for complex patterns.")
    print("Run 'python manage.py runserver' and test thoroughly.")

if __name__ == '__main__':
    main()
