import pulumi
from pulumi import Output
import pulumi_cloudflare as cloudflare
from components.compute import EksCluster, EksArgs, EksAddons, CloudflareValidatedCert

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

            k8s_version=cfg.get("version") or "1.32",
            endpoint_public_access=cfg.get_bool("endpointPublic") if cfg.get_bool("endpointPublic") is not None else (not is_prod),
            endpoint_private_access=True,

            # NodeGroup（先給一個通用預設）
            instance_types=cfg.get_object("instanceTypes") or ["t3.large"],
            desired_size=cfg.get_int("desired") or 2,
            min_size=cfg.get_int("min") or 1,
            max_size=cfg.get_int("max") or 3,
        ),
    )

    # addons = EksAddons("eks-addons", cluster=eks)
    
    # # 執行安裝並獲取 ARN 用於 export
    # alb_role_arn = addons.install_alb_controller()
    # eso_role_arn = addons.install_external_secrets(ssm_path_prefix=f"/ai-chatbot/{env}/*")
    # bedrock_role_arn = addons.install_bedrock_role()

    # cf_cfg = pulumi.Config("cloudflare")

    # cf_zone_id = cf_cfg.require("cloudflareZoneID")
    # cf_domain = cf_cfg.require("domainName")
    # cf_token = cf_cfg.require_secret("apiToken")
    # cf_provider = cloudflare.Provider("cf-provider",
    #     api_token=cf_token
    # )

    # cert = CloudflareValidatedCert(
    #     f"api-{env}",
    #     domain_name=cf_domain,
    #     zone_id=cf_zone_id,
    #     opts=pulumi.ResourceOptions(provider=cf_provider)
    # )

    # addons.install_external_dns(
    #     api_token=cf_token,
    #     domain_filter=cf_domain
    # )

    # 3. Exports（addons stack 依賴 clusterName, vpcId, oidc*）
    pulumi.export("env", env)
    pulumi.export("clusterName", eks.cluster_name)
    pulumi.export("vpcId", vpc_id)
    pulumi.export("clusterArn", eks.cluster_arn)
    pulumi.export("nodeGroupName", eks.nodegroup_name)
    
    # 用於 IAM OIDC Trust (如果別的 Stack 需要)
    pulumi.export("oidcProviderArn", eks.oidc_provider_arn)
    pulumi.export("oidcProviderUrl",eks.oidc_provider_url) 
    pulumi.export("kubeconfig", eks.kubeconfig)
    
    # ✅ 導出 IAM Role ARN，給 Ansible 用
    # pulumi.export("eso_role_arn", eso_role_arn)
    # pulumi.export("alb_role_arn", alb_role_arn)
    # pulumi.export("chatbot_bedrock_role_arn", bedrock_role_arn)

    # pulumi.export("certificate_arn", cert.arn)