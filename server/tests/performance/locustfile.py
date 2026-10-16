import os

from locust import HttpUser, between, task


class BreakscaleUser(HttpUser):
    wait_time=between(1,3)
    @task
    def health(self):
        self.client.get("/api/v1/health")

class AuthenticatedSimulationUser(HttpUser):
    abstract = not bool(os.getenv("LOCUST_EMAIL"))
    wait_time=between(1,3)
    def on_start(self):
        response=self.client.post("/api/v1/auth/login",json={"email":os.environ["LOCUST_EMAIL"],"password":os.environ["LOCUST_PASSWORD"]},headers={"Origin":os.getenv("FRONTEND_URL","http://localhost:3000")})
        self.headers={"Authorization":"Bearer "+response.json()["access_token"]}
    @task
    def history(self):
        self.client.get("/api/v1/simulations",params={"workspace_id":os.environ["LOCUST_WORKSPACE_ID"]},headers=self.headers)
