"""Diagnostics dataclasses — pure data models for issues and validation."""

from __future__ import annotations


class Issue:
    def __init__(self, issue_type: str, file: str, message: str):
        self.type = issue_type
        self.file = file
        self.message = message


class FixAction:
    def __init__(self, action: str, file: str, details: str):
        self.action = action
        self.file = file
        self.details = details


class ValidationError:
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message


class ValidationWarning:
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message