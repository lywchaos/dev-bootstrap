# Dev Bootstrap

## Quick Reference
- Run tests: `uv run pytest`
- List tools: `uv run devstrap list`
- Dry-run install: `uv run devstrap install --dry-run [tool-name]`

## Architecture
- Tools are declared in `src/devstrap/tools.yaml` — adding a tool requires no code changes
- `src/devstrap/installer.py` handles check/install logic; `cli.py` handles UI/output
- Install priority: package manager → script fallback

## Conventions
- Add YAML comments above `script:` entries to explain non-obvious flags or arguments
- When install commands use flags that aren't self-explanatory, always propose adding a comment (or ask the user)
