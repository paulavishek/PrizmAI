"""
ai_router.py — Central AI provider router for PrizmAI.

All AI features in PrizmAI should route their calls through this module
instead of calling Gemini (or any other provider) directly.  The router
determines which provider and API key to use for a given user, makes the
call, and returns a consistent response dictionary regardless of provider.

Usage:
    from ai_assistant.utils.ai_router import AIRouter, AIProviderError

    router = AIRouter()
    try:
        result = router.complete(prompt="Summarise this task", user=request.user)
        text = result["text"]
    except AIProviderError as e:
        # e.provider tells you which provider failed
        handle_error(e)

Provider resolution order (full detail in _resolve_provider):
  1. User personal BYOK key        → user's byok_provider  (always permitted)
  2. User provider_override        → if Org Admin or org.allow_user_provider_override
  3. Organisation BYOK key         → org.byok_provider
  4. Organisation provider setting → platform key from Django settings
  5. No settings at all            → Gemini with platform key  (safe fallback)
"""

import logging
import threading

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Lock used to serialise genai.configure() calls in _call_gemini.
# google-generativeai 0.8.x uses a module-level global API key, so concurrent
# BYOK requests from different users would clobber each other without this lock.
# Replace with per-client instantiation when upgrading to google-genai >= 1.0.
_GEMINI_CONFIGURE_LOCK = threading.Lock()

# To generate a valid Fernet key for AI_KEY_ENCRYPTION_KEY, run in Python:
#   from cryptography.fernet import Fernet
#   print(Fernet.generate_key().decode())


# ======================================================================
# Custom exception
# ======================================================================

class AIProviderError(Exception):
    """
    Raised when an AI provider call fails for any reason.

    Using a single exception type means every caller in PrizmAI only
    needs to handle AIProviderError, regardless of which provider is active.

    Attributes:
        provider (str): Which provider failed — 'gemini', 'openai', 'anthropic'.
        original_error (Exception): The underlying exception.
    """

    def __init__(self, provider: str, original_error: Exception):
        self.provider = provider
        self.original_error = original_error
        super().__init__(f"AI provider '{provider}' failed: {str(original_error)}")


# ======================================================================
# Router
# ======================================================================

