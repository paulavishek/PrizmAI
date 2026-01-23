"""
Universal AI Coach Suggestion Regeneration Tool

Regenerates AI-enhanced suggestions for any board(s).
Works for all board types: Software Development, Marketing Campaign, Bug Tracking, etc.

Usage:
    # Regenerate for specific board
    python regenerate_ai_suggestions_universal.py --board "Marketing Campaign"
    
    # Regenerate for all demo boards
    python regenerate_ai_suggestions_universal.py --all-demo
    
    # Regenerate for all boards
    python regenerate_ai_suggestions_universal.py --all
"""

import django
import os
import argparse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion
from kanban.models import Board, Task
from kanban.utils.coaching_rules import CoachingRuleEngine
from kanban.utils.ai_coach_service import AICoachService
from django.db.models import Count


def regenerate_board_suggestions(board, ai_coach):
    """Regenerate AI-enhanced suggestions for a board"""
    
    print(f"\n{'='*80}")
    print(f"Processing: {board.name}")
    print(f"{'='*80}\n")
    
    # Count before
    before_count = CoachingSuggestion.objects.filter(board=board).count()
    before_ai = CoachingSuggestion.objects.filter(
        board=board, 
        generation_method='hybrid'
    ).count()
    
    print(f"Before:")
    print(f"  Total: {before_count} suggestions")
    print(f"  AI-enhanced: {before_ai}")
    print(f"  Rule-only: {before_count - before_ai}\n")
    
    # Delete existing
    if before_count > 0:
        deleted = CoachingSuggestion.objects.filter(board=board).delete()
        print(f"✓ Deleted {deleted[0]} old suggestions\n")
    
    # Generate new suggestions
    print(f"Generating new suggestions...")
    rule_engine = CoachingRuleEngine(board)
    suggestions_data = rule_engine.analyze_and_generate_suggestions()
    
    print(f"✓ Rule engine generated {len(suggestions_data)} suggestions\n")
    
    if not suggestions_data:
        print(f"⚠️  No suggestions generated (board may not have issues to detect)\n")
        return 0, 0
    
    # Create context
    context = {
        'board_name': board.name,
        'team_size': board.members.count(),
        'active_tasks': Task.objects.filter(
            column__board=board, 
            progress__isnull=False, 
            progress__lt=100
        ).count(),
        'project_phase': 'active',
    }
    
    # Enhance and create
    created_count = 0
    enhanced_count = 0
    
    for suggestion_data in suggestions_data:
        try:
            # Enhance with AI
            title_preview = suggestion_data['title'][:60]
            print(f"  Enhancing: {title_preview}...")
            
            enhanced_data = ai_coach.enhance_suggestion_with_ai(
                suggestion_data, context
            )
            
            if enhanced_data.get('generation_method') == 'hybrid':
                enhanced_count += 1
                print(f"    ✓ Enhanced with AI")
            else:
                print(f"    ⚠️  Using basic format")
            
            # Create
            CoachingSuggestion.objects.create(**enhanced_data)
            created_count += 1
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            continue
    
    print(f"\nAfter:")
    print(f"  Created: {created_count} suggestions")
    print(f"  AI-enhanced: {enhanced_count}")
    if created_count > 0:
        print(f"  Success rate: {(enhanced_count/created_count*100):.1f}%")
    
    return created_count, enhanced_count


def main():
    parser = argparse.ArgumentParser(
        description='Regenerate AI-enhanced suggestions for boards'
    )
    parser.add_argument(
        '--board',
        type=str,
        help='Board name to regenerate (e.g., "Marketing Campaign")'
    )
    parser.add_argument(
        '--board-id',
        type=int,
        help='Board ID to regenerate'
    )
    parser.add_argument(
        '--all-demo',
        action='store_true',
        help='Regenerate all official demo boards'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Regenerate ALL boards (use with caution)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("AI Coach Suggestion Regeneration Tool")
    print("="*80)
    
    # Initialize AI service
    ai_coach = AICoachService()
    
    if not ai_coach.gemini_available:
        print("\n❌ AI Coach service not available.")
        print("   Please configure GEMINI_API_KEY in settings.\n")
        return
    
    print("\n✅ AI Coach service is available (Gemini AI)")
    
    # Determine which boards to process
    boards = []
    
    if args.board:
        board = Board.objects.filter(name__iexact=args.board).first()
        if board:
            boards = [board]
        else:
            print(f"\n❌ Board '{args.board}' not found")
            print("\nAvailable boards:")
            for b in Board.objects.all():
                print(f"  - {b.name}")
            return
    
    elif args.board_id:
        board = Board.objects.filter(id=args.board_id).first()
        if board:
            boards = [board]
        else:
            print(f"\n❌ Board ID {args.board_id} not found")
            return
    
    elif args.all_demo:
        boards = Board.objects.filter(is_official_demo_board=True)
        print(f"\nProcessing {boards.count()} official demo boards")
    
    elif args.all:
        boards = Board.objects.all()
        print(f"\n⚠️  Processing ALL {boards.count()} boards")
        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Cancelled")
            return
    
    else:
        print("\n❌ No boards specified")
        print("\nUsage:")
        print('  python regenerate_ai_suggestions_universal.py --board "Marketing Campaign"')
        print('  python regenerate_ai_suggestions_universal.py --board-id 2')
        print('  python regenerate_ai_suggestions_universal.py --all-demo')
        print('  python regenerate_ai_suggestions_universal.py --all')
        return
    
    if not boards:
        print("\n❌ No boards to process")
        return
    
    # Process boards
    total_created = 0
    total_enhanced = 0
    
    for board in boards:
        created, enhanced = regenerate_board_suggestions(board, ai_coach)
        total_created += created
        total_enhanced += enhanced
    
    # Summary
    print("\n" + "="*80)
    print("✅ Regeneration Complete!")
    print("="*80)
    print(f"\nTotal Summary:")
    print(f"  Boards processed: {len(boards)}")
    print(f"  Suggestions created: {total_created}")
    print(f"  AI-enhanced: {total_enhanced}")
    if total_created > 0:
        print(f"  Overall success rate: {(total_enhanced/total_created*100):.1f}%")
    
    print(f"\nNext steps:")
    print(f"  1. Refresh the AI Coach dashboard in your browser")
    print(f"  2. Verify suggestions are detailed and actionable")
    print(f"  3. Check that 'Why this matters' and actions are present\n")


if __name__ == '__main__':
    main()
