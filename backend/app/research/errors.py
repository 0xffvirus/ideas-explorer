"""Errors raised by the research-tools module."""

from __future__ import annotations


class ResearchError(Exception):
    """Base class for every error raised by the research tools."""


class ToolDisabled(ResearchError):
    """The tool is switched off by configuration (LeadFinder by default)."""


class ResearchUnavailable(ResearchError):
    """The tool is misconfigured or its provider is unavailable by configuration."""
