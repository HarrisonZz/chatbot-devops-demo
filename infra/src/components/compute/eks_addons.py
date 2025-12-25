import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
import json
from typing import Optional, List
from pathlib import Path
from pulumi import ResourceOptions, Output, Input

class EksAddons(pulumi.ComponentResource):
    def __init__(self, 
                 name: str, 
                 cluster_name: Input[str],
                 vpc_id: Input[str],
                 oidc_provider_arn: Input[str],
                 oidc_provider_url: Input[str],
                 k8s_provider: k8s.Provider,
                 opts: Optional[ResourceOptions] = None):
        """
        EKS Addons (Platform Layer)
        完全解耦的版本，不依賴 Infrastructure Stack 的物件實體，只依賴 Outputs。
        
        :param cluster_name: EKS 叢集名稱 (字串)
        :param vpc_id: VPC ID (字串)
        :param oidc_provider_arn: IAM OIDC Provider ARN
        :param oidc_provider_url: IAM OIDC Provider URL (https://...)
        :param k8s_provider: 專用的 Kubernetes Provider (必須使用 StackReference 拿到的 kubeconfig 建立)
        """
        super().__init__("pkg:compute:EksAddons", name, None, opts)
        
        self.cluster_name = cluster_name
        self.vpc_id = vpc_id
        self.oidc_provider_arn = oidc_provider_arn
        self.oidc_provider_url = oidc_provider_url
        
        # 設定所有 K8s 資源的預設 Provider (確保使用傳入的動態 Provider)
        self.k8s_opts = ResourceOptions(parent=self, provider=k8s_provider)

    def _create_irsa_role(self, role_name_part: str, namespace: str, sa_name: str, policy_json: str):
        """
        [內部方法] 建立 IRSA (IAM Role for Service Accounts)
        這是從原本 EksCluster 搬過來的邏輯，讓 Addons Stack 能獨立運作。
        """
        # 處理 OIDC URL，移除 'https://' 前綴以符合 AWS Trust Policy 格式
        oidc_domain = Output.from_input(self.oidc_provider_url).apply(
            lambda url: url.replace("https://", "")
        )

        assume_role_policy = Output.all(oidc_domain, self.oidc_provider_arn).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Federated": args[1]},
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            f"{args[0]}:sub": f"system:serviceaccount:{namespace}:{sa_name}",
                            f"{args[0]}:aud": "sts.amazonaws.com"
                        }
                    }
                }]
            })
        )

        role = aws.iam.Role(f"{self._name}-{role_name_part}-role",
            assume_role_policy=assume_role_policy,
            tags={"ManagedBy": "Pulumi", "Component": "EksAddons"},
            opts=ResourceOptions(parent=self)
        )

        policy = aws.iam.Policy(f"{self._name}-{role_name_part}-policy",
            policy=policy_json,
            opts=ResourceOptions(parent=self)
        )

        aws.iam.RolePolicyAttachment(f"{self._name}-{role_name_part}-attach",
            role=role.name,
            policy_arn=policy.arn,
            opts=ResourceOptions(parent=self)
        )

        return role.arn

    def install_alb_controller(self, version="1.7.1"):
        """
        安裝 AWS Load Balancer Controller
        """
        # 1. 讀取 Policy 文件 (確保路徑正確，建議放在專案根目錄的 policies 資料夾)
        # 這裡假設檔案結構為: project_root/pkg/compute/eks_addons.py，所以往上兩層找到 policies
        policy_path = Path(__file__).resolve().parents[2] / "policies" / "alb_controller_iam_policy.json"
        
        try:
            alb_policy_json = policy_path.read_text(encoding="utf-8")
        except FileNotFoundError:
             # 如果找不到檔案，拋出更有意義的錯誤提示
            raise FileNotFoundError(f"Cannot find ALB Policy at {policy_path}. Please ensure the file exists.")

        # 2. 建立 IRSA Role
        role_arn = self._create_irsa_role("alb", "kube-system", "aws-load-balancer-controller", alb_policy_json)

        # 3. 建立 K8s Service Account
        alb_sa = k8s.core.v1.ServiceAccount("aws-load-balancer-controller-sa",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="aws-load-balancer-controller",
                namespace="kube-system",
                annotations={"eks.amazonaws.com/role-arn": role_arn},
            ),
            opts=self.k8s_opts,
        )

        # 4. 安裝 Helm Chart
        self.alb_release = k8s.helm.v3.Release("alb-controller",
            k8s.helm.v3.ReleaseArgs(
                name="alb-controller",
                chart="aws-load-balancer-controller",
                version=version,
                namespace="kube-system",
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://aws.github.io/eks-charts",
                ),
                values={
                    "clusterName": self.cluster_name,
                    "region": aws.get_region().name,
                    "vpcId": self.vpc_id,
                    "serviceAccount": {
                        "create": False, # 我們上面手動建立了，所以這裡 False
                        "name": "aws-load-balancer-controller",
                    },
                },
                skip_await=False,
                atomic=True,
                cleanup_on_fail=True,
                timeout=900,
            ),
            # 確保 SA 建立後才安裝 Helm
            opts=self.k8s_opts.merge(ResourceOptions(depends_on=[alb_sa])),
        )
        return role_arn
    
    def install_observability_role(self, service_account: str, namespace: str):
        """
        建立給 ADOT Collector 或 App Pod 使用的觀測性角色 (CloudWatch + X-Ray)
        """
        obs_ns = k8s.core.v1.Namespace("observability-ns",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=namespace,
            ),
            opts=self.k8s_opts # 假設這是在 EksAddons 類別內
        )

        obs_policy_json = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                        "cloudwatch:PutMetricData",
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                        "xray:GetSamplingStatisticSummaries"
                    ],
                    "Resource": "*"
                }
            ]
        })

        cert_manager_release = self.install_cert_manager()

        obs_role_arn = self._create_irsa_role(
            role_name_part="adot-obs",
            namespace=namespace,
            sa_name=service_account,
            policy_json=obs_policy_json
        )

        adot_addon = aws.eks.Addon("eks-adot-addon",
            cluster_name=self.cluster_name,
            addon_name="adot",
            service_account_role_arn=obs_role_arn,
            resolve_conflicts_on_update="OVERWRITE",
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[
                    cert_manager_release, 
                    self.alb_release
                ] # 💡 確保 Cert-manager 的 Webhook 已就緒
            )
        )

        k8s.core.v1.ServiceAccount(
            "adot-collector-sa",
            metadata={
                "name": service_account,
                "namespace": namespace,
                "annotations": {
                    "eks.amazonaws.com/role-arn": obs_role_arn # 💡 自動追蹤變化
                }
            },
            opts=self.k8s_opts.merge(pulumi.ResourceOptions(depends_on=[obs_ns, adot_addon])) # 確保 Addon 裝好才建 SA
        )

        return obs_role_arn

    def install_external_secrets(self, version="0.9.11", ssm_path_prefix="/ai-chatbot/*"):
        """
        安裝 External Secrets Operator (ESO)
        """
        # 1. 定義允許存取 SSM Parameter Store 的 Policy
        policy_doc = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
                "Resource": f"arn:aws:ssm:*:*:parameter{ssm_path_prefix}"
            }]
        })

        # 2. 建立 IRSA Role
        role_arn = self._create_irsa_role("eso", "external-secrets", "external-secrets-sa", policy_doc)

        # 3. 建立 Namespace (ESO 官方建議獨立 Namespace)
        ns = k8s.core.v1.Namespace("external-secrets-ns",
            metadata={"name": "external-secrets"},
            opts=self.k8s_opts
        )

        # 4. 安裝 Helm Chart
        self.eso_chart = k8s.helm.v3.Release("external-secrets",
            k8s.helm.v3.ReleaseArgs(
                name="external-secrets",
                chart="external-secrets",
                version=version,
                namespace=ns.metadata.name,
                
                # Release 使用 repository_opts 而不是 fetch_opts
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://charts.external-secrets.io"
                ),
                
                values={
                    "installCRDs": True,
                    "serviceAccount": {
                        "create": True,
                        "name": "external-secrets-sa",
                        "annotations": {"eks.amazonaws.com/role-arn": role_arn}
                    },
                    "webhook": {
                        "timeoutSeconds": 30 # 增加這行防禦性設定
                    }
                },
                
                # 🔥 關鍵優勢：開啟原子性與失敗清理
                atomic=True,
                cleanup_on_fail=True,
                timeout=900, # 給它多一點時間
            ),
            # 🔥 記得加上對 ALB Release 的依賴
            opts=self.k8s_opts.merge(ResourceOptions(
                depends_on=[ns, self.alb_release] if hasattr(self, 'alb_release') else [ns]
            ))
        )

        return role_arn
    
    def install_cert_manager(self):
        """
        使用 Helm Release 安裝 Cert-manager (ADOT 的強制前置組件)
        """
        # 建立 Namespace
        ns = k8s.core.v1.Namespace(
            "cert-manager-ns",
            metadata={"name": "cert-manager"},
            opts=self.k8s_opts
        )

        # 透過 Helm Release 安裝
        cert_manager = k8s.helm.v3.Release(
            "cert-manager",
            k8s.helm.v3.ReleaseArgs(
                name="cert-manager",
                chart="cert-manager",
                version="v1.13.0",
                namespace=ns.metadata["name"],
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://charts.jetstack.io",
                ),
                # 重要：必須安裝 CRD，否則 ADOT 無法運作
                values={
                    "installCRDs": True,
                },
                # 確保 Helm 等待所有資源 Ready
                wait_for_jobs=True,
            ),
            opts=pulumi.ResourceOptions(parent=ns, depends_on=[ns])
        )
        return cert_manager

    def install_external_dns(self, api_token: Input[str], domain_filter: str, version="1.14.3"):
        """
        安裝 External DNS (整合 Cloudflare)
        """
        # 1. 建立 Secret 存放 Cloudflare Token
        cf_token_secret = k8s.core.v1.Secret("cloudflare-api-token",
            metadata={
                "name": "cloudflare-api-token",
                "namespace": "kube-system"
            },
            string_data={
                "api-token": api_token
            },
            opts=self.k8s_opts
        )

        # 2. 安裝 Helm Chart
        self.external_dns_chart = k8s.helm.v3.Release("external-dns", 
            k8s.helm.v3.ReleaseArgs(
                name="external-dns",
                chart="external-dns",
                version=version,
                namespace="kube-system",
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://kubernetes-sigs.github.io/external-dns/"
                ),
                values={
                    "provider": "cloudflare",
                    # ... (原本的 values 保持不變) ...
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
                        "--cloudflare-proxied",
                        "--source=ingress",
                        f"--domain-filter={domain_filter}"
                    ],
                    "policy": "sync",
                    "serviceAccount": {
                        "create": True,
                        "name": "external-dns"
                    }
                },
                atomic=True,
                cleanup_on_fail=True,
            ), 
            opts=self.k8s_opts.merge(ResourceOptions(depends_on=[cf_token_secret]))
        )

    def install_bedrock_role(self, service_account: str = "ai-chatbot-sa", namespace: str = "default"):
        """
        安裝 Bedrock IAM Role 並使用 EKS Pod Identity 綁定
        """
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
                    "Resource": "*"
                }
            ]
        })

        # 注意：Pod Identity 的 Principal 是 pods.eks.amazonaws.com，與 IRSA 不同
        bedrock_role = aws.iam.Role(f"{self._name}-bedrock-role",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "pods.eks.amazonaws.com"
                    },
                    "Action": [
                        "sts:AssumeRole",
                        "sts:TagSession"
                    ]
                }]
            }),
            opts=ResourceOptions(parent=self)
        )

        bedrock_policy = aws.iam.Policy(f"{self._name}-bedrock-policy",
            policy=bedrock_policy_json,
            opts=ResourceOptions(parent=self)
        )

        aws.iam.RolePolicyAttachment(f"{self._name}-bedrock-policy-attach",
            role=bedrock_role.name,
            policy_arn=bedrock_policy.arn,
            opts=ResourceOptions(parent=self)
        )

        # 建立 Pod Identity Association
        # 這裡需要 cluster_name，我們直接從 self.cluster_name 拿
        pod_identity_assoc = aws.eks.PodIdentityAssociation(f"{self._name}-bedrock-assoc",
            cluster_name=self.cluster_name,
            namespace=namespace,
            service_account=service_account,
            role_arn=bedrock_role.arn,
            opts=ResourceOptions(parent=self)
        )

        return bedrock_role.arn