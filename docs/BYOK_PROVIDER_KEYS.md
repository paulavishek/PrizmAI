# Getting Your Own AI API Keys (BYOK) — Anthropic & OpenAI

PrizmAI's AI features (Spectra chat, budgets, coaching, discovery, retrospectives, etc.)
run on one of three providers: **Google Gemini**, **Anthropic Claude**, or **OpenAI GPT**.
With **BYOK (Bring Your Own Key)** you supply your own provider API key, so AI usage runs
on *your* quota and billing instead of the shared workspace key.

This guide covers how to obtain a key for **Anthropic** and **OpenAI**. (Gemini keys come
from [Google AI Studio](https://aistudio.google.com) → *Get API Key* → *Create API key*.)

> The same steps are also shown inline in the app under **Profile → AI Provider
> Preferences → Use Your Own API Key (BYOK)**. This document is the fuller reference.

---

## Where you enter the key in PrizmAI

There are two places a BYOK key can live:

| Scope | Where | Who |
|-------|-------|-----|
| **Personal** | Profile → *AI Provider Preferences* → **Use Your Own API Key (BYOK)** | Any signed-in user (applies to your own AI usage) |
| **Workspace** | Org Admin → *Workspace AI Settings* | Org Admins only (applies to everyone in the workspace who hasn't set a personal key) |

In both places you: pick the **provider**, paste the **API key**, choose a **model**, and
save. On save, PrizmAI makes a tiny test call to confirm the key works ("verify"), then
stores it **encrypted** — the key is never logged and never shown again (you'll only see a
masked `••••XXXX` with the last 4 characters).

---

## Anthropic (Claude)

1. Go to **[console.anthropic.com](https://console.anthropic.com)**.
2. Sign in, or create an account.
3. Go to **Settings → API Keys → Create Key**.
4. Give the key a name (e.g. `PrizmAI`), create it, and **copy** the value.
   - Anthropic keys look like `sk-ant-...`.
5. Paste it into the BYOK **API key** field in PrizmAI and pick a model.

**Billing:** Anthropic requires purchased **credits** or a paid plan before the API will
respond. Add credits at **[console.anthropic.com/settings/billing](https://console.anthropic.com/settings/billing)**.
If verification fails with a usage/credit error, top up your balance and try again.

**Which Claude model to pick:** PrizmAI's platform default ladder uses **Claude Sonnet 5**
for light/medium tasks and **Claude Opus 4.8** for heavy tasks. For a personal BYOK key,
Sonnet 5 is a good all-round default; choose Opus 4.8 if you want the strongest reasoning
and don't mind higher cost. (See the BYOK single-model note below.)

---

## OpenAI (GPT)

1. Go to **[platform.openai.com](https://platform.openai.com)**.
2. Sign in, or create an account.
3. Go to **Settings → API Keys → Create new secret key**.
4. **Copy the key immediately** — OpenAI shows a secret key **only once** at creation. If
   you navigate away without copying it, you'll have to create a new one.
   - OpenAI keys look like `sk-...`.
5. Paste it into the BYOK **API key** field in PrizmAI and pick a model.

**Billing:** OpenAI requires a paid account with **billing set up** at
**[platform.openai.com/settings/organization/billing](https://platform.openai.com/settings/organization/billing)**
before the API will respond.

**Which GPT model to pick:** PrizmAI's platform default ladder uses the **GPT-5.6**
generation — **gpt-5.6-terra** for light tasks and **gpt-5.6-sol** for heavy tasks. Pick
whichever the model dropdown offers; if you type a custom model string, use the exact id
from OpenAI's model list (model names change over time).

---

## What "verify" does, and the encryption

- **Verify:** before saving, PrizmAI sends a one-word test prompt ("Hi") to the provider
  with your key (and chosen model). If the provider answers, the key is accepted; if not
  (bad key, no billing, wrong model name), the save is rejected with an error so you can
  fix it.
- **Storage:** the key is encrypted with Fernet (AES) before it touches the database. It is
  never written to logs and never displayed after saving — the UI only shows the masked
  last-4.
- **Removing a key:** tick **Remove my API key** in the BYOK section and save to clear it;
  AI usage then falls back to the workspace/platform key.

---

## Known limitation — one model per BYOK key

A BYOK key stores **one** model, and that single model is used for **all** AI tasks
regardless of whether the task is light or heavy. This means BYOK users don't get the
automatic light-vs-heavy tiering that the platform keys use (where light tasks
transparently route to a cheaper model and heavy tasks to a stronger one).

Practically: pick a model that's a good all-round fit for your workflow. If you mostly do
heavy analysis, pick the stronger model; if you mostly do quick chats and formatting, a
lighter/cheaper model keeps your costs down. Per-tier BYOK model selection may be added in
a future release.
