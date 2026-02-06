"""
AI utilities for the Wiki/Meeting Hub
Handles transcript analysis and task extraction
"""

import json
import logging
import re
from typing import Optional, Dict
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Temperature settings for wiki AI tasks
WIKI_TEMPERATURE_MAP = {
    'simple': 0.5,           # General content
    'complex': 0.4,          # Complex analysis
    'transcript_analysis': 0.4,  # Meeting transcript analysis - needs accuracy
    'task_extraction': 0.3,  # Task extraction - needs consistency
    'summary': 0.5,          # Summaries - balanced
}


def generate_ai_content(prompt: str, task_type='simple') -> Optional[str]:
    """
    Generate content using AI (Gemini) with smart model routing and optimized temperature.
    
    Routes to appropriate model based on task complexity:
    - Complex tasks → Gemini 2.5 Flash
    - Simple tasks → Gemini 2.5 Flash-Lite (default)
    
    Temperature settings:
    - transcript_analysis: 0.4 (needs accuracy)
    - task_extraction: 0.3 (needs consistency)
    - summary: 0.5 (balanced)
    - complex: 0.4 (analytical)
    - simple: 0.5 (general)
    
    Args:
        prompt: The prompt to send
        task_type: 'simple' or 'complex' to select model
    """
    try:
        import google.generativeai as genai
        from django.conf import settings
        
        if not hasattr(settings, 'GEMINI_API_KEY'):
            logger.error("GEMINI_API_KEY not configured")
            return None
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Smart routing: use Gemini 2.5 Flash for all tasks (best performance/price)
        model_name = 'gemini-2.5-flash'
        model = genai.GenerativeModel(model_name)
        
        # Get optimized temperature for this task type
        temperature = WIKI_TEMPERATURE_MAP.get(task_type, 0.5)
        
        # Create generation config with task-specific temperature
        generation_config = {
            'temperature': temperature,
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 4096,
        }
        
        logger.debug(f"Using {model_name} for task_type: {task_type}, temperature: {temperature}")
        
        response = model.generate_content(prompt, generation_config=generation_config)
        
        if response and response.text:
            return response.text
        return None
    except Exception as e:
        logger.error(f"Error generating AI content: {str(e)}")
        return None


