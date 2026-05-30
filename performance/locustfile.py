#!/usr/bin/env python3
"""
URA Performance Testing with Locust
"""

from locust import HttpUser, between, events, task
from locust.runners import MasterRunner


class URAUser(HttpUser):
    """Simulated user for URA API testing"""

    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts"""
        self.client.get("/health")

    @task(3)
    def health_check(self):
        """Health check endpoint"""
        self.client.get("/health")

    @task(2)
    def get_config(self):
        """Get configuration endpoint"""
        self.client.get("/config")

    @task(2)
    def get_metrics(self):
        """Get metrics endpoint"""
        self.client.get("/metrics")

    @task(1)
    def chat_request(self):
        """Chat request endpoint"""
        payload = {"message": "Hola, ¿cómo estás?", "model": "qwen2.5:3b-instruct"}
        headers = {"Content-Type": "application/json"}

        with self.client.post(
            "/chat", json=payload, headers=headers, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Called when Locust initializes"""
    print("URA Performance Testing initialized")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("Performance test started")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops"""
    print("Performance test stopped")

    if not isinstance(environment.runner, MasterRunner):
        print(f"Total requests: {environment.runner.stats.total.num_requests}")
        print(f"Total failures: {environment.runner.stats.total.num_failures}")
        print(f"Average response time: {environment.runner.stats.total.avg_response_time}")
        print(f"Min response time: {environment.runner.stats.total.min_response_time}")
        print(f"Max response time: {environment.runner.stats.total.max_response_time}")


if __name__ == "__main__":
    # Run Locust directly for testing
    from locust import run_single_user

    run_single_user(URAUser)
