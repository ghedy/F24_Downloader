"""Resolve bundled tools independently of a developer's environment."""
import os
import sys


def configure_runtime():
    if getattr(sys, "frozen", False):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
        os.environ.pop("PLAYWRIGHT_NODEJS_PATH", None)
