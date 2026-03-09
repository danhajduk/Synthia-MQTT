# Addon Theme CSS Audit

Date: 2026-03-09
Scope: `frontend/src/styles.css`, `frontend/src/theme/*.css`, `frontend/src/theme/themes/*.css`

## Findings

1. Prior hardcoded background literals (`white`, `black`) existed in mix expressions.
2. Prior fallback text and border token usage was split between addon-local and core-token names.
3. Prior spacing/radius/shadow usage mixed hardcoded values with non-`--sx-*` fallback chains.

## Remediation Applied (Tasks 120-129)

1. Added resolved token aliases in `frontend/src/theme/tokens.css` for:
   - text (`--sx-text-resolved`, `--sx-text-muted-resolved`, `--sx-text-on-primary-resolved`)
   - borders (`--sx-border-resolved`)
   - backgrounds (`--sx-bg-resolved`, `--sx-panel-resolved`)
   - spacing (`--sx-space-*-resolved`)
   - radii (`--sx-radius-*-resolved`)
   - shadows (`--sx-shadow-*-resolved`)
2. Replaced hardcoded background literals and default text/border usages with resolved `--sx-*` tokens across:
   - `frontend/src/theme/base.css`
   - `frontend/src/theme/components.css`
   - `frontend/src/styles.css`
3. Replaced component radius/shadow usage with resolved `--sx-radius-*` and `--sx-shadow-*` aliases.
4. Updated spacing declarations in primary UI layout styles to use `--sx-space-*` aliases.

## Residual Notes

- Semantic state accents (`--color-primary`, `--color-warning`, `--color-danger`) remain intentional for status emphasis and are not hardcoded literals.
