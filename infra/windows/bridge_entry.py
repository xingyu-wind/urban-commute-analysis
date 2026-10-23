"""Packaging-only UTF-8 pipe adapter for the unchanged isolated S8 bridge.

Java writes UTF-8 JSON. CPython -I ignores PYTHONUTF8/PYTHONIOENCODING, so
Windows locale decoding must be selected explicitly for non-ASCII paths.
"""
from pathlib import Path
import runpy
import sys

sys.stdin.reconfigure(encoding='utf-8',errors='strict')
runpy.run_path(str(Path(__file__).with_name('s8_adapter_bridge.py')),run_name='__main__')
