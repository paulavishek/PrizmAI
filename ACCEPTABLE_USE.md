# Acceptable Use & Responsible Deployment

PrizmAI is an open-source, AI-powered **project management** platform. Its AI
assistant, **Spectra**, and every other AI feature exist to help you plan, track,
and reason about projects, tasks, teams, and product work. This document explains
what the software is intended for, what it must not be used for, and — because
PrizmAI can be self-hosted with your own AI provider key — who is responsible for
usage of a given deployment.

## What Spectra is for

Spectra is a project-management assistant. It answers questions about your boards,
tasks, deadlines, risks, team workload, strategy, and the PrizmAI product itself.
By design it declines requests that fall outside that scope, and it will not
provide dangerous, harmful, or illegal content or instructions regardless of how a
request is framed. This scope limit is enforced in Spectra's system instructions
and by the underlying AI provider's own safety filters.

## Prohibited uses

You may not use PrizmAI, Spectra, or any AI feature to:

- Generate, obtain, or facilitate **dangerous, harmful, or illegal content or
  instructions** — including (but not limited to) weapons, explosives, illicit
  drugs, self-harm, or malware/hacking.
- Attempt to **jailbreak, prompt-inject, or otherwise circumvent** Spectra's scope
  and safety guardrails, or its role-based access controls.
- Violate the Acceptable Use Policy / Terms of Service of the AI provider whose
  API key powers the deployment (e.g. the
  [Google Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms)),
  or any applicable law.

## Who is responsible — the deployment boundary

PrizmAI is **Bring-Your-Own-Key (BYOK)**: an AI provider API key (Google Gemini,
and optionally OpenAI or Anthropic) is required to enable AI features, and that key
belongs to whoever runs the instance. Because of this, responsibility depends on
how PrizmAI is deployed:

- **Self-hosted / BYOK** (e.g. the downloadable Local App Runner, a one-click
  Deploy-to-Railway/Render instance, or any deployment you run yourself): You
  supply your own AI provider API key and run the software on your own account and
  infrastructure. **You are responsible** for how the instance is used — including
  by anyone you grant access to — and for complying with your AI provider's terms.
  AI requests are made under *your* key and are subject to *that provider's* safety
  systems and terms of service.

- **A hosted instance you operate for others:** If you stand up a public or shared
  PrizmAI instance using your own key, you are the operator of that instance and
  are responsible for its use and any abuse that occurs on it.

The project maintainers provide PrizmAI as open-source software and do not operate,
monitor, or control instances that other people deploy.

## No warranty

PrizmAI is provided "as is", without warranty of any kind, as set out in the
project [LICENSE](LICENSE). AI-generated output may be inaccurate or incomplete and
should be reviewed before you act on it. You are responsible for your use of the
software, for safeguarding your API keys (see [SECURITY.md](SECURITY.md)), and for
complying with all applicable terms and laws.

## Reporting

To report a **security vulnerability**, follow [SECURITY.md](SECURITY.md).
For questions about acceptable use, open a GitHub issue or contact the maintainer.
