# Pre-Launch TODO

Small, non-blocking follow-ups identified during the frontend self-hosting work
(commit `70dd469`, branch `feature/dashboard-modernization`). Neither blocks launch.

---

## 1. Confirm `collectstatic` runs in the GCP deploy pipeline

**Why:** All frontend libraries are now self-hosted under `static/vendor/` instead of
loaded from public CDNs (so a CDN outage can't break features). For this to work in
production, the deploy must copy those files to where the server serves static assets.

**What to do:**
- Ensure the GCP deploy step runs `python manage.py collectstatic --noinput`.
- After deploying, sanity-check that e.g. `https://<your-domain>/static/vendor/bootstrap.min.css`
  returns 200 (not 404).
- If a file 404s, `collectstatic` didn't run or static serving is misconfigured — pages
  will break.

---

## 2. Self-host the icon fonts (Font Awesome + Bootstrap Icons)

**Why (and why it was deferred):** These are the only libraries still loaded from a CDN.
They were deferred because their CSS pulls in separate webfont binary files via relative
paths, which is fiddly to bundle correctly, and their failure mode is only *missing icons*
(cosmetic) rather than broken functionality. But since they load on **every page** (via
`templates/base.html`), self-hosting them removes the last CDN dependency.

**Still on CDN (to replace):**
- Font Awesome 6.4.0 — `templates/base.html:18`, `templates/kanban/welcome.html:14`,
  `templates/kanban/onboarding/base_onboarding.html:10`
- Bootstrap Icons 1.11.0 — `templates/base.html:21`,
  `templates/kanban/onboarding/base_onboarding.html:11`

**What to do:**
- Download each icon font's full distribution (the CSS **plus** its `webfonts/` or `fonts/`
  binary files) into `static/vendor/` (e.g. `static/vendor/fontawesome/`,
  `static/vendor/bootstrap-icons/`).
- Point the `<link>` tags at the local CSS via `{% static %}` with the existing
  `?v={{ STATIC_VERSION|default:'12' }}` cache-bust pattern.
- **Verify the font files actually load** (open DevTools → Network, confirm the `.woff2`
  files return 200 and icons render) — the relative font paths inside the CSS are the easy
  thing to get wrong.
- Follow the existing self-hosted precedent in `static/vendor/` (see commit `70dd469`).

**Dead/test files that also reference these CDNs — ignore or delete, not in scope:**
`templates/kanban/drag_drop_demo.html`, `templates/kanban/test_ai_features.html`,
`static/test_ai_explainability.html`, `static/column-scroll-test.html`,
`static/test_js_debug.html`, `templates/kanban/board_analytics_backup.html`.
