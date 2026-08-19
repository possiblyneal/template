# Script Design & Patterns

## Designing Scripts for Agentic Use

Scripts must work in non-interactive agent execution environments.

**Hard requirements:**
- No interactive prompts — accept input via flags, env vars, or stdin
- Provide useful `--help` output
- Emit helpful, specific error messages
- Prefer structured output (JSON, CSV, TSV) to stdout
- Send diagnostics and progress to stderr

**Recommended:**
- Self-contained dependencies
- Safe defaults
- Meaningful, documented exit codes
- `--dry-run` support for destructive operations
- Idempotent behavior when retries are likely
- Clear input constraints (reject ambiguous input with guidance)
- Predictable output size; support `--offset`/`--output` for large results

**Solve, don't punt:** Handle error conditions in the script itself. Create files with defaults when missing, provide fallbacks for permission errors, return useful error messages rather than raw stack traces.

**Good:**
```python
def process_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f"File {path} not found, creating default")
        with open(path, "w") as f:
            f.write("")
        return ""
    except PermissionError:
        print(f"Cannot access {path}, using default")
        return ""
```

**Avoid voodoo constants** — document all configuration values:
```python
REQUEST_TIMEOUT = 30  # HTTP requests typically complete within 30s
MAX_RETRIES = 3       # Most intermittent failures resolve by retry 2
```

---

## Plan-Validate-Execute Pattern

For skills involving batch operations, destructive changes, or high-stakes operations:

1. **Create a plan file** (e.g., `changes.json`) describing intended changes
2. **Validate the plan** with a script before executing
3. **Execute** only after validation passes
4. **Verify** the result

Make validation scripts verbose with specific error messages like "Field 'signature_date' not found. Available fields: customer_name, order_total, signature_date_signed" to help the agent fix issues without guessing.
