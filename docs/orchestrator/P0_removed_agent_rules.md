# Removed from .claude/settings.local.json (P0)
# 2 permission-allow rules contained an embedded HA long-lived token in a
# `HATOKEN="<token>" node <script>.mjs` command (added during screenshot work).
# Rules fully removed. No token value retained. If such a command is needed again,
# read the token from the secret store at runtime (project_secrets / env), never inline.
- Bash(HATOKEN=<REDACTED> node shot.mjs)
- Bash(HATOKEN=<REDACTED> node wsdel.mjs)
