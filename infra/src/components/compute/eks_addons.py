import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
import json
from typing import Optional
from .eks_cluster import EksCluster
from pulumi import ResourceOptions
from pathlib import Path
# import requests

class EksAddons(pulumi.ComponentResource):
    def __init__(self, name: str, cluster: EksCluster, opts: Optional[pulumi.ResourceOptions] = None):
        super().__init__("pkg:compute:EksAddons", name, None, opts)
        self.cluster = cluster
        self.provider_opts = ResourceOptions(parent=self, provider=cluster.k8s_provider)

    
    def enable_external_secrets(self, namespace="external-secrets", sa_name="external-secrets-sa", ssm_path_prefix="/ai-chatbot/*"):

        policy_doc = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath"
                ],
                "Resource": f"arn:aws:ssm:*:*:parameter{ssm_path_prefix}"
            }]
        })

        return self.cluster.create_irsa_role("eso-role", namespace, sa_name, policy_doc)
    
    def install_alb_controller(self, version="1.7.1"):
        
        # print("Downloading official IAM Policy for ALB Controller...")
        # policy_url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.5.4/docs/install/iam_policy.json"
        policy_path = Path(__file__).resolve().parents[2] / "policies" / "aws_load_balancer_controller_iam_policy.json"
        alb_policy_json = policy_path.read_text(encoding="utf-8")
        
        # try:

        #     alb_policy_json = requests.get(policy_url).text
        # except Exception as e:
        #     raise Exception(f"Failed to download ALB IAM Policy: {e}")

        # -------------------------------------------------------------
        #  建立 IRSA Role (這裡沿用你的邏輯，傳入剛下載的完整 JSON)
        # -------------------------------------------------------------
        role_arn = self.cluster.create_irsa_role(
            "alb-role", 
            "kube-system", 
            "aws-load-balancer-controller", 
            alb_policy_json
        )

        # -------------------------------------------------------------
        # 安裝 Helm Chart
        # -------------------------------------------------------------
        self.alb_chart = k8s.helm.v3.Chart("alb-controller", k8s.helm.v3.ChartOpts(
            chart="aws-load-balancer-controller",
            version=version,
            namespace="kube-system",
            fetch_opts=k8s.helm.v3.FetchOpts(repo="https://aws.github.io/eks-charts"),
            values={
                "clusterName": self.cluster.cluster_name,
                "serviceAccount": {
                    "create": True, 
                    "name": "aws-load-balancer-controller", 
                    "annotations": {"eks.amazonaws.com/role-arn": role_arn}
                },
                "region": aws.get_region().name,
                "vpcId": self.cluster.vpc_id,
            }
        ), self.provider_opts)
        
        return role_arn

    def install_external_secrets(self, version="1.1.0", ssm_path_prefix: str = "/ai-chatbot/*"):
        # 建立 IAM Role (這會呼叫 eks_cluster.py 裡的邏輯)
        role_arn = self.cluster.enable_external_secrets(ssm_path_prefix=ssm_path_prefix)
        
        ns = k8s.core.v1.Namespace("external-secrets-ns",
            metadata={
                "name": "external-secrets"
            },
            opts=ResourceOptions(provider=self.cluster.k8s_provider, parent=self)
        )

        opts = self.provider_opts.merge(ResourceOptions(depends_on=[ns]))
        self.eso_chart = k8s.helm.v3.Chart("external-secrets", k8s.helm.v3.ChartOpts(
            chart="external-secrets",
            version=version,
            namespace=ns.metadata.name,
            fetch_opts=k8s.helm.v3.FetchOpts(repo="https://charts.external-secrets.io"),
            values={
                "installCRDs": True,
                "serviceAccount": {
                    "name": "external-secrets-sa",
                    "annotations": {"eks.amazonaws.com/role-arn": role_arn}
                }
            }
        ), opts=opts)
        
        return role_arn

    def install_bedrock_role(self, service_account: str = "ai-chatbot-sa"):

        bedrock_policy_json = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                        "bedrock:ListFoundationModels"
                    ],
                    "Resource": "*" # 如果想更安全，可以指定特定的 Model ARN
                }
            ]
        })

        bedrock_role = aws.iam.Role("bedrock-role",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "pods.eks.amazonaws.com" # 必須是這個
                    },
                    "Action": [
                        "sts:AssumeRole",
                        "sts:TagSession" # Pod Identity 需要這個來傳遞標籤
                    ]
                }]
            })
        )

        bedrock_policy = aws.iam.Policy("bedrock-policy",
            policy=bedrock_policy_json
        )

        aws.iam.RolePolicyAttachment("bedrock-policy-attach",
            role=bedrock_role.name,
            policy_arn=bedrock_policy.arn
        )

        pod_identity_assoc = aws.eks.PodIdentityAssociation("bedrock-assoc",
            cluster_name=self.cluster.cluster_name, # 確保這裡拿到的是 Cluster 名稱
            namespace="default",           # 建議確認之後 ArgoCD 是否真的裝在 default
            service_account=service_account,
            role_arn=bedrock_role.arn
        )

        return bedrock_role.arn