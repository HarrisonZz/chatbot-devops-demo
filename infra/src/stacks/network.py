import pulumi
from components.network import VpcNetwork, VpcArgs
from pathlib import Path

def _bool(cfg: pulumi.Config, key: str, default: bool) -> bool:
    v = cfg.get_bool(key)
    return default if v is None else v


def _int(cfg: pulumi.Config, key: str, default: int) -> int:
    v = cfg.get_int(key)
    return default if v is None else v


def deploy(env: str) -> None:
    """
    Stack responsibility:
    - Decide env defaults (dev/test cheap, prod HA)
    - Read per-stack config overrides (optional)
    - Compose component(s)
    - Export outputs
    """
    cfg = pulumi.Config("network")
    is_prod = (env == "prod")

    # ✅ 環境預設（可被 Pulumi.<stack>.yaml 覆蓋）
    # dev/test: 2AZ + single NAT（省錢）
    # prod:     3AZ + NAT per AZ（HA）
    az_count = _int(cfg, "azCount", 3 if is_prod else 2)
    enable_ha_nat = _bool(cfg, "enableHaNat", is_prod)
    enable_endpoints = _bool(cfg, "enableEndpoints", True)

    cluster_name = cfg.get("clusterName") or f"eks-{env}"
    vpc_cidr = cfg.get("vpcCidr") or "10.0.0.0/16"

    net = VpcNetwork(
        "net",
        VpcArgs(
            cluster_name=cluster_name,
            vpc_cidr=vpc_cidr,
            az_count=az_count,
            enable_ha_nat=enable_ha_nat,
            enable_endpoints=enable_endpoints,
            tags={"app": "ai-chatbot", "env": env, "stack": pulumi.get_stack()},
        ),
    )

    # outputs（給 eks stack StackReference 用）
    pulumi.export("clusterName", cluster_name)
    pulumi.export("vpcId", net.vpc_id)
    pulumi.export("publicSubnetIds", net.public_subnet_ids)
    pulumi.export("privateSubnetIds", net.private_subnet_ids)