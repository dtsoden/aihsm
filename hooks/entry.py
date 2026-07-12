#!/usr/bin/env python3
"""Plugin entry point for the aihsm UserPromptSubmit hook.

When aihsm is installed as a Claude Code plugin, this runs the bundled
detector directly, without requiring the `aihsm` pip package to be on the
Python path. Detection is standard-library only, so the guard works from a
plain plugin install; the vault commands (`aihsm put/run/list`) still need
the pip package.

It puts the plugin root (which contains the `aihsm` package) on sys.path,
then hands off to the same detector the installer-based hook uses.
"""
import os
import sys

# CLAUDE_PLUGIN_ROOT is exported to the hook subprocess. Fall back to the
# directory two levels up from this file (hooks/entry.py -> plugin root).
plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
sys.path.insert(0, plugin_root)

from aihsm.detect import main

main()
