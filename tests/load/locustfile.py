from locust import HttpUser, between, task


class HealthUser(HttpUser):
    wait_time = between(0.2, 1.0)  # type: ignore[no-untyped-call]

    @task
    def live(self) -> None:
        self.client.get("/health/live")
