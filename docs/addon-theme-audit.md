# Addon Theme CSS Audit

Date: 2026-03-09
Scope: `frontend/src/styles.css`, `frontend/src/theme/*.css`, `frontend/src/theme/themes/*.css`

## Findings

1. Background colors were using hardcoded color literals in mixed expressions (`white`, `black`) and direct fallback patterns.
2. Background token usage was inconsistent between component-layer and page-layer CSS.
3. One hardcoded text color remains (`#fff` in button fallback) and is tracked for Task 125.

## Remediation Applied (Tasks 120-124 Batch)

1. Added resolved shared background tokens in `frontend/src/theme/tokens.css`:
   - `--sx-bg-resolved`
   - `--sx-panel-resolved`
2. Updated background rendering in:
   - `frontend/src/theme/base.css`
   - `frontend/src/theme/components.css`
   - `frontend/src/styles.css`
3. Replaced background hardcoded color literals in `color-mix()` expressions with shared/fallback token chains.

## Remaining Hardcoded Color Tokens

- `frontend/src/theme/components.css`: `color: #fff;`

This remaining hardcoded text color will be handled in the text-color task batch (Task 125).
