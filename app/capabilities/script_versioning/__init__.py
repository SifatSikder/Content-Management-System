"""Script versioning capability — versioned markdown scripts with inline
comments + lock/unlock workflow.

The actual router still lives at `app/routes/scripts.py` for the moment;
this package re-exports it so the capability registry has a stable import
path. Moving the file into this package outright is a Phase D follow-up.
"""
