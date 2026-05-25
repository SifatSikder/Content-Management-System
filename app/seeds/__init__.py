"""Seed data — templates, demo rows, and other idempotent fixtures.

Templates are the only thing in here read at runtime: Phase B's data migration
materialises them into `department_templates` rows so the existing
`DepartmentTemplateModel` flow can instantiate departments from them.
"""
