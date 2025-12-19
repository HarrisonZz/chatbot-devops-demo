class EksAddons(pulumi.ComponentResource):
    def __init__(self, name: str, cluster: EksCluster, opts: Optional[pulumi.ResourceOptions] = None):
        super().__init__("pkg:compute:EksAddons", name, None, opts)
        self.cluster = cluster
        # 繼承叢集的 k8s provider，確保 Helm 裝在正確的地方
        self.provider_opts = ResourceOptions(parent=self, provider=cluster.k8s_provider)

    def install_alb_controller(self, version="1.7.1"):
        # 1. 準備 Policy (可以從獨立的 JSON 檔案讀取)
        alb_policy_json = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iam:CreateServiceLinkedRole",
                        "ec2:DescribeAccountAttributes",
                        "ec2:DescribeAddresses",
                        "ec2:DescribeAvailabilityZones",
                        "ec2:DescribeInternetGateways",
                        "ec2:DescribeVpcs",
                        "ec2:DescribeSubnets",
                        "ec2:DescribeSecurityGroups",
                        "ec2:DescribeInstances",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DescribeTags",
                        "ec2:GetCoipPoolUsage",
                        "ec2:DescribeCoipPools",
                        "elasticloadbalancing:*",
                        "acm:DescribeCertificate",
                        "acm:ListCertificates",
                        "acm:GetCertificate",
                        "iam:GetServerCertificate",
                        "iam:ListServerCertificates",
                        "cognito-idp:DescribeUserPoolClient",
                        "waf-regional:GetWebACLForResource",
                        "waf-regional:GetWebACL",
                        "waf-regional:AssociateWebACL",
                        "waf-regional:DisassociateWebACL",
                        "wafv2:GetWebACL",
                        "wafv2:GetWebACLForResource",
                        "wafv2:AssociateWebACL",
                        "wafv2:DisassociateWebACL",
                        "shield:DescribeProtection",
                        "shield:GetSubscriptionState",
                        "shield:DeleteProtection",
                        "shield:CreateProtection",
                        "shield:DescribeSubscription"
                    ],
                    "Resource": "*"
                }
            ]
        })

        # 2. 使用叢集內建的 create_irsa_role
        role_arn = self.cluster.create_irsa_role(
            "alb-role", "kube-system", "aws-load-balancer-controller", json.dumps(alb_policy_json)
        )

        # 3. Helm Chart
        return k8s.helm.v3.Chart("alb-controller", k8s.helm.v3.ChartOpts(
            chart="aws-load-balancer-controller",
            version=version,
            namespace="kube-system",
            fetch_opts=k8s.helm.v3.FetchOpts(repo="https://aws.github.io/eks-charts"),
            values={
                "clusterName": self.cluster.cluster_name,
                "serviceAccount": {"create": True, "name": "aws-load-balancer-controller", "annotations": {"eks.amazonaws.com/role-arn": role_arn}},
                "region": aws.get_region().name,
            }
        ), self.provider_opts)

    def install_external_secrets(self, version="0.9.11"):
        # 調用你原本寫好的 enable_external_secrets 邏輯
        role_arn = self.cluster.enable_external_secrets()
        
        return k8s.helm.v3.Chart("external-secrets", k8s.helm.v3.ChartOpts(
            chart="external-secrets",
            version=version,
            namespace="external-secrets",
            fetch_opts=k8s.helm.v3.FetchOpts(repo="https://charts.external-secrets.io"),
            values={
                "installCRDs": True,
                "serviceAccount": {"annotations": {"eks.amazonaws.com/role-arn": role_arn}}
            }
        ), self.provider_opts)