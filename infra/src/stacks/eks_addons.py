import pulumi
import pulumi_kubernetes as k8s
import pulumi_aws as aws
import json
from pulumi import Output
import os
from pathlib import Path
import pulumi_cloudflare as cloudflare
from components.compute import EksAddons, CloudflareValidatedCert # 假設憑證類別還在原本位置

def deploy(env: str):
    """
    部署 EKS 平台層組件 (Layer 2)
    依賴：Layer 1 (Infra Stack) 的 Outputs
    """
    
    # ------------------------------------------------------------------
    # 1. 配置讀取與 Stack Reference
    # ------------------------------------------------------------------
    # 讀取專案配置
    config = pulumi.Config()
    
    # 讀取 "eks-addons" 命名空間下的配置 (根據你的 snippet)
    addons_cfg = pulumi.Config("addons")
    eks_stack_ref = addons_cfg.require("eksRef") # 例如: "HarrisonZz-org/ai-chatbot-infra/eks-dev"
    namespace = addons_cfg.require("nameSpace")
    
    # 建立 Stack Reference 指向基礎設施層
    infra_ref = pulumi.StackReference(eks_stack_ref)

    # 取得關鍵 Outputs (這些必須在 Infra Stack 有 export 出來！)
    cluster_name = infra_ref.get_output("clusterName")
    #kubeconfig = infra_ref.get_output("kubeconfig")
    kube_config_path = os.getenv("KUBECONFIG", "./kubeconfig")
    try:
        kube_config_content = Path(kube_config_path).read_text()
    except FileNotFoundError:
        raise FileNotFoundError(f"找不到 Kubeconfig 檔案: {kube_config_path}，請確認 CLI 是否已正確產生該檔案。")

    vpc_id = infra_ref.get_output("vpcId")             # ⚠️ 確保 Infra Stack 有 export 這個
    oidc_arn = infra_ref.get_output("oidcProviderArn")
    oidc_url = infra_ref.get_output("oidcProviderUrl") # ⚠️ 確保 Infra Stack 有 export 這個

    # ------------------------------------------------------------------
    # 2. 定義動態 K8s Provider
    # ------------------------------------------------------------------
    # 這是避免「刪除死循環」的關鍵：每次執行都使用最新的 kubeconfig 連線
    eks_cluster = aws.eks.get_cluster_output(name=cluster_name)
    # auth = aws.eks.get_cluster_auth_output(name=cluster_name)    
    # cluster_name_o = Output.from_input(cluster_name)

    # kubeconfig = Output.all(
    #     eks_cluster.endpoint,
    #     eks_cluster.certificate_authorities[0].data,
    #     cluster_name_o,
    # ).apply(lambda a: json.dumps({
    #     "apiVersion": "v1",
    #     "kind": "Config",
    #     "clusters": [{
    #         "name": "eks",
    #         "cluster": {
    #             "server": a[0],
    #             "certificate-authority-data": a[1],
    #         },
    #     }],
    #     "contexts": [{
    #         "name": "eks",
    #         "context": {"cluster": "eks", "user": "eks-user"},
    #     }],
    #     "current-context": "eks",
    #     "users": [{
    #         "name": "eks-user",
    #         "user": {
    #             "exec": {
    #                 "apiVersion": "client.authentication.k8s.io/v1beta1",
    #                 "command": "aws",
    #                 "args": ["eks", "get-token", "--cluster-name", a[2]],
    #             }
    #         },
    #     }],
    # }))
    
    k8s_provider = k8s.Provider("k8s-provider",
        delete_unreachable=True,
        kubeconfig=kube_config_content,
#        enable_server_side_apply=False,
    )
    
    # ------------------------------------------------------------------
    # 3. 初始化 Addons 組件 (解耦模式)
    # ------------------------------------------------------------------
    # 注意：這裡傳入的都是 String Output 或 Provider，不依賴 Cluster 物件
    addons = EksAddons("eks-addons",
        cluster_name=cluster_name,
        vpc_id=vpc_id,
        oidc_provider_arn=oidc_arn,
        oidc_provider_url=oidc_url,
        k8s_provider=k8s_provider,
    )

    # ------------------------------------------------------------------
    # 4. 執行安裝邏輯
    # ------------------------------------------------------------------
    
    
    # A. 安裝 AWS Load Balancer Controller
    alb_role_arn = addons.install_alb_controller()

    # B. 安裝 External Secrets Operator
    # 根據環境決定 SSM 路徑前綴，例如 /ai-chatbot/dev/*
    eso_role_arn = addons.install_external_secrets(
        ssm_path_prefix=f"/ai-chatbot/{env}/*"
    )

    # C. 安裝 Bedrock 權限 (給 Pod Identity)
    bedrock_role_arn = addons.install_bedrock_role(
        service_account="ai-chatbot-sa",
        namespace=namespace # 或是你部署 App 的 Namespace
    )

    # D. 安裝 CloudWatch & X-Ray 觀測性權限
    # 通常建議給 ADOT Collector 使用，或是直接給你的 App Pod SA

    obs_role_arn = addons.install_observability_role(
        service_account="adot-collector-sa", # 或是你的應用程式 SA 名稱
        namespace="observability"           # 建議放在獨立的 namespace
    )



    # ------------------------------------------------------------------
    # 5. Cloudflare 相關 (DNS & Certs)
    # ------------------------------------------------------------------
    cf_cfg = pulumi.Config("cloudflare")
    cf_token = cf_cfg.require_secret("apiToken")
    cf_domain = cf_cfg.require("domainName")
    cf_zone_id = cf_cfg.require("cloudflareZoneID")
    cf_provider = cloudflare.Provider("cf-provider", api_token=cf_token)

    cert = CloudflareValidatedCert(f"api-token-{env}",
        domain_name=cf_domain,
        zone_id=cf_zone_id,
        opts=pulumi.ResourceOptions(provider=cf_provider)
    )

    # D. 安裝 External-DNS
    addons.install_external_dns(
        api_token=cf_token,
        domain_filter=cf_domain
    )
    

    # ------------------------------------------------------------------
    # 6. 導出 Outputs (供 App 層或 Ansible 使用)
    # ------------------------------------------------------------------
    pulumi.export("alb_role_arn", alb_role_arn)
    pulumi.export("eso_role_arn", eso_role_arn)
    pulumi.export("bedrock_role_arn", bedrock_role_arn)
    pulumi.export("certificate_arn", cert.arn)
    
    # 也可以把 kubeconfig 再導出一次，方便 debug
    pulumi.export("kubeconfig", kubeconfig)
