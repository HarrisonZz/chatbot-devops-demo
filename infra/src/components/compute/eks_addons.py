import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
import json
from typing import Any, Optional, List, Dict
from pulumi import ResourceOptions
from pathlib import Path
# import requests

class EksAddons(pulumi.ComponentResource):
    def __init__(self, name: str, cluster: Any, opts: Optional[pulumi.ResourceOptions] = None):
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
        policy_path = Path(__file__).resolve().parents[2] / "policies" / "alb_controller_iam_policy.json"
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

        alb_sa = k8s.core.v1.ServiceAccount(
            "aws-load-balancer-controller-sa",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="aws-load-balancer-controller",
                namespace="kube-system",
                annotations={
                    "eks.amazonaws.com/role-arn": role_arn,
                },
            ),
            opts=self.provider_opts,
        )
        
        opts = self.provider_opts.merge(ResourceOptions(depends_on=[alb_sa]))
        # -------------------------------------------------------------
        # 安裝 Helm Chart
        # -------------------------------------------------------------
        self.alb_release = k8s.helm.v3.Release(
            "alb-controller",
            k8s.helm.v3.ReleaseArgs(
                chart="aws-load-balancer-controller",
                version=version,
                namespace="kube-system",
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://aws.github.io/eks-charts",
                ),
                values={
                    "clusterName": self.cluster.cluster_name,

                    # 你原本 create=True + annotations 沒問題
                    # 若你之後想「最穩」：可以改成 create=False，自己用 k8s.core.v1.ServiceAccount 建 SA
                    "serviceAccount": {
                        "create": False,
                        "name": "aws-load-balancer-controller",
                    },

                    "region": aws.get_region().name,
                    "vpcId": self.cluster.vpc_id,
                },
                skip_await=False,
                atomic=True,
                cleanup_on_fail=True,
            ),
            opts=opts,
        )
                
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
    def install_external_dns(self, api_token: str, domain_filter: str, version="1.18.0"):
        """
        安裝 External-DNS 並配置 Cloudflare 整合
        :param api_token: Cloudflare API Token
        :param domain_filter: 限制處理的網域 (例如 "yourdomain.com")
        """
        
        # 1. 建立 Cloudflare 存取權限的 IAM Policy
        # 雖然 External-DNS 是動 Cloudflare，但如果它要跑在 EKS IRSA 上，
        # 我們通常會給它一個空的或基本的 Role，或者直接使用 Cloudflare Token。
        # 這裡我們建立一個專屬的 Service Account 並把 Token 注入為 K8s Secret。
        
        # 建立 Cloudflare Token Secret
        cf_token_secret = k8s.core.v1.Secret("cloudflare-api-token",
            metadata={
                "name": "cloudflare-api-token",
                "namespace": "kube-system"
            },
            string_data={
                "api-token": api_token
            },
            opts=self.provider_opts
        )

        # 2. 安裝 External-DNS Helm Chart
        opts=self.provider_opts.merge(
            pulumi.ResourceOptions(depends_on=[cf_token_secret, self.alb_release])
        )
        self.external_dns_chart = k8s.helm.v3.Chart("external-dns", k8s.helm.v3.ChartOpts(
            chart="external-dns",
            version=version,
            namespace="kube-system",
            fetch_opts=k8s.helm.v3.FetchOpts(repo="https://kubernetes-sigs.github.io/external-dns/"),
            values={
                "provider": "cloudflare",
                "env": [
                    {
                        "name": "CF_API_TOKEN",
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": cf_token_secret.metadata["name"],
                                "key": "api-token"
                            }
                        }
                    }
                ],
                "extraArgs": [
                    "--cloudflare-proxied", # 開啟 Cloudflare 橘色小雲朵
                    "--source=ingress",     # 監控 Ingress 資源
                    f"--domain-filter={domain_filter}"
                ],
                "policy": "sync", # 自動建立與刪除紀錄
                "serviceAccount": {
                    "create": True,
                    "name": "external-dns"
                }
            }
        ), opts=opts)

        return self.external_dns_chart.urn

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