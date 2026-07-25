# P10 — Config, Build, Tooling & Ops (findings)

> Scope: `package.json` + npm audit, backend `requirements.txt`, `Dockerfile`/`.dockerignore`/`Procfile`/
> `pytest.ini`, `.env`/`.env.example` secret hygiene, `.gitignore`, `vite/vitest/tsconfig/tailwind/eslint`,
> `public/sw.js`+manifest, `.github`. **Findings-only.**

## Verdict
Secret hygiene + container build are **solid**. Three real production-readiness gaps: **vulnerable FE dependencies**, **unpinned backend deps**, and **no CI**. Plus a dev-mode-by-default footgun.

---

## 🔴 P1

### CFG1 · Multiple HIGH-severity frontend dependency vulnerabilities — incl. the XSS mitigation itself · security
`npm audit` (prod deps) reports several HIGH:
- **axios (1.0–1.17):** **Authentication Bypass via Prototype Pollution in the `validateStatus` merge**, plus SSRF via NO_PROXY normalization bypass (incl. the 127.0.0.0/8 loopback follow-up). axios is the app's **entire API client** — auth-bypass prototype pollution is serious.
- **React Router (@remix-run/router ≤1.23.1):** XSS via open redirects.
- **DOMPurify:** XSS (GHSA-v2wj-7wpq-c8vv) — **this is the exact library P7 credited as the `Chat.tsx` XSS mitigation.** The mitigation is running on a vulnerable version, so the FE1/Chat XSS posture is weaker than P7 stated.
- brace-expansion / form-data (CRLF injection) / glob — mostly transitive/build-time DoS/injection.
**Fix:** `npm audit fix` (most have fixes), bump axios + React Router + **DOMPurify** explicitly, re-verify. **Revisit P7's XSS credit** — it's contingent on updating DOMPurify.

### CFG2 · Backend `requirements.txt` is 0/28 pinned — non-reproducible builds · reproducibility/security
**Zero** of 28 backend deps have a version (`asyncpg`, `redis`, `httpx`, `celery`, `cryptography`, `python-jose`, `passlib`, `pydantic-settings`, … all bare). `Dockerfile` does `pip install -r requirements.txt` → each image build pulls **whatever is latest that day** → non-reproducible builds, surprise breakages, and **security-sensitive libs (cryptography/jose/passlib) float uncontrolled**. No lockfile, no hashes. (Frontend is fine — `package-lock.json` pins.) **Fix:** pin with a lock (pip-tools / uv / `pip freeze`), add `pip-audit` to CI.

### CFG3 · No CI — no automated typecheck / lint / test / audit gate · ops
`.github/` contains only an agent definition; **`.github/workflows/` does not exist**. Nothing enforces `npm run typecheck` / `lint` / `test` / `npm audit` / `pytest` on push. Given CFG1/CFG2, regressions and new vulns land silently. **Fix:** add a CI workflow running FE typecheck+lint+vitest+`npm audit`, BE `python -c "import app.main"`+pytest+`pip-audit`, gate merges. (This is P14-E.)

---

## 🟡 P2

### CFG4 · `ENVIRONMENT` defaults to `"development"` → prod deploy that forgets to set it runs dev-mode silently · security/ops
> ✅ **FIXED 2026-07-26** — default flipped to **`production`** (fail-secure: an unset ENVIRONMENT now yields Secure cookies + JSON logging + no SQL echo + no dev-bypass). Added a validator that normalizes case and **rejects unknown values** (e.g. `prod`, which would otherwise silently disable prod behaviour). Dev is unaffected — `.env.example`/`.env` set `ENVIRONMENT=development` explicitly. Verified: dev valid, `Production`→`production`, `prod`→rejected, unset→`production`.
`config.py:7 ENVIRONMENT: str = "development"`. A deployment that doesn't explicitly set `ENVIRONMENT=production` fails **open to dev mode**:
- **admin cookie `secure = ENVIRONMENT != "development"` → cookie sent over plain HTTP, `SameSite=Lax`** (weaker than the intended `None+Secure`);
- SQLAlchemy `echo=True` → every query logged (perf + info exposure);
- the `REDIS_URL`-localhost fail-fast guard (`config.py:72`) is **skipped** (only fires when `!= development`);
- `ADMIN_DEV_BYPASS` becomes usable if also set.
**Fix:** default to `production`, or **fail-fast** if `ENVIRONMENT` is unset/`development` while a prod signal (e.g. non-localhost `DATABASE_URL`) is present.

---

## ⚪ P3
- **CFG5** Python version drift: `Dockerfile` pins **3.11**; local dev bytecode showed **3.14** (`cpython-314` pyc). Behaviour can differ (3.12+ changes). Align dev to the deployed runtime.
- **CFG6** `Procfile` (gevent/concurrency=100) vs `celery_app.py` (prefork/4) drift — already **D18/R1**; belongs to the ops-config reconciliation here too.
- **CFG7** `sw.js` is push/notification-focused with `skipWaiting()` on install+activate (aggressive immediate SW takeover) and **no `/api/` fetch caching** (so no stale-API risk — good); just confirm asset-cache versioning busts on deploy.

## ✅ Solid (credit)
- **Secret hygiene clean:** `.env` + `backend/.env` git-ignored and **not tracked**; `.env.example` files carry **no real secrets** (placeholders); `.gitignore` covers env/venv/dist/node_modules/pycache.
- **`.dockerignore` excludes `.env`/`.env.*`** (keeps `.env.example`) → **no secret baked into the image** despite `COPY . .`. Also excludes tests/docs/.git → lean image.
- **Dockerfile:** multi-stage (build deps not in runtime), **non-root `app` user**, `HEALTHCHECK` on `/health`, slim base. Good container posture.
- **FE tooling:** `package-lock.json` pins deps; `typecheck` correctly uses `-p tsconfig.app.json` (the `tsc --noEmit`-alone no-op trap is avoided); lint/test scripts present.

## For P14 (QA / ops)
`npm audit` + `pip-audit` clean gate (CFG1/CFG2) · CI pipeline (CFG3) · deploy-time assertion that `ENVIRONMENT=production` + admin cookie is Secure (CFG4) · reproducible-build check (locked deps) · SW update/cache-bust on deploy.
