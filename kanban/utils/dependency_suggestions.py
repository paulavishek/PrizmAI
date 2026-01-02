# kanban/utils/dependency_suggestions.py
"""
AI-powered task dependency analysis and suggestion engine
Analyzes task descriptions to suggest parent-child relationships and task dependencies
"""

import json
import logging
from typing import List, Dict, Optional
from django.utils import timezone
from kanban.models import Task

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Analyzes task descriptions to suggest dependencies
    Uses NLP and keyword matching to find related tasks
    """
    
    # Keywords that indicate parent-child relationships
    PARENT_KEYWORDS = ['implement', 'setup', 'configure', 'initialize', 'design', 'architect', 'plan']
    CHILD_KEYWORDS = ['test', 'validate', 'verify', 'debug', 'fix', 'optimize', 'refactor']
    DEPENDENCY_KEYWORDS = ['requires', 'depends on', 'after', 'once', 'following', 'completion']
    BLOCKING_KEYWORDS = ['blocks', 'blocked by', 'waiting for', 'pending']
    
    @staticmethod
    def analyze_task_description(task: Task, board=None) -> Dict:
        """
        Analyze a task's description to suggest dependencies
        
        Args:
            task: The Task object to analyze
            board: Optional board to limit search scope
            
        Returns:
            Dictionary with suggested dependencies and confidence scores
        """
        if not task.description:
            return {
                'parent_suggestions': [],
                'related_suggestions': [],
                'blocking_suggestions': [],
                'confidence': 0,
                'analysis': 'No description provided for analysis'
            }
        
        try:
            # Tokenize and prepare text
            description_lower = task.description.lower()
            
            # Find similar tasks in the same column or board
            if board:
                other_tasks = Task.objects.filter(column__board=board).exclude(id=task.id)
            else:
                other_tasks = Task.objects.filter(column=task.column).exclude(id=task.id)
            
            parent_suggestions = []
            related_suggestions = []
            blocking_suggestions = []
            
            # Analyze each other task
            for other_task in other_tasks:
                if not other_task.description:
                    continue
                
                other_desc_lower = other_task.description.lower()
                
                # Check for parent-child relationships
                parent_score = DependencyAnalyzer._calculate_parent_relationship_score(
                    description_lower, other_desc_lower, task, other_task
                )
                
                if parent_score > 0.5:
                    # Generate detailed reasoning for explainability
                    parent_reasoning = DependencyAnalyzer._generate_parent_reasoning(
                        task, other_task, parent_score
                    )
                    parent_suggestions.append({
                        'task_id': other_task.id,
                        'task_title': other_task.title,
                        'confidence': round(parent_score, 2),
                        'confidence_level': 'high' if parent_score > 0.8 else 'medium' if parent_score > 0.6 else 'low',
                        'reason': 'Task appears to be a prerequisite',
                        'reasoning_details': parent_reasoning,
                        'relationship_type': 'parent-child',
                        'impact_if_linked': 'This task would need to complete before the current task can start'
                    })
                
                # Check for related tasks
                related_score = DependencyAnalyzer._calculate_relatedness_score(
                    description_lower, other_desc_lower
                )
                
                if related_score > 0.6:
                    # Generate detailed reasoning for explainability
                    related_reasoning = DependencyAnalyzer._generate_relatedness_reasoning(
                        task, other_task, related_score
                    )
                    related_suggestions.append({
                        'task_id': other_task.id,
                        'task_title': other_task.title,
                        'confidence': round(related_score, 2),
                        'confidence_level': 'high' if related_score > 0.8 else 'medium' if related_score > 0.7 else 'low',
                        'reason': 'Tasks share similar context or requirements',
                        'reasoning_details': related_reasoning,
                        'relationship_type': 'related',
                        'impact_if_linked': 'Linking allows tracking related work and potential coordination'
                    })
                
                # Check for blocking relationships
                blocking_score = DependencyAnalyzer._calculate_blocking_score(
                    description_lower, other_desc_lower
                )
                
                if blocking_score > 0.6:
                    # Generate detailed reasoning for explainability
                    blocking_reasoning = DependencyAnalyzer._generate_blocking_reasoning(
                        task, other_task, blocking_score
                    )
                    blocking_suggestions.append({
                        'task_id': other_task.id,
                        'task_title': other_task.title,
                        'confidence': round(blocking_score, 2),
                        'confidence_level': 'high' if blocking_score > 0.8 else 'medium' if blocking_score > 0.7 else 'low',
                        'reason': 'This task may be blocked by or block the other task',
                        'reasoning_details': blocking_reasoning,
                        'relationship_type': 'blocking',
                        'impact_if_linked': 'Creates a dependency chain that affects scheduling'
                    })
            
            # Sort by confidence and limit results
            parent_suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            related_suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            blocking_suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            
            overall_confidence = max(
                [s['confidence'] for s in parent_suggestions] +
                [s['confidence'] for s in related_suggestions] +
                [s['confidence'] for s in blocking_suggestions] +
                [0]
            )
            
            # Build explainability summary
            explainability = {
                'analysis_method': 'Keyword matching and semantic analysis',
                'factors_analyzed': [
                    'Task title and description similarity',
                    'Dependency keywords (requires, depends on, after, etc.)',
                    'Blocking keywords (blocks, waiting for, etc.)',
                    'Column position in workflow',
                    'Parent/child keyword patterns'
                ],
                'assumptions': [
                    'Tasks in earlier workflow columns may be prerequisites',
                    'Explicit dependency language indicates relationships',
                    'Similar content suggests related work'
                ],
                'limitations': [
                    'Analysis is based on text patterns, not semantic understanding',
                    'May miss implicit dependencies not mentioned in descriptions',
                    'Confidence decreases with sparse descriptions'
                ]
            }
            
            return {
                'parent_suggestions': parent_suggestions[:3],  # Top 3 suggestions
                'related_suggestions': related_suggestions[:3],
                'blocking_suggestions': blocking_suggestions[:3],
                'confidence': round(overall_confidence, 2),
                'confidence_level': 'high' if overall_confidence > 0.8 else 'medium' if overall_confidence > 0.6 else 'low',
                'analysis': f"Found {len(parent_suggestions)} potential parent tasks, "
                          f"{len(related_suggestions)} related tasks, and "
                          f"{len(blocking_suggestions)} potentially blocking tasks",
                'explainability': explainability,
                'total_tasks_analyzed': other_tasks.count(),
                'recommendations': DependencyAnalyzer._generate_recommendations(
                    parent_suggestions, related_suggestions, blocking_suggestions
                )
            }
        
        except Exception as e:
            logger.error(f"Error analyzing task dependencies: {str(e)}")
            return {
                'parent_suggestions': [],
                'related_suggestions': [],
                'blocking_suggestions': [],
                'confidence': 0,
                'analysis': f'Error during analysis: {str(e)}'
            }
    
    @staticmethod
    def _calculate_parent_relationship_score(desc1: str, desc2: str, task1: Task, task2: Task) -> float:
        """Calculate probability that task2 is a parent of task1"""
        score = 0
        
        # Check if desc1 contains parent keywords and desc2 contains child keywords
        task1_has_child_keywords = any(keyword in desc1 for keyword in DependencyAnalyzer.CHILD_KEYWORDS)
        task2_has_parent_keywords = any(keyword in desc2 for keyword in DependencyAnalyzer.PARENT_KEYWORDS)
        
        if task1_has_child_keywords and task2_has_parent_keywords:
            score += 0.4
        
        # Check for explicit dependency mentions
        for keyword in DependencyAnalyzer.DEPENDENCY_KEYWORDS:
            if keyword in desc1 and task2.title.lower() in desc1:
                score += 0.3
        
        # Check column position (earlier columns might indicate parent tasks)
        if task2.column and task1.column:
            if task2.column.position < task1.column.position:
                score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def _calculate_relatedness_score(desc1: str, desc2: str) -> float:
        """Calculate how related two tasks are based on descriptions"""
        score = 0
        
        # Simple word overlap scoring
        words1 = set(desc1.split())
        words2 = set(desc2.split())
        
        if len(words1) > 0 and len(words2) > 0:
            overlap = len(words1.intersection(words2))
            total = len(words1.union(words2))
            score = overlap / total if total > 0 else 0
        
        return score
    
    @staticmethod
    def _calculate_blocking_score(desc1: str, desc2: str) -> float:
        """Calculate if one task blocks the other"""
        score = 0
        
        # Check for explicit blocking keywords
        for keyword in DependencyAnalyzer.BLOCKING_KEYWORDS:
            if keyword in desc1:
                score += 0.3
        
        return min(score, 1.0)
    
    @staticmethod
    def _generate_parent_reasoning(task, parent_task, score) -> Dict:
        """Generate detailed reasoning for parent relationship suggestion"""
        factors = []
        
        # Check for keyword matches
        task_desc = task.description.lower() if task.description else ''
        parent_desc = parent_task.description.lower() if parent_task.description else ''
        
        if any(kw in task_desc for kw in DependencyAnalyzer.CHILD_KEYWORDS):
            factors.append({
                'factor': 'Child task indicators',
                'contribution': 40,
                'detail': 'Task contains keywords like "test", "validate", "fix" suggesting it follows another task'
            })
        
        if any(kw in parent_desc for kw in DependencyAnalyzer.PARENT_KEYWORDS):
            factors.append({
                'factor': 'Parent task indicators',
                'contribution': 30,
                'detail': 'Suggested parent contains keywords like "implement", "setup", "design" suggesting prerequisite work'
            })
        
        if task.column and parent_task.column and parent_task.column.position < task.column.position:
            factors.append({
                'factor': 'Workflow position',
                'contribution': 20,
                'detail': f'Parent task is in earlier column ({parent_task.column.name}) suggesting it should complete first'
            })
        
        return {
            'contributing_factors': factors,
            'summary': f"This task appears to depend on '{parent_task.title}' based on {len(factors)} factor(s)",
            'confidence_explanation': 'high' if score > 0.8 else 'medium' if score > 0.6 else 'low' + ' confidence based on keyword and workflow analysis'
        }
    
    @staticmethod
    def _generate_relatedness_reasoning(task, related_task, score) -> Dict:
        """Generate detailed reasoning for related task suggestion"""
        task_desc = task.description.lower() if task.description else ''
        related_desc = related_task.description.lower() if related_task.description else ''
        
        words1 = set(task_desc.split())
        words2 = set(related_desc.split())
        common_words = words1.intersection(words2)
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'to', 'of', 'and', 'or', 'for', 'in', 'on', 'at', 'by'}
        meaningful_common = [w for w in common_words if w not in stop_words and len(w) > 2]
        
        return {
            'contributing_factors': [
                {
                    'factor': 'Content similarity',
                    'contribution': int(score * 100),
                    'detail': f'Tasks share {len(meaningful_common)} meaningful terms: {", ".join(list(meaningful_common)[:5])}'
                }
            ],
            'common_keywords': list(meaningful_common)[:10],
            'summary': f"Tasks share similar context with {len(meaningful_common)} common keywords",
            'confidence_explanation': f'{int(score * 100)}% text similarity detected between task descriptions'
        }
    
    @staticmethod
    def _generate_blocking_reasoning(task, blocking_task, score) -> Dict:
        """Generate detailed reasoning for blocking relationship suggestion"""
        task_desc = task.description.lower() if task.description else ''
        
        blocking_keywords_found = [kw for kw in DependencyAnalyzer.BLOCKING_KEYWORDS if kw in task_desc]
        
        return {
            'contributing_factors': [
                {
                    'factor': 'Blocking keywords detected',
                    'contribution': int(score * 100),
                    'detail': f'Found blocking indicators: {", ".join(blocking_keywords_found)}' if blocking_keywords_found else 'Implicit blocking relationship detected'
                }
            ],
            'keywords_found': blocking_keywords_found,
            'summary': f"Task contains {len(blocking_keywords_found)} blocking indicator(s)",
            'confidence_explanation': 'Explicit blocking language detected' if blocking_keywords_found else 'Implicit relationship inferred from context'
        }
    
    @staticmethod
    def _generate_recommendations(parent_suggestions, related_suggestions, blocking_suggestions) -> list:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        if parent_suggestions and parent_suggestions[0]['confidence'] > 0.7:
            top_parent = parent_suggestions[0]
            recommendations.append({
                'action': 'Consider linking as parent task',
                'target': top_parent['task_title'],
                'confidence': top_parent['confidence'],
                'reason': f"High confidence ({int(top_parent['confidence'] * 100)}%) that this is a prerequisite"
            })
        
        if blocking_suggestions and blocking_suggestions[0]['confidence'] > 0.7:
            top_blocker = blocking_suggestions[0]
            recommendations.append({
                'action': 'Review potential blocking relationship',
                'target': top_blocker['task_title'],
                'confidence': top_blocker['confidence'],
                'reason': 'Blocking keywords suggest dependency chain'
            })
        
        if related_suggestions and len(related_suggestions) >= 2:
            recommendations.append({
                'action': 'Consider grouping related tasks',
                'target': f"{len(related_suggestions)} related tasks found",
                'reason': 'Multiple related tasks may benefit from coordination'
            })
        
        if not recommendations:
            recommendations.append({
                'action': 'No strong dependencies detected',
                'reason': 'Consider adding more description details for better analysis'
            })
        
        return recommendations


class DependencyGraphGenerator:
    """
    Generates visual dependency graphs and trees from task relationships
    """
    
    @staticmethod
    def generate_dependency_tree(task: Task, include_subtasks: bool = True, 
                                include_related: bool = False) -> Dict:
        """
        Generate a tree structure representing task dependencies
        
        Args:
            task: Root task to generate tree from
            include_subtasks: Include child tasks in tree
            include_related: Include related tasks
            
        Returns:
            Dictionary representing the dependency tree
        """
        tree_node = {
            'id': task.id,
            'title': task.title,
            'description': task.description[:100] if task.description else '',
            'status': task.column.name if task.column else 'Unknown',
            'assigned_to': task.assigned_to.username if task.assigned_to else 'Unassigned',
            'priority': task.priority,
            'level': task.get_dependency_level(),
            'children': [],
            'related': [],
            'parent': None
        }
        
        # Add parent reference
        if task.parent_task:
            tree_node['parent'] = {
                'id': task.parent_task.id,
                'title': task.parent_task.title
            }
        
        # Add subtasks
        if include_subtasks:
            for subtask in task.subtasks.all():
                tree_node['children'].append(
                    DependencyGraphGenerator.generate_dependency_tree(subtask, include_subtasks, include_related)
                )
        
        # Add related tasks
        if include_related:
            for related in task.related_tasks.all():
                tree_node['related'].append({
                    'id': related.id,
                    'title': related.title
                })
        
        return tree_node
    
    @staticmethod
    def generate_dependency_graph(board, root_task_id: Optional[int] = None) -> Dict:
        """
        Generate a full dependency graph for visualization
        
        Args:
            board: Board to generate graph from
            root_task_id: Optional specific task to focus on
            
        Returns:
            Dictionary representing the full dependency graph
        """
        nodes = []
        edges = []
        
        tasks = Task.objects.filter(column__board=board)
        
        # Create nodes
        for task in tasks:
            nodes.append({
                'id': task.id,
                'label': f"{task.title[:30]}...",
                'full_title': task.title,
                'priority': task.priority,
                'status': task.column.name if task.column else 'Unknown',
                'level': task.get_dependency_level()
            })
        
        # Create edges for parent-child relationships
        for task in tasks:
            if task.parent_task:
                edges.append({
                    'from': task.parent_task.id,
                    'to': task.id,
                    'type': 'parent-child'
                })
            
            # Add related task edges
            for related in task.related_tasks.all():
                edges.append({
                    'from': task.id,
                    'to': related.id,
                    'type': 'related'
                })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'root_id': root_task_id
        }


def analyze_and_suggest_dependencies(task: Task, board=None, auto_link: bool = False) -> Dict:
    """
    Main entry point for dependency analysis
    
    Args:
        task: Task to analyze
        board: Board context (optional)
        auto_link: Whether to automatically create links to top suggestions
        
    Returns:
        Analysis result with suggestions
    """
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze_task_description(task, board)
    
    # Store suggestions on task
    task.suggested_dependencies = {
        'analysis_timestamp': timezone.now().isoformat(),
        'suggestions': result
    }
    task.last_dependency_analysis = timezone.now()
    
    # Optionally auto-link top parent suggestion
    if auto_link and result['parent_suggestions']:
        top_parent = result['parent_suggestions'][0]
        if top_parent['confidence'] > 0.7:
            try:
                parent_task = Task.objects.get(id=top_parent['task_id'])
                if not task.has_circular_dependency(parent_task):
                    task.parent_task = parent_task
            except Task.DoesNotExist:
                logger.warning(f"Suggested parent task {top_parent['task_id']} not found")
    
    task.save()
    return result
