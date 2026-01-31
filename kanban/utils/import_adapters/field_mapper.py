"""
Field Mapper and User Matcher Utilities
Provides utilities for custom field mapping and user resolution during imports.
"""

from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth.models import User
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


class FieldMapper:
    """
    Utility for mapping source fields to PrizmAI fields.
    
    Supports:
    - Custom field mappings provided by user
    - Default mappings for common field names
    - Transformation functions for field values
    """
    
    def __init__(self, custom_mappings: Dict[str, str] = None):
        """
        Initialize with optional custom mappings.
        
        Args:
            custom_mappings: Dict mapping source field names to PrizmAI field names
                            e.g., {'Summary': 'title', 'Issue Key': 'external_id'}
        """
        self.custom_mappings = custom_mappings or {}
        self._reverse_mappings = None
    
    @property
    def reverse_mappings(self) -> Dict[str, str]:
        """Get reverse mappings (PrizmAI field -> source field)"""
        if self._reverse_mappings is None:
            self._reverse_mappings = {v: k for k, v in self.custom_mappings.items()}
        return self._reverse_mappings
    
    def map_field(self, source_field: str, default_target: str = None) -> str:
        """
        Map a source field to a PrizmAI field.
        
        Args:
            source_field: The source field name
            default_target: Default PrizmAI field if no mapping exists
        
        Returns:
            The mapped PrizmAI field name
        """
        # Check custom mappings first (case-insensitive)
        source_lower = source_field.lower()
        for src, target in self.custom_mappings.items():
            if src.lower() == source_lower:
                return target
        
        return default_target or source_field
    
    def get_source_field(self, prizmAI_field: str) -> Optional[str]:
        """
        Get the source field name for a PrizmAI field.
        
        Args:
            prizmAI_field: The PrizmAI field name
        
        Returns:
            The source field name, or None if not mapped
        """
        return self.reverse_mappings.get(prizmAI_field)
    
    def add_mapping(self, source: str, target: str):
        """Add a field mapping"""
        self.custom_mappings[source] = target
        self._reverse_mappings = None  # Clear cache
    
    def get_all_mappings(self) -> Dict[str, str]:
        """Get all custom mappings"""
        return dict(self.custom_mappings)


class UserMatcher:
    """
    Utility for matching imported users to existing PrizmAI users.
    
    Matching strategies:
    1. Email address (exact match)
    2. Username (exact match)
    3. Full name (fuzzy match)
    """
    
    def __init__(self, organization=None, create_placeholders: bool = False):
        """
        Initialize user matcher.
        
        Args:
            organization: Organization to scope user lookups
            create_placeholders: Whether to track unmatched users for later creation
        """
        self.organization = organization
        self.create_placeholders = create_placeholders
        
        # Cache of matched users: source_id -> User
        self._user_cache: Dict[str, Optional[User]] = {}
        
        # Unmatched users for later handling
        self.unmatched_users: List[Dict[str, Any]] = []
    
    def match_user(self, identifier: str, full_name: str = None, 
                   email: str = None) -> Optional[User]:
        """
        Try to match an imported user to an existing PrizmAI user.
        
        Args:
            identifier: Primary identifier (username, email, or display name)
            full_name: Optional full name for additional matching
            email: Optional email for additional matching
        
        Returns:
            Matched User object, or None if no match found
        """
        if not identifier:
            return None
        
        # Check cache first
        cache_key = f"{identifier}|{email or ''}|{full_name or ''}"
        if cache_key in self._user_cache:
            return self._user_cache[cache_key]
        
        user = None
        
        # Strategy 1: Try email match (most reliable)
        if email:
            user = self._match_by_email(email)
        
        # Strategy 2: Try identifier as email
        if not user and '@' in identifier:
            user = self._match_by_email(identifier)
        
        # Strategy 3: Try username match
        if not user:
            user = self._match_by_username(identifier)
        
        # Strategy 4: Try full name match
        if not user and full_name:
            user = self._match_by_name(full_name)
        
        # Strategy 5: Try identifier as name
        if not user:
            user = self._match_by_name(identifier)
        
        # Cache result
        self._user_cache[cache_key] = user
        
        # Track unmatched for potential placeholder creation
        if not user and self.create_placeholders:
            self.unmatched_users.append({
                'identifier': identifier,
                'full_name': full_name,
                'email': email,
            })
        
        return user
    
    def _match_by_email(self, email: str) -> Optional[User]:
        """Match user by email address"""
        try:
            query = Q(email__iexact=email)
            
            # If organization is set, prefer users in that organization
            if self.organization:
                org_users = User.objects.filter(
                    query,
                    profile__organization=self.organization
                )
                if org_users.exists():
                    return org_users.first()
            
            # Fall back to any user with that email
            return User.objects.filter(query).first()
            
        except Exception as e:
            logger.warning(f"Error matching user by email: {e}")
            return None
    
    def _match_by_username(self, username: str) -> Optional[User]:
        """Match user by username"""
        try:
            # Clean up username
            clean_username = username.strip().lower()
            
            query = Q(username__iexact=clean_username)
            
            if self.organization:
                org_users = User.objects.filter(
                    query,
                    profile__organization=self.organization
                )
                if org_users.exists():
                    return org_users.first()
            
            return User.objects.filter(query).first()
            
        except Exception as e:
            logger.warning(f"Error matching user by username: {e}")
            return None
    
    def _match_by_name(self, name: str) -> Optional[User]:
        """Match user by full name or parts of name"""
        try:
            if not name or len(name) < 2:
                return None
            
            # Try exact full name match
            name_parts = name.strip().split()
            
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
                
                query = Q(first_name__iexact=first_name, last_name__iexact=last_name)
                
                if self.organization:
                    org_users = User.objects.filter(
                        query,
                        profile__organization=self.organization
                    )
                    if org_users.exists():
                        return org_users.first()
                
                user = User.objects.filter(query).first()
                if user:
                    return user
            
            # Try partial match on first name or last name
            query = Q(first_name__iexact=name) | Q(last_name__iexact=name)
            
            if self.organization:
                org_users = User.objects.filter(
                    query,
                    profile__organization=self.organization
                )
                if org_users.exists():
                    return org_users.first()
            
            return User.objects.filter(query).first()
            
        except Exception as e:
            logger.warning(f"Error matching user by name: {e}")
            return None
    
    def get_match_summary(self) -> Dict[str, Any]:
        """Get summary of user matching results"""
        matched_count = sum(1 for u in self._user_cache.values() if u is not None)
        unmatched_count = len(self.unmatched_users)
        
        return {
            'total_lookups': len(self._user_cache),
            'matched': matched_count,
            'unmatched': unmatched_count,
            'unmatched_users': self.unmatched_users[:10],  # First 10 for preview
        }
    
    def clear_cache(self):
        """Clear the user matching cache"""
        self._user_cache.clear()
        self.unmatched_users.clear()


def normalize_username(value: str) -> str:
    """
    Normalize a username for matching.
    
    - Lowercase
    - Remove common email domains for display names
    - Strip whitespace
    """
    if not value:
        return ''
    
    result = value.strip().lower()
    
    # If it looks like an email, extract the username part
    if '@' in result:
        result = result.split('@')[0]
    
    return result


def extract_email_from_text(text: str) -> Optional[str]:
    """
    Try to extract an email address from a text string.
    """
    import re
    
    if not text:
        return None
    
    # Simple email regex
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    match = re.search(email_pattern, text)
    
    if match:
        return match.group(0).lower()
    
    return None