def extract_tasks_from_transcript(transcript: str, meeting_context: Dict, 
                                 related_board=None, organization=None) -> Optional[Dict]:
    """
    Extract actionable tasks from meeting transcript using AI
    
    Args:
        transcript: The meeting transcript text
        meeting_context: Additional context (meeting type, participants, etc.)
        related_board: Optional board for context
        organization: Organization context
        
    Returns:
        Dictionary with extracted tasks and metadata
    """
    try:
        # Build board context if provided
        board_context = ""
        if related_board:
            board_members = [member.username for member in related_board.members.all()]
            board_members.append(related_board.created_by.username)
            existing_columns = [col.name for col in related_board.columns.all()]
            
            board_context = f"""
        ## Board Context:
        - Board: {related_board.name}
        - Available Assignees: {', '.join(board_members)}
        - Project Context: {related_board.description[:200] if related_board.description else 'No description'}
        - Available Columns: {', '.join(existing_columns)}
        """
        
        prompt = f"""
        Analyze this meeting transcript and extract actionable tasks. Focus on clear action items, 
        decisions that require follow-up, and commitments made during the meeting.
        Provide comprehensive explainability for all extracted tasks.
        
        ## Meeting Context:
        - Meeting Type: {meeting_context.get('meeting_type', 'General')}
        - Date: {meeting_context.get('date', 'Not specified')}
        - Participants: {', '.join(meeting_context.get('participants', []))}
        {board_context}
        
        ## Meeting Transcript:
        {transcript}
        
        ## Instructions:
        1. Extract ONLY clear, actionable tasks (not general discussion points)
        2. Each task should have a specific deliverable or outcome
        3. Include context from the discussion for each task
        4. Suggest appropriate assignees if mentioned or implied
        5. Estimate priority based on urgency/importance discussed
        6. Suggest realistic due dates if timeframes were mentioned
        7. Identify dependencies between tasks if any
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "extraction_summary": {{
                "total_tasks_found": 0,
                "meeting_summary": "Brief 2-3 sentence summary of key outcomes",
                "confidence_level": "high|medium|low",
                "confidence_score": 0.XX,
                "processing_notes": "Any important context or limitations",
                "extraction_quality": {{
                    "transcript_clarity": "high|medium|low",
                    "action_item_density": "high (many tasks)|medium|low (few clear tasks)",
                    "context_completeness": "How much context was available for extraction"
                }}
            }},
            "extracted_tasks": [
                {{
                    "title": "Clear, actionable task title",
                    "description": "Detailed description with context from the meeting",
                    "priority": "low|medium|high|urgent",
                    "priority_reasoning": "Why this priority level was assigned",
                    "suggested_assignee": "username or null",
                    "assignee_confidence": "high|medium|low",
                    "assignee_reasoning": "Why this person was suggested (based on discussion context)",
                    "due_date_suggestion": "YYYY-MM-DD or relative like '+7 days' or null",
                    "due_date_reasoning": "Why this date was suggested (based on timeline mentions)",
                    "estimated_effort": "1-3 days",
                    "effort_reasoning": "Basis for this estimate",
                    "category": "action_item|follow_up|decision_implementation|research",
                    "source_context": "Relevant excerpt from transcript showing where this task came from",
                    "extraction_confidence": 0.XX,
                    "extraction_reasoning": "Why we're confident this is a valid task",
                    "dependencies": ["indices of other tasks this depends on"],
                    "dependency_reasoning": "Why these dependencies exist",
                    "urgency_indicators": ["phrases from transcript indicating urgency"],
                    "success_criteria": "How to know when this task is complete",
                    "potential_blockers": ["Potential issues mentioned that could block this task"],
                    "assumptions": ["Assumptions made when extracting this task"]
                }}
            ],
            "suggested_follow_ups": [
                {{
                    "type": "meeting|check_in|review",
                    "description": "What kind of follow-up is suggested",
                    "timeframe": "When this follow-up should happen",
                    "reasoning": "Why this follow-up is needed based on discussion"
                }}
            ],
            "unresolved_items": [
                {{
                    "item": "Item mentioned but needs clarification",
                    "why_unresolved": "What information is missing",
                    "clarification_needed": "What question should be asked to resolve"
                }}
            ],
            "meeting_insights": {{
                "key_decisions": ["Decision 1 made during meeting", "Decision 2"],
                "concerns_raised": ["Concern 1 mentioned", "Concern 2"],
                "positive_highlights": ["Positive outcome 1", "Progress noted"],
                "overall_sentiment": "positive|neutral|concerning"
            }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='complex')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Clean up common JSON issues from AI responses
            response_text = response_text.replace('True', 'true').replace('False', 'false')
            response_text = response_text.replace('None', 'null')
            response_text = re.sub(r',\s*([}\]])', r'\1', response_text)
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error extracting tasks from transcript: {str(e)}")
        return None


def analyze_meeting_notes_from_wiki(wiki_content: str, wiki_page_context: Dict, 
                                   organization=None, available_boards=None) -> Optional[Dict]:
    """
    Analyze wiki-based meeting notes and extract structured information
    Optimized for wiki pages that contain meeting notes (structured or unstructured)
    
    Args:
        wiki_content: The wiki page content (markdown)
        wiki_page_context: Context about the wiki page (title, attendees, date, etc.)
        organization: Organization context
        available_boards: List of available boards for task assignment suggestions
        
    Returns:
        Dictionary with comprehensive meeting analysis including:
        - Action items with task details
        - Decisions made
        - Blockers and risks
        - Suggested team members
        - Meeting summary
    """
    try:
        # Build organization context
        org_context = ""
        board_list = ""
        if available_boards:
            board_list = "\n".join([f"- {board.name} (ID: {board.id})" for board in available_boards[:10]])
            org_context = f"""
        ## Available Project Boards:
        {board_list}
        """
        
        prompt = f"""
        You are analyzing meeting notes from a wiki page. Extract ALL valuable information including action items, 
        decisions, blockers, risks, and suggestions for task creation.
        
        ## Wiki Page Context:
        - Title: {wiki_page_context.get('title', 'Untitled')}
        - Date Created: {wiki_page_context.get('created_at', 'Not specified')}
        - Created By: {wiki_page_context.get('created_by', 'Unknown')}
        - Tags: {', '.join(wiki_page_context.get('tags', []))}
        {org_context}
        
        ## Meeting Notes Content (Markdown):
        {wiki_content}
        
        ## Your Task:
        Analyze these meeting notes and extract:
        1. **Action Items**: Clear tasks that need to be done
        2. **Decisions**: Key decisions made during the meeting
        3. **Blockers**: Issues preventing progress
        4. **Risks**: Potential risks identified
        5. **Participants**: People mentioned or involved (extract from content)
        6. **Key Topics**: Main discussion topics
        7. **Follow-ups**: Things that need follow-up meetings or check-ins
        
        **IMPORTANT**: Be generous in extracting action items. Even informal mentions like "we should...", 
        "need to...", "will do...", or "someone should..." can be tasks.
        
        Format your response as JSON:
        {{
            "meeting_summary": {{
                "title": "Suggested meeting title if not clear from context",
                "summary": "3-4 sentence summary of the meeting",
                "date_detected": "Detected meeting date or null",
                "participants_detected": ["List of names/usernames mentioned"],
                "meeting_type": "standup|planning|review|retrospective|general",
                "confidence": "high|medium|low"
            }},
            "action_items": [
                {{
                    "title": "Clear, actionable task title (max 100 chars)",
                    "description": "Detailed description with full context from the notes",
                    "priority": "low|medium|high|urgent",
                    "suggested_assignee": "username/name if mentioned, else null",
                    "assignee_confidence": "high|medium|low",
                    "due_date_suggestion": "YYYY-MM-DD or '+N days' or null",
                    "estimated_effort": "e.g., '2-3 hours', '1 day', '1 week'",
                    "source_context": "Direct quote or paraphrase from notes showing where this came from",
                    "suggested_board_id": "ID of most relevant board or null",
                    "suggested_board_name": "Name of suggested board or null",
                    "tags": ["relevant", "tags"],
                    "category": "action_item|follow_up|decision_implementation|research|bug_fix|feature"
                }}
            ],
            "decisions": [
                {{
                    "decision": "Clear statement of the decision made",
                    "context": "Why this decision was made",
                    "impact": "Who/what this affects",
                    "requires_action": true/false,
                    "action_description": "What needs to be done if requires_action is true"
                }}
            ],
            "blockers": [
                {{
                    "blocker": "Description of the blocker",
                    "affected_area": "What is blocked",
                    "severity": "low|medium|high|critical",
                    "suggested_resolution": "How to resolve it",
                    "owner": "Who should resolve it or null"
                }}
            ],
            "risks": [
                {{
                    "risk": "Description of the risk",
                    "impact": "Potential impact if risk materializes",
                    "probability": "low|medium|high",
                    "mitigation": "Suggested mitigation strategy"
                }}
            ],
            "key_topics": [
                "Topic 1", "Topic 2", "Topic 3"
            ],
            "follow_ups": [
                {{
                    "type": "meeting|check_in|review|sync",
                    "description": "What needs to be followed up",
                    "timeframe": "When (e.g., 'next week', 'before sprint end')",
                    "participants": ["suggested participants"]
                }}
            ],
            "metadata": {{
                "total_action_items": 0,
                "total_decisions": 0,
                "total_blockers": 0,
                "total_risks": 0,
                "requires_immediate_attention": true/false,
                "overall_sentiment": "positive|neutral|concerning",
                "processing_notes": "Any important notes about the analysis"
            }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='complex')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Clean up common JSON issues from AI responses
            response_text = response_text.replace('True', 'true').replace('False', 'false')
            response_text = response_text.replace('None', 'null')
            # Remove any trailing commas before closing brackets (common AI mistake)
            response_text = re.sub(r',\s*([}\]])', r'\1', response_text)
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parse error: {json_err}. Response text (first 500 chars): {response_text[:500]}")
                # Try a more aggressive cleanup
                response_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response_text)  # Remove control characters
                result = json.loads(response_text)
            
            # Ensure metadata counts are accurate
            if 'metadata' in result:
                result['metadata']['total_action_items'] = len(result.get('action_items', []))
                result['metadata']['total_decisions'] = len(result.get('decisions', []))
                result['metadata']['total_blockers'] = len(result.get('blockers', []))
                result['metadata']['total_risks'] = len(result.get('risks', []))
            
            return result
        return None
    except Exception as e:
        logger.error(f"Error analyzing meeting notes from wiki: {str(e)}")
        return None


def parse_due_date(due_date_suggestion: str) -> Optional[datetime]:
    """Helper function to parse AI-suggested due dates"""
    if not due_date_suggestion:
        return None
    
    try:
        # Handle relative dates like "+7 days"
        if due_date_suggestion.startswith('+'):
            days = int(due_date_suggestion.replace('+', '').replace(' days', '').replace(' day', ''))
            return (timezone.now() + timedelta(days=days)).date()
        
        # Handle absolute dates
        return datetime.strptime(due_date_suggestion, '%Y-%m-%d').date()
    except:
        return None


def extract_text_from_file(file_path: str, file_type: str) -> Optional[str]:
    """
    Extract text content from uploaded files
    
    Args:
        file_path: Path to the uploaded file
        file_type: Type of file (txt, docx, pdf, etc.)
        
    Returns:
        Extracted text content or None if extraction fails
    """
    try:
        if file_type == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        
        elif file_type == 'docx':
            try:
                from docx import Document
                doc = Document(file_path)
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                return '\n'.join(text)
            except ImportError:
                logger.error("python-docx package not installed. Cannot extract from DOCX files.")
                return None
        
        elif file_type == 'pdf':
            try:
                import PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = []
                    for page in pdf_reader.pages:
                        text.append(page.extract_text())
                    return '\n'.join(text)
            except ImportError:
                logger.error("PyPDF2 package not installed. Cannot extract from PDF files.")
                return None
        
        return None
    except Exception as e:
        logger.error(f"Error extracting text from file: {str(e)}")
        return None


def analyze_wiki_documentation(wiki_content: str, wiki_page_context: Dict,
                              organization=None, available_boards=None) -> Optional[Dict]:
    """
    Analyze general wiki documentation pages (non-meeting content)
    Provides summary, extracts tasks, suggests improvements, and identifies key information
    
    Args:
        wiki_content: The wiki page content (markdown)
        wiki_page_context: Context about the wiki page (title, tags, category, etc.)
        organization: Organization context
        available_boards: List of available boards for task suggestions
        
    Returns:
        Dictionary with comprehensive documentation analysis including:
        - Summary and key points
        - Action items (if any)
        - Suggested tasks
        - Related topics
        - Documentation quality insights
    """
    try:
        # Build organization context
        org_context = ""
        board_list = ""
        if available_boards:
            board_list = "\n".join([f"- {board.name} (ID: {board.id})" for board in available_boards[:10]])
            org_context = f"""
        ## Available Project Boards:
        {board_list}
        """
        
        prompt = f"""
        You are analyzing a wiki documentation page. Extract valuable information, provide insights,
        and identify any actionable items or improvements.
        
        ## Wiki Page Context:
        - Title: {wiki_page_context.get('title', 'Untitled')}
        - Category: {wiki_page_context.get('category', 'General')}
        - Date Created: {wiki_page_context.get('created_at', 'Not specified')}
        - Created By: {wiki_page_context.get('created_by', 'Unknown')}
        - Tags: {', '.join(wiki_page_context.get('tags', []))}
        {org_context}
        
        ## Documentation Content (Markdown):
        {wiki_content}
        
        ## Your Task:
        Analyze this documentation and provide:
        1. **Summary**: Clear, concise summary of the content (2-3 sentences)
        2. **Key Points**: Main topics and important information (bullet points)
        3. **Action Items**: Any tasks, TODOs, or action items mentioned (if any)
        4. **Suggested Improvements**: Areas that could be enhanced or expanded
        5. **Related Topics**: Related areas or pages that might be relevant
        6. **Potential Tasks**: Tasks that could be created based on the content
        
        **IMPORTANT**: This is general documentation, not meeting notes. Look for:
        - TODOs or action items mentioned in the text
        - Incomplete sections or placeholders
        - References to work that needs to be done
        - Suggestions for improvements or enhancements
        
        Format your response as JSON:
        {{
            "documentation_summary": {{
                "title": "Clear title summarizing the documentation",
                "summary": "2-3 sentence overview of what this documentation covers",
                "document_type": "guide|reference|tutorial|process|policy|technical|general",
                "completeness": "complete|partial|draft",
                "last_updated_detected": "Detected date if mentioned or null",
                "target_audience": "Who this documentation is for"
            }},
            "key_points": [
                "Main point 1",
                "Main point 2",
                "Main point 3"
            ],
            "action_items": [
                {{
                    "title": "Clear, actionable task title",
                    "description": "What needs to be done",
                    "priority": "low|medium|high",
                    "type": "todo|enhancement|update|bug_fix|documentation",
                    "source_context": "Where this was mentioned in the documentation",
                    "suggested_board_id": "ID if board is obvious, else null",
                    "suggested_board_name": "Name if obvious, else null"
                }}
            ],
            "suggested_improvements": [
                {{
                    "area": "What area needs improvement",
                    "suggestion": "Specific improvement suggestion",
                    "priority": "low|medium|high",
                    "effort": "low|medium|high"
                }}
            ],
            "related_topics": [
                "Topic 1",
                "Topic 2",
                "Topic 3"
            ],
            "questions_raised": [
                "Question or unclear point that needs clarification"
            ],
            "dependencies_mentioned": [
                "External dependencies, tools, or systems mentioned"
            ],
            "metadata": {{
                "total_action_items": 0,
                "total_suggestions": 0,
                "documentation_quality": "excellent|good|needs_improvement|incomplete",
                "requires_update": true/false,
                "technical_level": "beginner|intermediate|advanced|expert",
                "processing_notes": "Any important notes about the analysis"
            }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='complex')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Clean up common JSON issues from AI responses
            response_text = response_text.replace('True', 'true').replace('False', 'false')
            response_text = response_text.replace('None', 'null')
            response_text = re.sub(r',\s*([}\]])', r'\1', response_text)
            
            result = json.loads(response_text)
            # Ensure metadata counts are accurate
            if 'metadata' in result:
                result['metadata']['total_action_items'] = len(result.get('action_items', []))
                result['metadata']['total_suggestions'] = len(result.get('suggested_improvements', []))
            
            return result
        return None
    except Exception as e:
        logger.error(f"Error analyzing wiki documentation: {str(e)}")
        return None


def get_file_type_from_filename(filename: str) -> str:
    """Get file type from filename"""
    if filename.endswith('.pdf'):
        return 'pdf'
    elif filename.endswith('.docx'):
        return 'docx'
    elif filename.endswith('.txt'):
        return 'txt'
    return 'txt'  # Default to txt
