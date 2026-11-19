#!/usr/bin/env python3
"""Compatibility wrapper for `python -m harness.cli run ...`."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from harness.cli import main
if __name__=='__main__':
    sys.exit(main(['run',*sys.argv[1:]]))
