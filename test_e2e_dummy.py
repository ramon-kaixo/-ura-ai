#!/usr/bin/env python3
import time

agent_id = "test_e2e_dummy"
agent_type = "test"
agent_ip = "127.0.0.1"
agent_port = 19999


def dummy_agent():
    return {"status": "ok", "timestamp": time.time()}
