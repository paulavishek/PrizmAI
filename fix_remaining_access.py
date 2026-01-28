"""
Fix remaining access restrictions in view files
"""
import re

# Files to fix
files = [
    'kanban/retrospective_views.py',
    'kanban/conflict_views.py',
    'kanban/permission_views.py',
]

for filepath in files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Pattern 1: if not (request.user == board.created_by or request.user in board.members.all()):
        #             return JsonResponse({'error': 'Permission denied'}, status=403)
        content = re.sub(
            r"if not \(request\.user == board\.created_by or request\.user in board\.members\.all\(\)\):\s*\n\s*return JsonResponse\(\{'error': 'Permission denied'\}, status=403\)",
            "# Access restriction removed - all authenticated users can access",
            content
        )
        
        # Pattern 2: Similar with HttpResponseForbidden  
        content = re.sub(
            r'if not \(request\.user == board\.created_by or request\.user in board\.members\.all\(\)\):\s*\n\s*return HttpResponseForbidden\("You don\'t have access to this board"\)',
            "# Access restriction removed - all authenticated users can access",
            content
        )
        
        # Pattern 3: Conflict variant
        content = re.sub(
            r'if not \(request\.user == board\.created_by or request\.user in board\.members\.all\(\)\):\s*\n\s*return HttpResponseForbidden\("You don\'t have access to this conflict"\)',
            "# Access restriction removed - all authenticated users can access",
            content
        )
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'Modified: {filepath}')
        else:
            print(f'No changes: {filepath}')
            
    except Exception as e:
        print(f'Error processing {filepath}: {e}')

print('Done!')
