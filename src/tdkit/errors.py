"""Errors shared by the commands."""


class UsageError(Exception):
    """A usage or configuration error: `tdkit` exits with code 2 and prints the message."""
