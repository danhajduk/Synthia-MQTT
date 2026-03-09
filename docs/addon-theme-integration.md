# Addon Theme Integration

## Purpose

This addon UI consumes Synthia Core shared theme assets and class patterns so embedded rendering inside Core iframes follows the same visual language.

## Source Of Truth

- Synthia Core shared theme tokens/classes are the design source-of-truth.
- Addon theme files provide fallback compatibility when Core tokens are unavailable.
- Addon custom styles are scoped under `:root.core-theme-fallback` to avoid overriding injected Core styles.

## Theme Entry Flow

1. Frontend bootstrap (`frontend/src/app.js`) calls `ensureSharedThemeEntry()` to load `/ui/theme/index.css`.
2. Theme imports are resolved through `frontend/src/theme/index.css`:
   - `tokens.css`
   - `base.css`
   - `components.css`
   - `themes/light.css`
   - `themes/dark.css`
3. Runtime detects iframe context and Core token availability:
   - `in-iframe` class for embedded behavior
   - `core-theme-detected` when Core tokens are present
   - `core-theme-fallback` when fallback styling is required

## Shared Class Mapping

Bootstrap adds shared classes to addon markup for style parity:

- cards/containers: `card`
- buttons: `btn`, `btn-primary`, `btn-secondary`
- controls: `sx-input`
- status surfaces: `sx-status`
- list primitives: `sx-list`, `sx-list-item`

Fallback theme layer defines `sx-table`/table primitives for Core-aligned tabular/list surfaces.

## Fallback Strategy

Resolved aliases in `tokens.css` route `--sx-*` tokens to Core tokens first, then local addon fallbacks:

- color/text/border/background aliases
- radius/shadow aliases
- spacing aliases

Where mixed-color rules are used, direct background fallback declarations are included before `color-mix(...)` rules.

## Verification

Run all related checks:

```bash
npm --prefix frontend run build
./scripts/verify-theme-paths.sh all
./scripts/verify-iframe-theme.sh
./scripts/verify-iframe-style-language.sh
```

## Addon-Specific Exceptions

These styles remain addon-specific by design and are not direct Core replacements:

1. Setup wizard progress state visuals (`.steps li.active/.done`) to preserve task-flow clarity.
2. Optional docker group runtime status accents (`failed|starting|active`) tied to addon operational semantics.
3. Iframe compact layout constraints (`html.in-iframe .layout`, hidden hero banner) for embedded UX density.
4. Status mini-cards (`.home-mini*`) used by addon dashboard snapshots.

All exceptions are still token-driven and scoped to fallback mode where applicable.
