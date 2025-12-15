Bedrock Chatbot on AWS EKS (Pulumi + GitOps)

A production-minded, fully reproducible demo that deploys a Bedrock-powered chatbot API on AWS EKS, fronted by ALB Ingress and optionally CloudFront + S3 for a single entry point.
Infrastructure is managed by Pulumi, application delivery by Argo CD (GitOps), and lifecycle actions (deploy/update/destroy + smoke test) are automated via Ansible.

Highlights

Full lifecycle: one command to deploy/update/destroy (clean teardown, minimal leftovers)

Least privilege: Bedrock access via IRSA (K8s ServiceAccount ↔ IAM Role)

Observable by default: structured logs + CloudWatch (and optional ALB access logs to S3)

Rollback-friendly: GitOps + immutable image tags (commit SHA)