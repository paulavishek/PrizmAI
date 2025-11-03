"""
AI utilities for the Wiki/Meeting Hub
Handles transcript analysis and task extraction
"""

import json
import logging
from typing import Optional, Dict
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def generate_ai_content(prompt: str) -> Optional[str]:
    """Generate content using AI (Gemini)"""
    try:
        import google.generativeai as genai
        from django.conf import settings
        
        if not hasattr(settings, 'GEMINI_API_KEY'):
            logger.error("GEMINI_API_KEY not configured")
            return None
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
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
        
        Format your response as JSON:
        {{
            "extraction_summary": {{
                "total_tasks_found": 0,
                "meeting_summary": "Brief 2-3 sentence summary of key outcomes",
                "confidence_level": "high|medium|low",
                "processing_notes": "Any important context or limitations"
            }},
            "extracted_tasks": [
                {{
                    "title": "Clear, actionable task title",
                    "description": "Detailed description with context from the meeting",
                    "priority": "low|medium|high|urgent",
                    "suggested_assignee": "username or null",
                    "assignee_confidence": "high|medium|low",
                    "due_date_suggestion": "YYYY-MM-DD or relative like '+7 days' or null",
                    "estimated_effort": "1-3 days",
                    "category": "action_item|follow_up|decision_implementation|research",
                    "source_context": "Relevant excerpt from transcript showing where this task came from",
                    "dependencies": ["indices of other tasks this depends on"],
                    "urgency_indicators": ["phrases from transcript indicating urgency"],
                    "success_criteria": "How to know when this task is complete"
                }}
            ],
            "suggested_follow_ups": [
                {{
                    "type": "meeting|check_in|review",
                    "description": "What kind of follow-up is suggested",
                    "timeframe": "When this follow-up should happen"
                }}
            ],
            "unresolved_items": [
                "Items mentioned but need clarification before becoming tasks"
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt)
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error extracting tasks from transcript: {str(e)}")
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


def get_file_type_from_filename(filename: str) -> str:
    """Get file type from filename"""
    if filename.endswith('.pdf'):
        return 'pdf'
    elif filename.endswith('.docx'):
        return 'docx'
    elif filename.endswith('.txt'):
        return 'txt'
    return 'txt'  # Default to txt
