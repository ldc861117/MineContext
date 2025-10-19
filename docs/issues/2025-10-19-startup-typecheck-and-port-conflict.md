Title: Fix dev startup failures: TS6133 errors and backend port conflict

Date: 2025-10-19
Author: Droid (Factory AI)

Summary
- Running `./start-dev.sh` failed due to:
  1) TypeScript TS6133 errors from unused imports/variables in frontend components
  2) Backend FastAPI server failed to bind `127.0.0.1:8000` (address in use)
  3) PostHog upload SSL error observed during logs (benign, not blocking)

Reproduction
1. Execute `./start-dev.sh`
2. Observe errors:
   - TS6133 in:
     - `frontend/src/renderer/src/pages/home/components/to-do-card/index.tsx` (unused IconEdit)
     - `frontend/src/renderer/src/pages/settings/settings.tsx` (unused loadingGif and isLoading)
   - Backend: `ERROR: [Errno 48] ... ('127.0.0.1', 8000): address already in use`

Root Cause
- Frontend: stale/unused symbols after recent UI refactors.
- Backend: dev launcher binds a fixed port (8000); if occupied (leftover process or other app), startup aborts.

Fix
- Frontend TS errors:
  - Remove unused `IconEdit` import.
  - Remove unused `loadingGif` import and dead `isLoading` state/updates.
- Backend port conflict:
  - Add automatic fallback in `opencontext/cli.py:start_web_server` to try subsequent ports when 8000 is in use (up to 20 attempts). Logs a warning with the new port.
  - Frontend already supports dynamic backend port via IPC and runtime `axios` baseURL updates; packaged flow unaffected. Dev CLI now resilient too.

Validation
- pnpm install (frontend) completed successfully.
- Type checks pass: `pnpm run typecheck` → 0 errors.
- Linting currently reports many pre-existing warnings/errors unrelated to this fix. Not gated for this change.
- Full build cannot be executed in CI container (macOS-specific Python externals). Local macOS build path remains unchanged.

Follow-ups
- Address ESLint config violations across the repo (separate task).
- Optionally add a configurable env var for dev server port.

Links
- PR: <to be filled after PR is opened>