class AIRouter:
    """
    Central switchboard for all AI calls in PrizmAI.

    Determines the correct provider and API key for a given user,
    dispatches the call to the appropriate provider method, and returns
    every response in the same normalised dictionary format regardless
    of which provider answered.

    The router carries no per-request state — it is safe to instantiate
    once at module level and reuse across requests, or to create a fresh
    instance per request.
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def complete(self, prompt: str, user=None, system_prompt: str = None,
                 conversation_history: list = None, complexity: str = 'simple') -> dict:
        """
        Make an AI completion call on behalf of a user.

        Resolves the correct provider and key for this user, calls the
        provider, and returns a normalised response dictionary.

        Args:
            prompt (str): The user's input or the feature's generated prompt.
            user: Django User object.  Used to look up provider / key settings.
                Pass None for background/Celery tasks with no user context —
                the router will fall back to org-level settings or Gemini.
            system_prompt (str, optional): System-level context prepended to
                the call.
            conversation_history (list, optional): Prior conversation turns.
                Canonical format (all providers)::

                    [
                        {"role": "user",      "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                        ...
                    ]

                Only ``role`` values of ``"user"`` and ``"assistant"`` are
                accepted.  The router converts this into each provider's
                native message format before making the call.  Gemini
                currently ignores history (stateless calls only).
            complexity (str): 'simple' or 'complex'.  Maps to a cheaper/faster
                model for light tasks, or the full model for heavy analysis.
                Defaults to 'simple'.  Call sites should pass 'complex' for
                multi-step AI analysis, document understanding, or code tasks.

        Returns:
            dict: Normalised response — see _normalise_response() for keys.

        Raises:
            AIProviderError: If the provider call fails for any reason.
            ImproperlyConfigured: If AI_KEY_ENCRYPTION_KEY is missing and a
                BYOK key needs to be decrypted.
        """
        # Emergency rollback switch — if AI_ROUTER_ENABLED is False in settings,
        # bypass all provider resolution and call Gemini directly.  This is an
        # operator-level kill-switch for production incidents.
        if not getattr(settings, 'AI_ROUTER_ENABLED', True):
            logger.warning(
                "AIRouter: AI_ROUTER_ENABLED=False — bypassing router, calling Gemini directly."
            )
            return self._emergency_gemini_fallback(prompt, system_prompt, conversation_history, complexity)

        provider, api_key, is_byok, byok_model = self._resolve_provider(user)

        try:
            if provider == 'gemini':
                raw = self._call_gemini(prompt, api_key, system_prompt, conversation_history, complexity, model_override=byok_model)
            elif provider == 'openai':
                raw = self._call_openai(prompt, api_key, system_prompt, conversation_history, complexity, model_override=byok_model)
            elif provider == 'anthropic':
                raw = self._call_anthropic(prompt, api_key, system_prompt, conversation_history, complexity, model_override=byok_model)
            else:
                raise AIProviderError(provider, ValueError(f"Unknown provider: '{provider}'"))

        except (AIProviderError, NotImplementedError, ImproperlyConfigured):
            raise  # already correctly typed — pass straight through
        except Exception as exc:
            raise AIProviderError(provider, exc) from exc

        return self._normalise_response(
            text=raw.get('text', ''),
            provider=provider,
            model=raw.get('model', ''),
            used_byok=is_byok,
            tokens_used=raw.get('tokens_used'),
        )

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    def _resolve_provider(self, user) -> tuple:
        """
        Determine which provider and API key to use for a given user.

        Checks in this exact order:

          Step 1  — User personal BYOK key
                    If the user has an encrypted personal API key stored,
                    decrypt it and use that provider.  This is always
                    permitted regardless of any organisation setting because
                    it is the user's own key on their own bill.

          Step 2  — User provider_override
                    If the user has chosen a specific provider (not 'inherit'),
                    respect it when:
                      (a) the user is an Org Admin, OR
                      (b) the organisation's allow_user_provider_override is True.
                    If neither condition holds, the override is silently ignored
                    and resolution falls through to Step 3.

          Step 3  — Organisation BYOK key
                    If the organisation has an encrypted BYOK key, decrypt
                    and use it with the organisation's byok_provider.

          Step 4  — Organisation provider setting
                    Use the organisation's configured provider with the
                    matching platform API key from Django settings.

          Step 5  — Fallback (no settings at all)
                    Default to Gemini with the platform key.  This is the
                    correct behaviour for all existing users whose records
                    do not yet exist in either AI settings table.

        IMPORTANT: Both UserAISettings and OrganizationAISettings tables
        start empty.  This method handles .DoesNotExist for both models
        explicitly — a missing record is the normal case, not an error.

        Args:
            user: Django User object.

        Returns:
            tuple: (provider_str, api_key_str, is_byok_bool, byok_model_or_none)
                provider_str      — 'gemini', 'openai', or 'anthropic'
                api_key_str       — API key to pass to the provider call
                is_byok_bool      — True if a user-supplied key is being used
                byok_model_or_none — model string if the BYOK user chose one, else None
        """
        # Import here (not at module top) to avoid circular imports, since
        # ai_router.py lives inside the ai_assistant app that owns these models.
        from ai_assistant.models import UserAISettings, OrganizationAISettings

        # ==============================================================
        # Background task path — user=None means no user context.
        # Steps 1 (personal BYOK) and 2 (user override) are skipped.
        # We still attempt org-level resolution (Steps 3-4) by scanning
        # for any active OrganizationAISettings record.
        # ==============================================================
        if user is None:
            # Try to find any org-level AI settings to use as context.
            # For Celery tasks this gives the most-recently configured org.
            try:
                org_settings = OrganizationAISettings.objects.filter(
                    provider__isnull=False
                ).first()
                if org_settings and org_settings.encrypted_api_key and org_settings.byok_provider:
                    try:
                        api_key = self._decrypt_key(org_settings.encrypted_api_key)
                        logger.debug(
                            "AIRouter (background task): using org BYOK key provider=%s",
                            org_settings.byok_provider,
                        )
                        return (org_settings.byok_provider, api_key, True, org_settings.byok_model or None)
                    except Exception:
                        pass  # Decryption failure — fall through to platform key
                if org_settings and org_settings.provider:
                    api_key = self._platform_key(org_settings.provider)
                    logger.debug(
                        "AIRouter (background task): using org provider=%s",
                        org_settings.provider,
                    )
                    return (org_settings.provider, api_key, False, None)
            except Exception:
                pass  # Table doesn't exist yet or any other error — fall through
            # Final fallback for background tasks: Gemini with platform key.
            logger.debug("AIRouter (background task): falling back to Gemini platform key")
            return ('gemini', self._platform_key('gemini'), False, None)

        # ---- Fetch user AI settings (starts empty for new users) ----
        user_settings = None
        try:
            user_settings = user.ai_settings
        except UserAISettings.DoesNotExist:
            pass  # No personal settings yet — continue resolution
        except AttributeError:
            pass  # Defensive: unexpected user object shape

        # ---- Fetch organisation AI settings (also starts empty) ----
        org_settings = None
        try:
            profile = getattr(user, 'profile', None)
            if profile is not None and getattr(profile, 'organization', None) is not None:
                org_settings = profile.organization.ai_settings
        except OrganizationAISettings.DoesNotExist:
            pass  # No org-level settings yet — continue resolution
        except AttributeError:
            pass  # Defensive: profile or organization missing

        # ---- Determine if user is an Org Admin ----
        # Org Admin = UserProfile.is_admin == True (set by the accounts app)
        is_org_admin = False
        try:
            is_org_admin = bool(getattr(user.profile, 'is_admin', False))
        except AttributeError:
            pass  # No profile — treat as non-admin

        # ==============================================================
        # Step 1: User personal BYOK key
        # Always permitted — user is paying with their own key.
        # ==============================================================
        if (
            user_settings is not None
            and user_settings.encrypted_api_key
            and user_settings.byok_provider
        ):
            try:
                api_key = self._decrypt_key(user_settings.encrypted_api_key)
                logger.debug(
                    "AIRouter: using personal BYOK key for user=%s provider=%s",
                    getattr(user, 'username', '?'),
                    user_settings.byok_provider,
                )
                return (user_settings.byok_provider, api_key, True, user_settings.byok_model or None)
            except (ImproperlyConfigured, AIProviderError):
                raise  # already descriptive — pass through
            except Exception as exc:
                raise AIProviderError(
                    user_settings.byok_provider,
                    Exception(
                        "Failed to decrypt your personal BYOK key. "
                        "The stored key may be corrupted — please re-enter it "
                        "in your AI settings."
                    ),
                ) from exc

        # ==============================================================
        # Step 2: User provider_override
        # Respected when: user is Org Admin OR org.allow_user_provider_override
        # ==============================================================
        if (
            user_settings is not None
            and user_settings.provider_override != 'inherit'
        ):
            override_allowed = is_org_admin or (
                org_settings is not None and org_settings.allow_user_provider_override
            )
            if override_allowed:
                api_key = self._platform_key(user_settings.provider_override)
                logger.debug(
                    "AIRouter: using provider_override=%s for user=%s",
                    user_settings.provider_override,
                    getattr(user, 'username', '?'),
                )
                return (user_settings.provider_override, api_key, False, None)
            # Override present but not permitted — fall through silently

        # ==============================================================
        # Step 3: Organisation BYOK key
        # ==============================================================
        if (
            org_settings is not None
            and org_settings.encrypted_api_key
            and org_settings.byok_provider
        ):
            try:
                api_key = self._decrypt_key(org_settings.encrypted_api_key)
                logger.debug(
                    "AIRouter: using org BYOK key for provider=%s",
                    org_settings.byok_provider,
                )
                return (org_settings.byok_provider, api_key, True, org_settings.byok_model or None)
            except (ImproperlyConfigured, AIProviderError):
                raise
            except Exception as exc:
                raise AIProviderError(
                    org_settings.byok_provider,
                    Exception(
                        "Failed to decrypt the organisation BYOK key. "
                        "The stored key may be corrupted — an Org Admin should "
                        "re-enter it in the organisation AI settings."
                    ),
                ) from exc

        # ==============================================================
        # Step 4: Organisation provider with platform key
        # ==============================================================
        if org_settings is not None and org_settings.provider:
            api_key = self._platform_key(org_settings.provider)
            logger.debug(
                "AIRouter: using org provider=%s (platform key)",
                org_settings.provider,
            )
            return (org_settings.provider, api_key, False, None)

        # ==============================================================
        # Step 5: Fallback — Gemini with platform key
        # This is the path every existing user takes until settings are added.
        # ==============================================================
        logger.debug(
            "AIRouter: no settings found for user=%s — falling back to Gemini",
            getattr(user, 'username', '?') if user is not None else '<background task>',
        )
        return ('gemini', self._platform_key('gemini'), False, None)

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _get_fernet(self):
        """
        Return a Fernet instance using the AI_KEY_ENCRYPTION_KEY setting.

        Raises:
            ImproperlyConfigured: If AI_KEY_ENCRYPTION_KEY is missing or empty.
        """
        # To generate a valid key, run in Python:
        #   from cryptography.fernet import Fernet
        #   print(Fernet.generate_key().decode())
        from cryptography.fernet import Fernet

        key = getattr(settings, 'AI_KEY_ENCRYPTION_KEY', None)
        if not key:
            raise ImproperlyConfigured(
                "AI_KEY_ENCRYPTION_KEY is not set in Django settings. "
                "Generate a Fernet key with: "
                "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode()) "
                "and add it to your .env file as AI_KEY_ENCRYPTION_KEY."
            )
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)

    def _encrypt_key(self, raw_key: str) -> str:
        """
        Encrypt a plain-text API key using Fernet (AES-256).

        Call this from views when a user saves a BYOK key.  Never store
        the raw key anywhere — only store the string this method returns.

        Args:
            raw_key (str): The plain-text API key entered by the user.

        Returns:
            str: Fernet-encrypted key string, safe to store in the database.

        Raises:
            ImproperlyConfigured: If AI_KEY_ENCRYPTION_KEY is not configured.
        """
        f = self._get_fernet()
        return f.encrypt(raw_key.encode()).decode()

    def _decrypt_key(self, encrypted_key: str) -> str:
        """
        Decrypt a Fernet-encrypted API key back to plain text.

        Call this only immediately before making an API call.  Never log
        or store the decrypted result.

        Args:
            encrypted_key (str): The encrypted string from the database.

        Returns:
            str: Plain-text API key, ready for use.

        Raises:
            ImproperlyConfigured: If AI_KEY_ENCRYPTION_KEY is not configured.
            Exception: If decryption fails (key may be corrupted, or the
                encryption key may have changed since the key was stored).
        """
        f = self._get_fernet()
        return f.decrypt(encrypted_key.encode()).decode()

    # ------------------------------------------------------------------
    # Platform key helper
    # ------------------------------------------------------------------

    def _platform_key(self, provider: str) -> str:
        """
        Return the platform-level API key for a provider from Django settings.

        Args:
            provider (str): 'gemini', 'openai', or 'anthropic'.

        Returns:
            str: API key string from settings (may be empty if not configured).
        """
        key_map = {
            'gemini': getattr(settings, 'GEMINI_API_KEY', ''),
            'openai': getattr(settings, 'OPENAI_API_KEY', ''),
            'anthropic': getattr(settings, 'ANTHROPIC_API_KEY', ''),
        }
        return key_map.get(provider, '')

    # ------------------------------------------------------------------
    # BYOK key validation
    # ------------------------------------------------------------------

    def validate_api_key(self, provider: str, raw_key: str, model: str = None) -> bool:
        """
        Validate a raw (unencrypted) API key by making a minimal test call
        to the specified provider.

        Used by the settings views before encrypting and storing a BYOK key.
        This avoids any DB state changes — the key is tested directly, not
        routed through _resolve_provider().

        Args:
            provider (str): 'gemini', 'openai', or 'anthropic'.
            raw_key (str): Plain-text API key to test.
            model (str, optional): If provided, test the call with this exact
                model string.  Used to validate custom model names before saving.

        Returns:
            bool: True if the key is valid and the provider responded,
                  False on any failure (bad key, network error, quota,
                  unrecognised model name, etc.).
        """
        probe = "Hi"
        try:
            if provider == 'gemini':
                self._call_gemini(probe, raw_key, model_override=model)
            elif provider == 'openai':
                self._call_openai(probe, raw_key, model_override=model)
            elif provider == 'anthropic':
                self._call_anthropic(probe, raw_key, model_override=model)
            else:
                return False
            return True
        except (AIProviderError, NotImplementedError, ImproperlyConfigured,
                Exception):
            return False

    # ------------------------------------------------------------------
    # Provider call methods
    # ------------------------------------------------------------------

    def _emergency_gemini_fallback(self, prompt: str, system_prompt: str = None,
                                    conversation_history: list = None,
                                    complexity: str = 'simple') -> dict:
        """
        Emergency fallback path invoked when AI_ROUTER_ENABLED=False.

        Bypasses all provider resolution and calls Gemini directly using the
        platform key.  Returns a normalised response in the same format as
        complete() so callers are unaware of the bypass.

        This method should only ever be triggered by an operator setting
        AI_ROUTER_ENABLED=false in production during an incident.
        """
        api_key = self._platform_key('gemini')
        raw = self._call_gemini(prompt, api_key, system_prompt, conversation_history, complexity)
        return self._normalise_response(
            text=raw.get('text', ''),
            provider='gemini',
            model=raw.get('model', ''),
            used_byok=False,
            tokens_used=raw.get('tokens_used'),
        )

    def _call_gemini(self, prompt: str, api_key: str, system_prompt: str = None,
                     conversation_history: list = None, complexity: str = 'simple',
                     model_override: str = None) -> dict:
        """
        Call Google Gemini and return a raw response dictionary.

        This method is standalone — it does NOT use or modify the existing
        GeminiClient class, so no existing call sites are affected.

        NOTE ON THREAD SAFETY: google.generativeai uses a module-level global
        API key (genai.configure).  Concurrent requests that use different BYOK
        keys may interfere with each other.  The _GEMINI_CONFIGURE_LOCK ensures
        thread safety for BYOK scenarios.

        Args:
            prompt (str): The prompt to send.
            api_key (str): Gemini API key (platform or BYOK).
            system_prompt (str, optional): Prepended as context before the prompt.
            conversation_history (list, optional): Accepted for interface
                consistency but not used — Gemini is called statelessly.
            complexity (str): 'simple' → gemini-2.5-flash-lite (faster/cheaper);
                              'complex' → gemini-2.5-flash (full model).

        Returns:
            dict: {'text': str, 'model': str, 'tokens_used': int | None}

        Raises:
            AIProviderError: On any Gemini-side failure.
        """
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise AIProviderError(
                'gemini',
                ImportError("google-generativeai package is not installed."),
            ) from exc

        if not api_key:
            raise AIProviderError(
                'gemini',
                ValueError(
                    "No Gemini API key is available. "
                    "Set GEMINI_API_KEY in your .env file or enter a BYOK key."
                ),
            )

        # Select model: BYOK model override takes priority; otherwise use complexity-based defaults.
        # 'simple' → gemini-3.1-flash-lite (no thinking mode, fast structured output)
        # 'complex' → gemini-2.5-flash (full model for analysis, generation, reasoning)
        if model_override:
            model_name = model_override
        elif complexity == 'complex':
            model_name = getattr(settings, 'GEMINI_MODEL_COMPLEX', 'gemini-2.5-flash')
        else:
            model_name = getattr(settings, 'GEMINI_MODEL_SIMPLE', 'gemini-2.0-flash')

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # 'simple' tasks (structured JSON output like pre-mortem) use a smaller token
        # budget.  Avoid Gemini 2.5 models for simple tasks: their extended thinking
        # mode adds 30–90 s of latency on analytical prompts without quality benefit.
        # GEMINI_MODEL_SIMPLE should point to a non-thinking model (e.g. gemini-3.1-flash-lite).
        # ThinkingConfig is not available in google-generativeai 0.8.x; thinking behaviour
        # is controlled solely by model choice.
        max_output_tokens = 2048 if complexity == 'simple' else 6144
        generation_config = {
            'temperature': 0.7,
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': max_output_tokens,
        }

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT",         "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",  "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT",  "threshold": "BLOCK_ONLY_HIGH"},
        ]

        # google-generativeai 0.8.x uses a module-level global API key (genai.configure).
        # The lock serialises configure() calls so concurrent BYOK requests don't
        # overwrite each other's key.  For the platform key (shared, never changes)
        # we can release the lock before the network call so other tasks aren't
        # blocked for the full API round-trip; BYOK calls hold it for the duration.
        platform_key = getattr(settings, 'GEMINI_API_KEY', None)
        is_byok = bool(api_key) and api_key != platform_key

        def _build_model():
            genai.configure(api_key=api_key)
            return genai.GenerativeModel(
                model_name,
                generation_config=generation_config,
                safety_settings=safety_settings,
            )

        if is_byok:
            # Hold the lock for the entire call; key must not change mid-request.
            with _GEMINI_CONFIGURE_LOCK:
                model = _build_model()
                response = model.generate_content(
                    full_prompt,
                    request_options={"timeout": 120},
                )
        else:
            # Platform key never changes — release lock before the slow network call.
            with _GEMINI_CONFIGURE_LOCK:
                model = _build_model()
            response = model.generate_content(
                full_prompt,
                request_options={"timeout": 120},
            )

        # Guard against empty / safety-blocked responses
        if (
            not response.candidates
            or not response.candidates[0].content.parts
        ):
            finish_reason = (
                response.candidates[0].finish_reason
                if response.candidates else 'unknown'
            )
            raise AIProviderError(
                'gemini',
                ValueError(
                    f"Gemini returned an empty response (finish_reason={finish_reason}). "
                    "The content may have been blocked by safety filters."
                ),
            )

        text = response.text
        tokens_used = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tokens_used = (
                getattr(response.usage_metadata, 'prompt_token_count', 0)
                + getattr(response.usage_metadata, 'candidates_token_count', 0)
            )

        return {'text': text, 'model': model_name, 'tokens_used': tokens_used}

    def _call_openai(self, prompt: str, api_key: str, system_prompt: str = None,
                     conversation_history: list = None, complexity: str = 'simple',
                     model_override: str = None) -> dict:
        """
        Call OpenAI GPT and return a raw response dictionary.

        Args:
            prompt (str): The prompt to send.
            api_key (str): OpenAI API key (platform or BYOK).
            system_prompt (str, optional): System context.
            conversation_history (list, optional): Prior turns.
            complexity (str): 'simple' → gpt-4o-mini; 'complex' → gpt-4o.

        Returns:
            dict: {'text': str, 'model': str, 'tokens_used': int | None}

        Raises:
            AIProviderError: On any OpenAI-side failure.
        """
        try:
            import openai
        except ImportError as exc:
            raise AIProviderError(
                'openai',
                ImportError("openai package is not installed. Run: pip install openai"),
            ) from exc

        if not api_key:
            raise AIProviderError(
                'openai',
                ValueError(
                    "No OpenAI API key is available. "
                    "Set OPENAI_API_KEY in your .env file or enter a BYOK key."
                ),
            )

        # Select model: BYOK model override takes priority; otherwise use complexity-based defaults.
        if model_override:
            model = model_override
        elif complexity == 'complex':
            model = getattr(settings, 'OPENAI_MODEL_COMPLEX', getattr(settings, 'OPENAI_MODEL', 'gpt-4o'))
        else:
            model = getattr(settings, 'OPENAI_MODEL_SIMPLE', 'gpt-4o-mini')

        # Build the messages list in OpenAI's native format.
        # Canonical conversation_history format: [{'role': 'user'|'assistant', 'content': str}]
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            for turn in conversation_history:
                role = turn.get('role', 'user')
                content = turn.get('content', '')
                if role in ('user', 'assistant') and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        try:
            # Instantiate per-call — thread-safe, each BYOK user gets their own client.
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
        except openai.AuthenticationError as exc:
            raise AIProviderError(
                'openai',
                Exception(
                    "OpenAI API key is invalid or expired. "
                    "Please check your API key."
                ),
            ) from exc
        except openai.RateLimitError as exc:
            # Distinguish quota/billing exhaustion from a transient rate limit.
            err_body = str(exc).lower()
            if 'insufficient_quota' in err_body or 'exceeded your current quota' in err_body:
                raise AIProviderError(
                    'openai',
                    Exception(
                        "Your OpenAI API key has reached its usage limit. "
                        "Please check your billing on the OpenAI dashboard."
                    ),
                ) from exc
            raise AIProviderError(
                'openai',
                Exception("OpenAI rate limit reached. Please try again shortly."),
            ) from exc
        except openai.APIError as exc:
            raise AIProviderError(
                'openai',
                Exception(f"OpenAI API call failed: {exc}"),
            ) from exc

        text = response.choices[0].message.content
        model_used = response.model
        tokens_used = getattr(response.usage, 'total_tokens', None)
        if tokens_used is not None:
            tokens_used = int(tokens_used)

        return {'text': text, 'model': model_used, 'tokens_used': tokens_used}

    def _call_anthropic(self, prompt: str, api_key: str, system_prompt: str = None,
                        conversation_history: list = None, complexity: str = 'simple',
                        model_override: str = None) -> dict:
        """
        Call Anthropic Claude and return a raw response dictionary.

        Args:
            prompt (str): The prompt to send.
            api_key (str): Anthropic API key (platform or BYOK).
            system_prompt (str, optional): System context.
            conversation_history (list, optional): Prior turns.
            complexity (str): 'simple' → claude-haiku-4-5; 'complex' → claude-sonnet-4-6.

        Returns:
            dict: {'text': str, 'model': str, 'tokens_used': int | None}

        Raises:
            AIProviderError: On any Anthropic-side failure.
        """
        try:
            import anthropic
        except ImportError as exc:
            raise AIProviderError(
                'anthropic',
                ImportError("anthropic package is not installed. Run: pip install anthropic"),
            ) from exc

        if not api_key:
            raise AIProviderError(
                'anthropic',
                ValueError(
                    "No Anthropic API key is available. "
                    "Set ANTHROPIC_API_KEY in your .env file or enter a BYOK key."
                ),
            )

        # Select model: BYOK model override takes priority; otherwise use complexity-based defaults.
        if model_override:
            model = model_override
        elif complexity == 'complex':
            model = getattr(settings, 'ANTHROPIC_MODEL_COMPLEX', getattr(settings, 'ANTHROPIC_MODEL', 'claude-sonnet-4-6'))
        else:
            model = getattr(settings, 'ANTHROPIC_MODEL_SIMPLE', 'claude-haiku-4-5')
        max_tokens = getattr(settings, 'ANTHROPIC_MAX_TOKENS', 2048)

        # Build the messages list in Anthropic's native format.
        # IMPORTANT: Anthropic does NOT accept role='system' inside the messages list.
        # System context is passed as a separate top-level parameter (see api call below).
        # Canonical conversation_history format: [{'role': 'user'|'assistant', 'content': str}]
        messages = []
        if conversation_history:
            for turn in conversation_history:
                role = turn.get('role', 'user')
                content = turn.get('content', '')
                if role in ('user', 'assistant') and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        try:
            # Instantiate per-call — thread-safe, each BYOK user gets their own client.
            client = anthropic.Anthropic(api_key=api_key)
            create_kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
            # system is an optional top-level param; omit it if not provided.
            if system_prompt:
                create_kwargs['system'] = system_prompt
            response = client.messages.create(**create_kwargs)
        except anthropic.AuthenticationError as exc:
            raise AIProviderError(
                'anthropic',
                Exception(
                    "Anthropic API key is invalid or expired. "
                    "Please check your API key."
                ),
            ) from exc
        except anthropic.RateLimitError as exc:
            # Distinguish quota/billing exhaustion from a transient rate limit.
            err_body = str(exc).lower()
            if 'credit' in err_body or 'billing' in err_body or 'quota' in err_body:
                raise AIProviderError(
                    'anthropic',
                    Exception(
                        "Your Anthropic API key has reached its usage limit. "
                        "Please check your billing on the Anthropic dashboard."
                    ),
                ) from exc
            raise AIProviderError(
                'anthropic',
                Exception("Anthropic rate limit reached. Please try again shortly."),
            ) from exc
        except anthropic.BadRequestError as exc:
            raise AIProviderError(
                'anthropic',
                Exception(
                    "Anthropic rejected the request. "
                    "This may be due to content policy restrictions."
                ),
            ) from exc
        except anthropic.APIError as exc:
            raise AIProviderError(
                'anthropic',
                Exception(f"Anthropic API call failed: {exc}"),
            ) from exc

        text = response.content[0].text
        model_used = response.model
        tokens_used = None
        if hasattr(response, 'usage') and response.usage:
            tokens_used = (
                getattr(response.usage, 'input_tokens', 0)
                + getattr(response.usage, 'output_tokens', 0)
            )

        return {'text': text, 'model': model_used, 'tokens_used': tokens_used}

    # ------------------------------------------------------------------
    # Response normalisation
    # ------------------------------------------------------------------

    def _normalise_response(self, text: str, provider: str, model: str,
                             used_byok: bool, tokens_used=None) -> dict:
        """
        Produce a consistent response dictionary regardless of provider.

        Every caller in PrizmAI receives this exact structure, so no
        feature needs to know which provider was used unless it wants to
        display that information explicitly.

        Args:
            text (str): The AI's response as a plain string.
            provider (str): 'gemini', 'openai', or 'anthropic'.
            model (str): Specific model name e.g. 'gemini-2.5-flash'.
            used_byok (bool): True if a user-supplied BYOK key was used.
            tokens_used (int | None): Total tokens consumed, or None if
                the provider did not return usage metadata.

        Returns:
            dict with keys:
                text        (str)       — AI response text
                provider    (str)       — provider that answered
                model       (str)       — specific model used
                used_byok   (bool)      — True if a BYOK key was used
                tokens_used (int|None)  — token count or None

        Raises:
            AIProviderError: If text is empty (provider returned nothing usable).
        """
        if not text:
            raise AIProviderError(
                provider,
                ValueError("Provider returned an empty response."),
            )
        result = {
            'text': text,
            'provider': provider,
            'model': model,
            'used_byok': used_byok,
            'tokens_used': tokens_used,
        }
        return result

    @staticmethod
    def get_provider_display_name(provider_string):
        """Returns a human-readable display name for a provider key."""
        names = {
            'gemini': 'Google Gemini',
            'openai': 'OpenAI',
            'anthropic': 'Anthropic Claude',
        }
        return names.get(provider_string, 'AI')

    @staticmethod
    def get_model_name(provider, complexity='simple'):
        """Returns the default model name for a provider at a given complexity level."""
        from django.conf import settings
        mapping = {
            'gemini': {
                'simple': getattr(settings, 'GEMINI_MODEL_SIMPLE', 'gemini-2.5-flash-lite'),
                'complex': getattr(settings, 'GEMINI_MODEL_COMPLEX', 'gemini-2.5-flash'),
            },
            'openai': {
                'simple': getattr(settings, 'OPENAI_MODEL_SIMPLE', 'gpt-4o-mini'),
                'complex': getattr(settings, 'OPENAI_MODEL_COMPLEX', 'gpt-4o'),
            },
            'anthropic': {
                'simple': getattr(settings, 'ANTHROPIC_MODEL_SIMPLE', 'claude-haiku-4-5'),
                'complex': getattr(settings, 'ANTHROPIC_MODEL_COMPLEX', 'claude-sonnet-4-6'),
            },
        }
        return mapping.get(provider, {}).get(complexity, 'unknown')
