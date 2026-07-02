"""Shared errors for lead sync API."""


class LeadSyncError(Exception):
    def __init__(self, message, *, code="INVALID_REQUEST", details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
