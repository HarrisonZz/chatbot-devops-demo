import json
import pulumi
import pulumi_aws as aws

class EcrRepo(pulumi.ComponentResource):
    def __init__(self, name: str, opts: pulumi.ResourceOptions | None = None):
        super().__init__("custom:registry:EcrRepo", name, None, opts)

        self.repo = aws.ecr.Repository(
            f"{name}-repo",
            name=name,
            image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                scan_on_push=True
            ),
            force_delete=True,
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.ecr.LifecyclePolicy(
            f"{name}-lifecycle",
            repository=self.repo.name,
            policy=json.dumps({
                "rules": [
                {
                    "rulePriority": 1,
                    "description": "Expire untagged images older than 7 days",
                    "selection": {
                        "tagStatus": "untagged",
                        "countType": "sinceImagePushed",
                        "countNumber": 7,
                        "countUnit": "days"
                    },
                    "action": {"type": "expire"}
                }]
            }),
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.repo]),
        )

        self.repository_url = self.repo.repository_url
        self.register_outputs({
            "repository_url": self.repository_url,
        })
