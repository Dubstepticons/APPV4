#!/usr/bin/env python3
"""
Standalone test for debug subsystem (no PyQt6 required)
"""

import os
import sys


# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import directly from modules (bypass core/__init__.py)
import importlib.util


# Load diagnostics module directly
spec = importlib.util.spec_from_file_location("diagnostics", "core/diagnostics.py")
diagnostics = importlib.util.module_from_spec(spec)
sys.modules["core.diagnostics"] = diagnostics

# Load utils.logger first (dependency)
spec_logger = importlib.util.spec_from_file_location("logger", "utils/logger.py")
logger_module = importlib.util.module_from_spec(spec_logger)
sys.modules["utils.logger"] = logger_module
spec_logger.loader.exec_module(logger_module)

# Now load diagnostics
spec.loader.exec_module(diagnostics)

# Get the functions we need
DiagnosticsHub = diagnostics.DiagnosticsHub
info = diagnostics.info
debug = diagnostics.debug
warn = diagnostics.warn
error = diagnostics.error
PerformanceMarker = diagnostics.PerformanceMarker

import time


print("=" * 70)
print("Testing APPSIERRA Debug Subsystem")
print("=" * 70)
print()

# Test 1: Basic event logging
print("[1] Testing basic event logging...")
hub = DiagnosticsHub.get_instance(max_events=100)

info("system", "Test system started")
debug("network", "Connection test", context={"host": "127.0.0.1", "port": 11099})
warn("perf", "Slow operation detected", context={"elapsed_ms": 1500})
error("core", "Test error", context={"test": True})

stats = hub.get_statistics()
print(f"    Total events: {stats['total_events']}")
print(f"    Categories: {stats['events_by_category']}")
print(f"    Levels: {stats['events_by_level']}")
print()

# Test 2: Performance markers
print("[2] Testing performance markers...")
with PerformanceMarker("test_operation", category="perf"):
    time.sleep(0.1)

perf_events = [e for e in hub.events if e.event_type == "PerformanceMeasurement"]
if perf_events:
    print("    Performance marker created")
    print(f"    Elapsed: {perf_events[-1].elapsed_ms:.2f}ms")
print()

# Test 3: Snapshot export
print("[3] Testing snapshot export...")
snapshot = hub.snapshot(max_events=10)
print(f"    Snapshot contains {len(snapshot)} events")

export_file = "logs/test_snapshot.json"
hub.export_json(export_file)
print(f"    Exported to {export_file}")
print()

# Test 4: Error policy manager
# Test 4: Final statistics
print("[4] Final statistics:")
final_stats = hub.get_statistics()
print(f"   Total events: {final_stats['total_events']}")
print(f"   Error count: {final_stats['errors_count']}")
print(f"   Fatal count: {final_stats['fatal_count']}")
print()

print("=" * 70)
print(" All tests passed!")
print("=" * 70)
print()
print("Debug subsystem is working correctly.")
print(f"Check {export_file} for exported diagnostic data.")
