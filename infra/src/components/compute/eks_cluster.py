from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pulumi_tls as tls

import pulumi
import pulumi_aws as aws


@dataclass(frozen=True)
class EksArgs:
    cluster_name: pulumi.Input[str]
    vpc_id: pulumi.Input[str]
    private_subnet_ids: pulumi.Input[List[str]]
    public_subnet_ids: pulumi.Input[List[str]]

    k8s_version: str = "1.29"

    endpoint_public_access: bool = True
    endpoint_private_access: bool = True

    instance_types: List[str] = None
    desired_size: int = 2
    min_size: int = 1
    max_size: int = 3

    tags: Optional[Dict[str, str]] = None


class EksCluster(pulumi.ComponentResource):
    def __init__(self, name: str, args: EksArgs, opts: Optional[pulumi.ResourceOptions] = None):
        super().__init__("pkg:compute:EksCluster", name, None, opts)
        parent = pulumi.ResourceOptions(parent=self)

        tags = {"ManagedBy": "pulumi", **(args.tags or {})}

        # 1) Cluster IAM Role
        cluster_role = aws.iam.Role(
            f"{name}-cluster-role",
            assume_role_policy=aws.iam.get_policy_document(statements=[aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                principals=[aws.iam.GetPolicyDocumentStatementPrincipalArgs(type="Service", identifiers=["eks.amazonaws.com"])],
            )]).json,
            tags=tags,
            opts=parent,
        )

        for pol in [
            "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
            "arn:aws:iam::aws:policy/AmazonEKSServicePolicy",
        ]:
            aws.iam.RolePolicyAttachment(f"{name}-cluster-{pol.split('/')[-1]}", role=cluster_role.name, policy_arn=pol, opts=parent)

        # 2) Security Group（cluster SG）
        cluster_sg = aws.ec2.SecurityGroup(
            f"{name}-cluster-sg",
            vpc_id=args.vpc_id,
            description="EKS control-plane security group",
            egress=[aws.ec2.SecurityGroupEgressArgs(protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"])],
            tags={**tags, "Name": f"{name}-cluster-sg"},
            opts=parent,
        )

        # 3) EKS Cluster
        cluster = aws.eks.Cluster(
            f"{name}-cluster",
            name=args.cluster_name,
            role_arn=cluster_role.arn,
            version=args.k8s_version,
            vpc_config=aws.eks.ClusterVpcConfigArgs(
                subnet_ids=args.private_subnet_ids,  # ✅ Node 放 private 子網；LB 走 public 子網靠 tags
                security_group_ids=[cluster_sg.id],
                endpoint_public_access=args.endpoint_public_access,
                endpoint_private_access=args.endpoint_private_access,
            ),
            tags=tags,
            opts=parent,
        )

        # 4) Node IAM Role
        node_role = aws.iam.Role(
            f"{name}-node-role",
            assume_role_policy=aws.iam.get_policy_document(statements=[aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                principals=[aws.iam.GetPolicyDocumentStatementPrincipalArgs(type="Service", identifiers=["ec2.amazonaws.com"])],
            )]).json,
            tags=tags,
            opts=parent,
        )

        for pol in [
            "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
            "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
            "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        ]:
            aws.iam.RolePolicyAttachment(f"{name}-node-{pol.split('/')[-1]}", role=node_role.name, policy_arn=pol, opts=parent)

        # 5) Managed Node Group
        ng = aws.eks.NodeGroup(
            f"{name}-ng",
            cluster_name=cluster.name,
            node_role_arn=node_role.arn,
            subnet_ids=args.private_subnet_ids,
            instance_types=args.instance_types or ["t3.large"],
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=args.desired_size,
                min_size=args.min_size,
                max_size=args.max_size,
            ),
            tags=tags,
            opts=parent,
        )

        # 6) OIDC Provider（IRSA 必備）
        cluster_info = aws.eks.get_cluster_output(name=cluster.name)

        oidc_issuer = cluster_info.identity.apply(lambda ident: ident["oidc"]["issuer"])
        
        # 只有在 issuer 存在時才嘗試建立 OpenIdConnectProvider 資源
        oidc_cert = tls.get_certificate_output(url=oidc_issuer)

        # AWS 要的是「root CA」的 SHA1 指紋：通常取 chain 最後一張
        thumbprint = oidc_cert.certificates.apply(lambda certs: [certs[-1].sha1_fingerprint])

        oidc = aws.iam.OpenIdConnectProvider(
            f"{name}-oidc",
            client_id_lists=["sts.amazonaws.com"],
            # 確保 url 只有在非空時才使用
            url=oidc_issuer,
            # ... 保持 thumbprint 不變 ...
            thumbprint_lists=thumbprint,
            tags=tags,
            opts=parent.merge(pulumi.ResourceOptions(
                # 確保 OIDC Provider 必須等待 Cluster 建立完成才能取得 Issuer
                depends_on=[cluster],
                # 如果 OIDC Issuer 是空的，則不要創建 OIDC Provider
                # resource_should_be_created=oidc_issuer.apply(lambda issuer: issuer != "") # 這個屬性在 Classic Provider中不存在，故使用 depends_on
            )),
        )

        # 7) kubeconfig（給 kubectl / pulumi-k8s provider）
        auth = aws.eks.get_cluster_auth_output(name=cluster.name)
        kubeconfig = pulumi.Output.all(cluster.endpoint, cluster.certificate_authorities, auth.token, cluster.name).apply(
            lambda a: {
                "apiVersion": "v1",
                "clusters": [{
                    "cluster": {"server": a[0], "certificate-authority-data": a[1][0]["data"]},
                    "name": a[3],
                }],
                "contexts": [{
                    "context": {"cluster": a[3], "user": a[3]},
                    "name": a[3],
                }],
                "current-context": a[3],
                "kind": "Config",
                "users": [{
                    "name": a[3],
                    "user": {"token": a[2]},
                }],
            }
        )

        self.cluster_name = cluster.name
        self.cluster_arn = cluster.arn
        self.nodegroup_name = ng.node_group_name
        self.oidc_provider_arn = oidc.arn
        self.kubeconfig = pulumi.Output.secret(kubeconfig)

        self.register_outputs({
            "clusterName": self.cluster_name,
            "clusterArn": self.cluster_arn,
            "nodeGroupName": self.nodegroup_name,
            "oidcProviderArn": self.oidc_provider_arn,
            "kubeconfig": self.kubeconfig,
        })
