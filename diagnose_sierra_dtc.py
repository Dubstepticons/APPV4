#!/usr/bin/env python3
"""Diagnose Sierra Chart DTC server configuration.

Tests both Binary and JSON encoding capabilities using plain ASCII output.
"""

import contextlib
import json
import socket
import struct
import sys
import time
from typing import Tuple


HOST = "127.0.0.1"
PORT = 11099


def test_json_encoding() -> bool:
    """Test if Sierra accepts JSON encoding negotiation."""
    print("\n" + "=" * 80)
    print("TEST 1: JSON ENCODING NEGOTIATION")
    print("=" * 80)

    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((HOST, PORT))
        print(f"[OK] Connected to {HOST}:{PORT}")

        encoding_req = {
            "Type": 5,
            "ProtocolVersion": 8,
            "Encoding": 2,
            "ProtocolType": "DTC",
        }
        msg = json.dumps(encoding_req).encode("utf-8") + b"\x00"
        sock.send(msg)
        print(f"[SEND] ENCODING_REQUEST: {encoding_req}")

        buffer = b""
        start = time.time()

        while time.time() - start < 3:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    print("[CLOSE] Server closed connection (rejected)")
                    return False
                buffer += chunk

                while b"\x00" in buffer:
                    idx = buffer.index(b"\x00")
                    frame = buffer[:idx]
                    buffer = buffer[idx + 1 :]

                    if not frame:
                        continue

                    try:
                        msg_obj = json.loads(frame)
                        msg_type = msg_obj.get("Type")

                        if msg_type == 6:  # ENCODING_RESPONSE
                            print(f"[OK] ENCODING_RESPONSE received: {msg_obj}")
                            return True
                        if msg_type == 5:  # LOGOFF
                            print(
                                f"[CLOSE] Server sent LOGOFF: "
                                f\"{msg_obj.get('Reason', 'Unknown')}\"
                            )
                            print("\n[DIAGNOSIS] Sierra Chart is rejecting JSON encoding.")
                            print("   Possible causes:")
                            print("   1. DTC server is in Binary-only mode")
                            print("   2. JSON support not enabled in Sierra settings")
                            return False

                        print(f"  Received Type {msg_type}: {msg_obj}")
                    except json.JSONDecodeError:
                        print("Invalid JSON (server might be in Binary mode)")
                        print(f"   Raw: {frame[:80]}")
                        return False
            except socket.timeout:
                break

        print("Timeout waiting for ENCODING_RESPONSE")
        return False

    except Exception as exc:
        print(f"[ERROR] {exc}")
        return False
    finally:
        if sock is not None:
            with contextlib.suppress(Exception):
                sock.close()


def test_binary_encoding() -> bool:
    """Test if Sierra accepts Binary DTC protocol."""
    print("\n" + "=" * 80)
    print("TEST 2: BINARY DTC PROTOCOL")
    print("=" * 80)

    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((HOST, PORT))
        print(f"[OK] Connected to {HOST}:{PORT}")

        msg_type = 1  # LOGON_REQUEST
        size = 4  # size + type
        data = struct.pack("<HH", size, msg_type)

        sock.send(data)
        print(f"[SEND] Binary LOGON_REQUEST header (Type={msg_type})")

        buffer = b""
        start = time.time()

        while time.time() - start < 3:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    print("Server closed connection")
                    return False
                buffer += chunk

                if len(buffer) >= 4:
                    size_val, msg_type_val = struct.unpack("<HH", buffer[:4])
                    print(
                        f"[RECV] Binary message: Size={size_val}, "
                        f"Type={msg_type_val}"
                    )

                    if msg_type_val == 2:
                        print("[OK] Server accepts BINARY protocol.")
                        return True
                    if 1 <= msg_type_val <= 900:
                        print(
                            f"[OK] Server is in BINARY mode "
                            f"(Type {msg_type_val})"
                        )
                        return True

            except socket.timeout:
                break
            except Exception as exc:
                print(f"Parse error: {exc}")
                break

        print("No valid binary response")
        return False

    except Exception as exc:
        print(f"[ERROR] {exc}")
        return False
    finally:
        if sock is not None:
            with contextlib.suppress(Exception):
                sock.close()


def test_no_encoding_negotiation() -> bool:
    """Test direct LOGON without ENCODING_REQUEST."""
    print("\n" + "=" * 80)
    print("TEST 3: DIRECT JSON LOGON (No Encoding Negotiation)")
    print("=" * 80)

    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((HOST, PORT))
        print(f"[OK] Connected to {HOST}:{PORT}")

        logon_req = {
            "Type": 1,
            "ProtocolVersion": 8,
            "ClientName": "APPSIERRA_TEST",
            "HeartbeatIntervalInSeconds": 5,
            "Username": "",
            "Password": "",
            "TradeMode": 1,
        }
        msg = json.dumps(logon_req).encode("utf-8") + b"\x00"
        sock.send(msg)
        print(f"[SEND] LOGON_REQUEST: {logon_req}")

        buffer = b""
        start = time.time()

        while time.time() - start < 3:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    print("Server closed connection (rejected)")
                    return False
                buffer += chunk

                while b"\x00" in buffer:
                    idx = buffer.index(b"\x00")
                    frame = buffer[:idx]
                    buffer = buffer[idx + 1 :]

                    if not frame:
                        continue

                    try:
                        msg_obj = json.loads(frame)
                        msg_type = msg_obj.get("Type")

                        if msg_type == 2:
                            print(f"[OK] LOGON_RESPONSE received: {msg_obj}")
                            print(
                                "[OK] Server accepts direct JSON LOGON "
                                "(no encoding negotiation required)."
                            )
                            return True

                        print(f"  Received Type {msg_type}: {msg_obj}")
                    except json.JSONDecodeError:
                        print("Invalid JSON response")
                        return False
            except socket.timeout:
                break

        print("Timeout waiting for LOGON_RESPONSE")
        return False

    except Exception as exc:
        print(f"[ERROR] {exc}")
        return False
    finally:
        if sock is not None:
            with contextlib.suppress(Exception):
                sock.close()


def summarize(json_ok: bool, binary_ok: bool, direct_ok: bool) -> None:
    """Print a summary of capability results."""
    print("\n" + "=" * 80)
    print("DIAGNOSIS SUMMARY")
    print("=" * 80)
    print(
        "JSON Encoding Negotiation:  "
        f\"{'SUPPORTED' if json_ok else 'NOT SUPPORTED'}\"
    )
    print(
        "Binary DTC Protocol:        "
        f\"{'SUPPORTED' if binary_ok else 'NOT SUPPORTED'}\"
    )
    print(
        "Direct JSON Logon:          "
        f\"{'SUPPORTED' if direct_ok else 'NOT SUPPORTED'}\"
    )

    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if json_ok:
        print("Sierra Chart supports JSON encoding.")
    elif binary_ok:
        print(
            "Sierra Chart accepts JSON but skips encoding negotiation, "
            "or is Binary-only."
        )
    else:
        print("Cannot establish DTC connection; check Sierra configuration.")


def main() -> None:
    print("=" * 80)
    print("SIERRA CHART DTC CONFIGURATION DIAGNOSIS")
    print("=" * 80)
    print(f"Target: {HOST}:{PORT}")

    json_ok = test_json_encoding()
    binary_ok = test_binary_encoding()
    direct_ok = test_no_encoding_negotiation()
    summarize(json_ok, binary_ok, direct_ok)


if __name__ == "__main__":
    main()
