"""Capability slots — pluggable feature blocks a department template can declare.

Each capability bundles:

  * a backend router (FastAPI) — the HTTP surface for the feature
  * a set of permission action keys gated against `department_role_permissions`
  * a set of notification event keys recognised by `app.services.push_service`
  * a default-permissions table used when the capability ships in a template

Capabilities are *registered* (declared) here and *enabled* per-department
via `departments.capabilities` (a JSONB array of capability keys). The
project-detail page surfaces a capability's UI tab iff the project's
department has the capability key listed.

See `app/capabilities/registry.py` for the registry entries.
"""
