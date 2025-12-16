import pulumi
from components.registry.ecr_repo import EcrRepo

def deploy(env: str):
    name = f"ai-chatbot-app-{env}"
    protect = (env == "prod")

    repo = EcrRepo(name)
    pulumi.export("ecr_repo_url", repo.repository_url)


