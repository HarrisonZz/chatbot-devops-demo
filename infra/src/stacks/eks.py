import pulumi
from pulumi import Output
from components.compute.eks_cluster import EksCluster, EksArgs

def deploy(env: str):
    cfg = pulumi.Config("eks")

    net_ref = cfg.require("netRef")
    net = pulumi.StackReference(net_ref)

    vpc_id = net.get_output("vpcId")
    private_subnet_ids = net.get_output("privateSubnetIds")
    public_subnet_ids = net.get_output("publicSubnetIds")
    cluster_name = net.get_output("clusterName")

    # ✅ dev/test/prod 預設差異：prod 偏安全（private endpoint），dev 方便（public endpoint）
    is_prod = (env == "prod")

    eks = EksCluster(
        "eks",
        EksArgs(
            cluster_name=cluster_name,
            vpc_id=vpc_id,
            private_subnet_ids=private_subnet_ids,
            public_subnet_ids=public_subnet_ids,

            k8s_version=cfg.get("version") or "1.29",
            endpoint_public_access=cfg.get_bool("endpointPublic") if cfg.get_bool("endpointPublic") is not None else (not is_prod),
            endpoint_private_access=True,

            # NodeGroup（先給一個通用預設）
            instance_types=cfg.get_object("instanceTypes") or ["t3.large"],
            desired_size=cfg.get_int("desired") or 2,
            min_size=cfg.get_int("min") or 1,
            max_size=cfg.get_int("max") or 3,
        ),
    )

    pulumi.export("env", env)
    pulumi.export("clusterName", eks.cluster_name)
    pulumi.export("clusterArn", eks.cluster_arn)
    pulumi.export("nodeGroupName", eks.nodegroup_name)
    pulumi.export("oidcProviderArn", eks.oidc_provider_arn)
    pulumi.export("kubeconfig", eks.kubeconfig)  # 可能是 secret output
