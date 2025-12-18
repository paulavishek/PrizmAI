#!/usr/bin/env python
"""
Test effectiveness calculation for Software Project board
"""
from kanban.models import Board
from kanban.utils.feedback_learning import FeedbackLearningSystem
from django.contrib.auth.models import User

# Get board and user
board = Board.objects.get(id=18)
user = User.objects.get(username='user7')

# Calculate effectiveness
learning_system = FeedbackLearningSystem()
effectiveness = learning_system.calculate_pm_coaching_effectiveness(
    board, user, days=30
)

print("\n" + "="*80)
print("EFFECTIVENESS CALCULATION TEST")
print("="*80)
print(f"\nBoard: {board.name}")
print(f"User: {user.username}")
print("\nEffectiveness Dictionary:")
for key, value in effectiveness.items():
    print(f"  {key}: {value}")

print("\n" + "="*80)
