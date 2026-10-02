#!/usr/bin/env python3
"""Capture non-identifying runtime details needed to interpret CPU timings.

The record deliberately omits host names and user paths.  A resumable campaign
must keep one environment record; mixing jobs from different environments would
make the timing table ambiguous and is rejected.
"""
from __future__ import annotations

import json
import os
import platform
import struct
import sys
from pathlib import Path
from typing import Any

SCHEMA = "runtime-environment-1"


def _os_release() -> dict[str, str | None]:
    fields: dict[str, str] = {}
    path = Path('/etc/os-release')
    if path.is_file():
        for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if '=' not in raw or raw.lstrip().startswith('#'):
                continue
            key, value = raw.split('=', 1)
            fields[key] = value.strip().strip('"')
    return {
        'pretty_name': fields.get('PRETTY_NAME'),
        'id': fields.get('ID'),
        'version_id': fields.get('VERSION_ID'),
    }


def _cpu_model() -> str | None:
    path = Path('/proc/cpuinfo')
    if path.is_file():
        preferred = ('model name', 'hardware', 'processor')
        values: dict[str, str] = {}
        for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if ':' not in raw:
                continue
            key, value = raw.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            if value and key in preferred and key not in values:
                values[key] = value
        for key in preferred:
            if key in values:
                return values[key]
    value = platform.processor().strip()
    return value or None


def capture_environment() -> dict[str, Any]:
    try:
        affinity = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = None
    return {
        'schema': SCHEMA,
        'recording_status': 'captured_before_run',
        'cpu': {
            'model': _cpu_model(),
            'logical_cpu_count': os.cpu_count(),
            'affinity_cpu_count': affinity,
        },
        'architecture': {
            'machine': platform.machine() or None,
            'pointer_bits': struct.calcsize('P') * 8,
        },
        'operating_system': {
            'system': platform.system() or None,
            'kernel_release': platform.release() or None,
            'kernel_version': platform.version() or None,
            **_os_release(),
        },
        'python': {
            'implementation': platform.python_implementation() or None,
            'version': platform.python_version() or None,
            'full_version': ' '.join(sys.version.split()),
            'cache_tag': getattr(sys.implementation, 'cache_tag', None),
        },
        'timing_clocks': {
            'kernel_elapsed': 'time.perf_counter_ns',
            'driver_elapsed': 'time.monotonic',
            'process_cpu': 'time.process_time/resource.getrusage as documented by each runner',
        },
    }


def ensure_environment_file(path: Path) -> dict[str, Any]:
    current = capture_environment()
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if existing != current:
            raise RuntimeError(
                'output environment differs from the existing record; use a fresh output '
                'directory rather than mixing timing samples'
            )
        return existing
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return current
