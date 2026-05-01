"""
test_ai_router.py — Unit tests for AIRouter (Phase 2: OpenAI + Anthropic).

All external AI SDK calls are mocked with unittest.mock.
No API keys or real network calls are needed to run these tests.

Run with:
    python manage.py test ai_assistant.tests.test_ai_router
"""

import threading
from unittest.mock import MagicMock, patch, call

import httpx
from django.test import SimpleTestCase, override_settings

from ai_assistant.utils.ai_router import AIRouter, AIProviderError


# ===========================================================================
# Exception factory helpers
# ===========================================================================

def _openai_status_error(cls, status_code, message):
    """Create a real openai APIStatusError subclass (AuthenticationError, RateLimitError, …)."""
    import openai  # noqa: PLC0415

    response = httpx.Response(
        status_code=status_code,
        content=b"{}",
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    return cls(message, response=response, body={})


def _openai_connection_error(message="Network error."):
    """Create an openai.APIConnectionError — caught by the generic APIError handler."""
    import openai  # noqa: PLC0415

    return openai.APIConnectionError(
        message=message,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


def _anthropic_status_error(cls, status_code, message):
    """Create a real anthropic APIStatusError subclass."""
    import anthropic  # noqa: PLC0415

    response = httpx.Response(
        status_code=status_code,
        content=b"{}",
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return cls(message, response=response, body={})


def _anthropic_connection_error(message="Network error."):
    """Create an anthropic.APIConnectionError — caught by the generic APIError handler."""
    import anthropic  # noqa: PLC0415

    return anthropic.APIConnectionError(
        message=message,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )


# ===========================================================================
# Mock response builders
# ===========================================================================

def _mock_openai_response(text="Hello!", model="gpt-4o", total_tokens=42):
    """Build a MagicMock that looks like an openai ChatCompletion response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.model = model
    response.usage.total_tokens = total_tokens
    return response


def _mock_anthropic_response(text="Hello!", model="claude-sonnet-4-6",
                              input_tokens=10, output_tokens=20):
    """Build a MagicMock that looks like an anthropic Messages response."""
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = text
    response.model = model
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


# ===========================================================================
# _call_openai tests
# ===========================================================================

@override_settings(OPENAI_MODEL="gpt-4o")
class TestCallOpenAI(SimpleTestCase):
    """Unit tests for AIRouter._call_openai."""

    def setUp(self):
        self.router = AIRouter()
        self.api_key = "sk-test-key"

    def _run(self, prompt="Say hello", api_key=None, system_prompt=None,
             conversation_history=None, mock_response=None):
        """Helper: patch openai.OpenAI, run _call_openai, return (result, mock_client)."""
        if api_key is None:
            api_key = self.api_key
        if mock_response is None:
            mock_response = _mock_openai_response()

        with patch("openai.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            result = self.router._call_openai(
                prompt, api_key, system_prompt, conversation_history
            )
            return result, mock_client, mock_cls

    # --- Success cases -------------------------------------------------------

    def test_success_basic(self):
        """Returns correct text, model, and tokens_used from the response."""
        result, _, _ = self._run(mock_response=_mock_openai_response(
            text="Hi there!", model="gpt-4o", total_tokens=55
        ))
        self.assertEqual(result["text"], "Hi there!")
        self.assertEqual(result["model"], "gpt-4o")
        self.assertEqual(result["tokens_used"], 55)

    def test_client_instantiated_with_api_key(self):
        """openai.OpenAI is instantiated once with the supplied api_key."""
        _, _, mock_cls = self._run(api_key="sk-mykey")
        mock_cls.assert_called_once_with(api_key="sk-mykey")

    def test_model_read_from_settings(self):
        """The model passed to the API comes from settings.OPENAI_MODEL."""
        _, mock_client, _ = self._run()
        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "gpt-4o")

    def test_no_system_no_history_messages_only_user(self):
        """Without system_prompt or history, messages list has only the user prompt."""
        _, mock_client, _ = self._run(prompt="Hello", system_prompt=None,
                                      conversation_history=None)
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(messages, [{"role": "user", "content": "Hello"}])

    def test_system_prompt_prepended_as_system_role(self):
        """system_prompt becomes the first message with role='system'."""
        _, mock_client, _ = self._run(
            prompt="Hi", system_prompt="You are a helpful assistant."
        )
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": "You are a helpful assistant."})
        self.assertEqual(messages[-1], {"role": "user", "content": "Hi"})

    def test_conversation_history_included_before_prompt(self):
        """History turns appear between the system message and the final prompt."""
        history = [
            {"role": "user", "content": "What is PrizmAI?"},
            {"role": "assistant", "content": "It is a project management tool."},
        ]
        _, mock_client, _ = self._run(
            prompt="Tell me more.",
            system_prompt="You are helpful.",
            conversation_history=history,
        )
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1], {"role": "user", "content": "What is PrizmAI?"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "It is a project management tool."})
        self.assertEqual(messages[3], {"role": "user", "content": "Tell me more."})

    def test_history_invalid_roles_excluded(self):
        """History entries with invalid roles (e.g. 'system') are silently dropped."""
        history = [
            {"role": "system", "content": "Injected system"},
            {"role": "user", "content": "Hello"},
        ]
        _, mock_client, _ = self._run(
            prompt="Hi", system_prompt=None, conversation_history=history
        )
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        roles = [m["role"] for m in messages]
        self.assertNotIn("system", roles)

    def test_tokens_used_is_integer(self):
        """tokens_used in the returned dict is an int."""
        result, _, _ = self._run(mock_response=_mock_openai_response(total_tokens=100))
        self.assertIsInstance(result["tokens_used"], int)

    # --- Error cases ---------------------------------------------------------

    def test_missing_api_key_raises_ai_provider_error(self):
        """Empty api_key raises AIProviderError before making any API call."""
        with self.assertRaises(AIProviderError) as ctx:
            self.router._call_openai("Hello", api_key="")
        self.assertEqual(ctx.exception.provider, "openai")

    def test_authentication_error_raises_ai_provider_error(self):
        """openai.AuthenticationError is caught and re-raised as AIProviderError."""
        import openai

        exc = _openai_status_error(openai.AuthenticationError, 401, "Invalid API key")
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_openai("Hello", api_key=self.api_key)

        self.assertEqual(ctx.exception.provider, "openai")
        self.assertIn("invalid or expired", str(ctx.exception).lower())

    def test_rate_limit_error_transient_raises_try_again(self):
        """A transient RateLimitError (no quota keywords) says 'try again'."""
        import openai

        exc = _openai_status_error(openai.RateLimitError, 429, "Too many requests. Please slow down.")
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_openai("Hello", api_key=self.api_key)

        self.assertIn("try again", str(ctx.exception).lower())

    def test_rate_limit_error_insufficient_quota_raises_billing_message(self):
        """RateLimitError with 'insufficient_quota' in message triggers billing prompt."""
        import openai

        exc = _openai_status_error(
            openai.RateLimitError, 429,
            "You exceeded your current quota. insufficient_quota"
        )
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_openai("Hello", api_key=self.api_key)

        msg = str(ctx.exception).lower()
        self.assertIn("usage limit", msg)
        self.assertIn("billing", msg)

    def test_rate_limit_error_exceeded_current_quota_raises_billing_message(self):
        """RateLimitError with 'exceeded your current quota' triggers billing prompt."""
        import openai

        exc = _openai_status_error(
            openai.RateLimitError, 429,
            "You exceeded your current quota, please check your plan."
        )
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_openai("Hello", api_key=self.api_key)

        self.assertIn("billing", str(ctx.exception).lower())

    def test_generic_api_error_raises_ai_provider_error_with_message(self):
        """A general openai.APIError is caught and wrapped with the original message."""
        exc = _openai_connection_error("Network error.")
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.chat.completions.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_openai("Hello", api_key=self.api_key)

        self.assertEqual(ctx.exception.provider, "openai")
        self.assertIn("api call failed", str(ctx.exception).lower())


# ===========================================================================
# _call_anthropic tests
# ===========================================================================

@override_settings(ANTHROPIC_MODEL="claude-sonnet-4-6", ANTHROPIC_MAX_TOKENS=2048)
class TestCallAnthropic(SimpleTestCase):
    """Unit tests for AIRouter._call_anthropic."""

    def setUp(self):
        self.router = AIRouter()
        self.api_key = "sk-ant-test"

    def _run(self, prompt="Say hello", api_key=None, system_prompt=None,
             conversation_history=None, mock_response=None):
        """Helper: patch anthropic.Anthropic, run _call_anthropic, return (result, mock_client)."""
        if api_key is None:
            api_key = self.api_key
        if mock_response is None:
            mock_response = _mock_anthropic_response()

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = self.router._call_anthropic(
                prompt, api_key, system_prompt, conversation_history
            )
            return result, mock_client, mock_cls

    # --- Success cases -------------------------------------------------------

    def test_success_basic(self):
        """Returns correct text, model, and combined token count."""
        result, _, _ = self._run(mock_response=_mock_anthropic_response(
            text="Hello from Claude!", model="claude-sonnet-4-6",
            input_tokens=15, output_tokens=25
        ))
        self.assertEqual(result["text"], "Hello from Claude!")
        self.assertEqual(result["model"], "claude-sonnet-4-6")
        self.assertEqual(result["tokens_used"], 40)  # 15 + 25

    def test_client_instantiated_with_api_key(self):
        """anthropic.Anthropic is instantiated once with the supplied api_key."""
        _, _, mock_cls = self._run(api_key="sk-ant-mykey")
        mock_cls.assert_called_once_with(api_key="sk-ant-mykey")

    def test_model_and_max_tokens_from_settings(self):
        """model and max_tokens are read from settings."""
        _, mock_client, _ = self._run()
        kwargs = mock_client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-sonnet-4-6")
        self.assertEqual(kwargs["max_tokens"], 2048)

    def test_system_prompt_passed_as_top_level_param(self):
        """system_prompt is passed as 'system=' kwarg, NOT inside messages list."""
        _, mock_client, _ = self._run(
            prompt="Hello", system_prompt="You are a PM assistant."
        )
        kwargs = mock_client.messages.create.call_args.kwargs
        # system= kwarg should be present at the top level
        self.assertEqual(kwargs.get("system"), "You are a PM assistant.")
        # None of the messages should have role='system'
        roles = [m["role"] for m in kwargs["messages"]]
        self.assertNotIn("system", roles)

    def test_no_system_prompt_system_kwarg_absent(self):
        """When system_prompt is None, the 'system' key is NOT passed at all."""
        _, mock_client, _ = self._run(prompt="Hello", system_prompt=None)
        kwargs = mock_client.messages.create.call_args.kwargs
        self.assertNotIn("system", kwargs)

    def test_no_history_messages_only_user_prompt(self):
        """Without history, messages has exactly one user entry."""
        _, mock_client, _ = self._run(prompt="Hello", conversation_history=None)
        kwargs = mock_client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "Hello"}])

    def test_conversation_history_included_before_prompt(self):
        """History turns appear before the final user prompt in messages."""
        history = [
            {"role": "user", "content": "What is Spectra?"},
            {"role": "assistant", "content": "Spectra is the AI layer."},
        ]
        _, mock_client, _ = self._run(
            prompt="Tell me more.", conversation_history=history
        )
        messages = mock_client.messages.create.call_args.kwargs["messages"]
        self.assertEqual(messages[0], {"role": "user", "content": "What is Spectra?"})
        self.assertEqual(messages[1], {"role": "assistant", "content": "Spectra is the AI layer."})
        self.assertEqual(messages[2], {"role": "user", "content": "Tell me more."})

    def test_tokens_used_is_sum_of_input_and_output(self):
        """tokens_used = input_tokens + output_tokens."""
        result, _, _ = self._run(mock_response=_mock_anthropic_response(
            input_tokens=100, output_tokens=200
        ))
        self.assertEqual(result["tokens_used"], 300)

    # --- Error cases ---------------------------------------------------------

    def test_missing_api_key_raises_ai_provider_error(self):
        """Empty api_key raises AIProviderError before making any API call."""
        with self.assertRaises(AIProviderError) as ctx:
            self.router._call_anthropic("Hello", api_key="")
        self.assertEqual(ctx.exception.provider, "anthropic")

    def test_authentication_error_raises_ai_provider_error(self):
        """anthropic.AuthenticationError is re-raised as AIProviderError."""
        import anthropic

        exc = _anthropic_status_error(anthropic.AuthenticationError, 401, "Invalid API key")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_anthropic("Hello", api_key=self.api_key)

        self.assertEqual(ctx.exception.provider, "anthropic")
        self.assertIn("invalid or expired", str(ctx.exception).lower())

    def test_rate_limit_error_transient_raises_try_again(self):
        """A transient RateLimitError (no quota keywords) says 'try again'."""
        import anthropic

        exc = _anthropic_status_error(
            anthropic.RateLimitError, 429, "Too many requests. Please slow down."
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_anthropic("Hello", api_key=self.api_key)

        self.assertIn("try again", str(ctx.exception).lower())

    def test_rate_limit_error_credit_balance_raises_billing_message(self):
        """RateLimitError with 'credit' in message triggers billing prompt."""
        import anthropic

        exc = _anthropic_status_error(
            anthropic.RateLimitError, 429,
            "Your credit balance is too low to access the Anthropic API."
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_anthropic("Hello", api_key=self.api_key)

        msg = str(ctx.exception).lower()
        self.assertIn("usage limit", msg)
        self.assertIn("billing", msg)

    def test_rate_limit_error_quota_keyword_raises_billing_message(self):
        """RateLimitError with 'quota' in message triggers billing prompt."""
        import anthropic

        exc = _anthropic_status_error(
            anthropic.RateLimitError, 429, "Monthly quota exceeded."
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_anthropic("Hello", api_key=self.api_key)

        self.assertIn("billing", str(ctx.exception).lower())

    def test_bad_request_error_raises_content_policy_message(self):
        """anthropic.BadRequestError is raised with a content policy message."""
        import anthropic

        exc = _anthropic_status_error(
            anthropic.BadRequestError, 400, "Content policy violation."
        )
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_anthropic("Hello", api_key=self.api_key)

        self.assertIn("content policy", str(ctx.exception).lower())

    def test_generic_api_error_raises_ai_provider_error_with_message(self):
        """A general anthropic.APIError is caught and wrapped with the original message."""
        exc = _anthropic_connection_error("Network failure.")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = exc

            with self.assertRaises(AIProviderError) as ctx:
                self.router._call_anthropic("Hello", api_key=self.api_key)

        self.assertEqual(ctx.exception.provider, "anthropic")
        self.assertIn("api call failed", str(ctx.exception).lower())


# ===========================================================================
# complete() routing tests
# ===========================================================================

class TestCompleteRouting(SimpleTestCase):
    """
    Tests for AIRouter.complete() dispatch logic.

    _resolve_provider is mocked to avoid any database access.
    Individual provider call methods are mocked to return canned raw responses.
    """

    def setUp(self):
        self.router = AIRouter()
        self.mock_user = MagicMock()

    def _complete(self, provider, api_key="sk-test", is_byok=False,
                  raw_text="Hello!", raw_model="test-model", raw_tokens=10,
                  prompt="Say hello", system_prompt=None, conversation_history=None):
        """
        Helper: mock _resolve_provider and the correct _call_* method,
        call complete(), and return the result.
        """
        raw = {"text": raw_text, "model": raw_model, "tokens_used": raw_tokens}
        call_method = f"_call_{provider}"

        with patch.object(self.router, "_resolve_provider",
                          return_value=(provider, api_key, is_byok, None)):
            with patch.object(self.router, call_method, return_value=raw) as mock_call:
                result = self.router.complete(
                    prompt, user=self.mock_user,
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                )
                return result, mock_call

    # --- Routing dispatch ----------------------------------------------------

    def test_routes_to_openai(self):
        """complete() calls _call_openai when provider resolves to 'openai'."""
        result, mock_call = self._complete("openai")
        mock_call.assert_called_once()
        self.assertEqual(result["provider"], "openai")

    def test_routes_to_anthropic(self):
        """complete() calls _call_anthropic when provider resolves to 'anthropic'."""
        result, mock_call = self._complete("anthropic")
        mock_call.assert_called_once()
        self.assertEqual(result["provider"], "anthropic")

    def test_routes_to_gemini(self):
        """complete() calls _call_gemini when provider resolves to 'gemini'."""
        result, mock_call = self._complete("gemini")
        mock_call.assert_called_once()
        self.assertEqual(result["provider"], "gemini")

    def test_provider_call_receives_correct_arguments(self):
        """prompt, api_key, system_prompt, and conversation_history are forwarded."""
        history = [{"role": "user", "content": "hi"}]
        _, mock_call = self._complete(
            "openai", api_key="sk-special",
            prompt="Summarise", system_prompt="Be brief.",
            conversation_history=history,
        )
        mock_call.assert_called_once_with("Summarise", "sk-special", "Be brief.", history)

    # --- Normalised response -------------------------------------------------

    def test_normalised_response_contains_all_five_keys(self):
        """complete() always returns a dict with text, provider, model, used_byok, tokens_used."""
        result, _ = self._complete("openai")
        for key in ("text", "provider", "model", "used_byok", "tokens_used"):
            self.assertIn(key, result, msg=f"Key '{key}' missing from normalised response")

    def test_normalised_response_values_are_correct_types(self):
        """Each field in the response has the expected type."""
        result, _ = self._complete(
            "openai", raw_text="Hi", raw_model="gpt-4o", raw_tokens=42
        )
        self.assertIsInstance(result["text"], str)
        self.assertIsInstance(result["provider"], str)
        self.assertIsInstance(result["model"], str)
        self.assertIsInstance(result["used_byok"], bool)
        self.assertIsInstance(result["tokens_used"], int)

    def test_used_byok_false_for_platform_key(self):
        """used_byok=False when _resolve_provider returns is_byok=False."""
        result, _ = self._complete("openai", is_byok=False)
        self.assertFalse(result["used_byok"])

    def test_used_byok_true_for_byok_key(self):
        """used_byok=True when _resolve_provider returns is_byok=True."""
        result, _ = self._complete("anthropic", is_byok=True)
        self.assertTrue(result["used_byok"])

    def test_text_and_model_propagated_correctly(self):
        """text and model from the raw provider response appear in the normalised result."""
        result, _ = self._complete(
            "openai", raw_text="Board summary here.", raw_model="gpt-4o"
        )
        self.assertEqual(result["text"], "Board summary here.")
        self.assertEqual(result["model"], "gpt-4o")

    # --- Error propagation ---------------------------------------------------

    def test_ai_provider_error_propagates_from_call_method(self):
        """AIProviderError raised by a provider call method surfaces unchanged."""
        original_error = Exception("API down")
        with patch.object(self.router, "_resolve_provider",
                          return_value=("openai", "sk-test", False, None)):
            with patch.object(self.router, "_call_openai",
                              side_effect=AIProviderError("openai", original_error)):
                with self.assertRaises(AIProviderError) as ctx:
                    self.router.complete("Hello", user=self.mock_user)
        self.assertEqual(ctx.exception.provider, "openai")

    def test_unexpected_exception_wrapped_in_ai_provider_error(self):
        """An unhandled exception from a provider call is wrapped as AIProviderError."""
        with patch.object(self.router, "_resolve_provider",
                          return_value=("openai", "sk-test", False, None)):
            with patch.object(self.router, "_call_openai",
                              side_effect=RuntimeError("Unexpected crash")):
                with self.assertRaises(AIProviderError):
                    self.router.complete("Hello", user=self.mock_user)


# ===========================================================================
# Gemini thread-safety tests
# ===========================================================================

class TestGeminiThreadSafety(SimpleTestCase):
    """
    Verify the module-level lock is used in _call_gemini to prevent concurrent
    BYOK requests from clobbering the global genai.configure() call.
    """

    def test_configure_lock_is_defined_at_module_level(self):
        """_GEMINI_CONFIGURE_LOCK exists and is a threading lock."""
        from ai_assistant.utils import ai_router

        self.assertTrue(hasattr(ai_router, "_GEMINI_CONFIGURE_LOCK"))
        lock = ai_router._GEMINI_CONFIGURE_LOCK
        # threading.Lock() returns a _thread.lock; hasattr is the safe check
        self.assertTrue(hasattr(lock, "acquire") and hasattr(lock, "release"))

    def test_call_gemini_acquires_and_releases_lock(self):
        """_call_gemini enters the context manager on _GEMINI_CONFIGURE_LOCK."""
        from ai_assistant.utils import ai_router

        mock_lock = MagicMock()
        mock_lock.__enter__ = MagicMock(return_value=None)
        mock_lock.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.text = "Hello!"
        mock_response.usage_metadata = None

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        router = AIRouter()

        with patch.object(ai_router, "_GEMINI_CONFIGURE_LOCK", mock_lock):
            with patch("google.generativeai.configure"):
                with patch("google.generativeai.GenerativeModel", return_value=mock_model):
                    router._call_gemini("Say hello", api_key="test-gemini-key")

        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()

    def test_concurrent_gemini_calls_serialised(self):
        """
        Simulate two concurrent calls with different BYOK keys.
        Verify that genai.configure is called with both keys (not just one),
        and the lock prevents the second from running before the first finishes.
        """
        configure_calls = []

        def fake_configure(api_key):
            configure_calls.append(api_key)

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.text = "response"
        mock_response.usage_metadata = None

        router = AIRouter()

        with patch("google.generativeai.configure", side_effect=fake_configure):
            with patch("google.generativeai.GenerativeModel") as mock_model_cls:
                instance = MagicMock()
                instance.generate_content.return_value = mock_response
                mock_model_cls.return_value = instance

                results = []
                errors = []

                def worker(key):
                    try:
                        results.append(router._call_gemini("Hello", api_key=key))
                    except Exception as exc:
                        errors.append(exc)

                t1 = threading.Thread(target=worker, args=("key-user-1",))
                t2 = threading.Thread(target=worker, args=("key-user-2",))
                t1.start()
                t2.start()
                t1.join()
                t2.join()

        self.assertEqual(len(errors), 0, f"Errors in threads: {errors}")
        self.assertEqual(len(results), 2)
        # Both keys must have been configured (not one silently dropped)
        self.assertIn("key-user-1", configure_calls)
        self.assertIn("key-user-2", configure_calls)
