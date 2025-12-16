from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
import ipaddress

import pulumi
import pulumi_aws as aws


@dataclass(frozen=True)
class VpcArgs:
    """
    HA VPC for EKS (public/private subnets + IGW + NAT + routes + optional endpoints)

    Notes:
    - Subnet CIDRs are derived from vpc_cidr by splitting into /24 blocks.
    - Requires vpc_cidr to be large enough to allocate (2 * az_count) /24 subnets.
    """
    cluster_name: str
    vpc_cidr: str = "10.0.0.0/16"
    az_count: int = 3

    # NAT: True -> NAT per AZ (HA); False -> single NAT (cost saving)
    enable_ha_nat: bool = True

    # Endpoints: S3 gateway + ECR/Logs/STS interface endpoints
    enable_endpoints: bool = True
    interface_endpoints: Sequence[str] = ("ecr.api", "ecr.dkr", "logs", "sts")

    # EKS cluster tag value: "shared" (recommended when multiple stacks share VPC)
    eks_cluster_tag_value: str = "shared"

    tags: Optional[Dict[str, str]] = None


def _merge_tags(*maps: Optional[Dict[str, str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in maps:
        if m:
            out.update(m)
    return out


def _derive_subnet_cidrs(vpc_cidr: str, az_count: int, new_prefix: int = 24) -> Tuple[List[str], List[str]]:
    """
    Split vpc_cidr into /new_prefix subnets, allocate first az_count for public,
    next az_count for private.
    """
    net = ipaddress.ip_network(vpc_cidr)
    if new_prefix < net.prefixlen:
        raise ValueError(f"new_prefix={new_prefix} must be >= vpc prefix {net.prefixlen}")

    subnets = list(net.subnets(new_prefix=new_prefix))
    need = 2 * az_count
    if len(subnets) < need:
        raise ValueError(f"vpc_cidr {vpc_cidr} cannot provide {need} subnets of /{new_prefix}")

    pub = [str(s) for s in subnets[:az_count]]
    pri = [str(s) for s in subnets[az_count: az_count * 2]]
    return pub, pri


class VpcNetwork(pulumi.ComponentResource):
    """
    Creates:
    - VPC
    - IGW
    - Public subnets + public route table (0.0.0.0/0 -> IGW)
    - Private subnets + private route tables (0.0.0.0/0 -> NAT)
    - NAT GW (per AZ if enable_ha_nat else single)
    - Optional VPC endpoints (S3 gateway + interface endpoints)
    """

    def __init__(self, name: str, args: VpcArgs, opts: Optional[pulumi.ResourceOptions] = None):
        super().__init__("pkg:network:VpcNetwork", name, None, opts)

        parent_opts = pulumi.ResourceOptions(parent=self)

        base_tags = _merge_tags(
            {"ManagedBy": "pulumi"},
            args.tags,
        )
        eks_cluster_tag = {f"kubernetes.io/cluster/{args.cluster_name}": args.eks_cluster_tag_value}

        # --- AZ selection ---
        azs = aws.get_availability_zones(state="available")
        az_list = azs.names[: max(1, min(args.az_count, len(azs.names)))]

        # --- CIDR allocation (public/private) ---
        public_cidrs, private_cidrs = _derive_subnet_cidrs(args.vpc_cidr, az_count=len(az_list), new_prefix=24)

        # --- VPC ---
        vpc = aws.ec2.Vpc(
            f"{name}-vpc",
            cidr_block=args.vpc_cidr,
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-vpc"}),
            opts=parent_opts,
        )

        # --- IGW + public RT ---
        igw = aws.ec2.InternetGateway(
            f"{name}-igw",
            vpc_id=vpc.id,
            tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-igw"}),
            opts=parent_opts,
        )

        public_rt = aws.ec2.RouteTable(
            f"{name}-public-rt",
            vpc_id=vpc.id,
            routes=[aws.ec2.RouteTableRouteArgs(cidr_block="0.0.0.0/0", gateway_id=igw.id)],
            tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-public-rt"}),
            opts=parent_opts,
        )

        # --- Subnets ---
        public_subnets: List[aws.ec2.Subnet] = []
        private_subnets: List[aws.ec2.Subnet] = []

        for i, az in enumerate(az_list):
            pub = aws.ec2.Subnet(
                f"{name}-public-{i}",
                vpc_id=vpc.id,
                availability_zone=az,
                cidr_block=public_cidrs[i],
                map_public_ip_on_launch=True,
                tags=_merge_tags(
                    base_tags,
                    eks_cluster_tag,
                    {
                        "Name": f"{args.cluster_name}-public-{az}",
                        "kubernetes.io/role/elb": "1",  # internet-facing LB
                    },
                ),
                opts=parent_opts,
            )
            aws.ec2.RouteTableAssociation(
                f"{name}-public-rta-{i}",
                subnet_id=pub.id,
                route_table_id=public_rt.id,
                opts=parent_opts,
            )
            public_subnets.append(pub)

            pri = aws.ec2.Subnet(
                f"{name}-private-{i}",
                vpc_id=vpc.id,
                availability_zone=az,
                cidr_block=private_cidrs[i],
                map_public_ip_on_launch=False,
                tags=_merge_tags(
                    base_tags,
                    eks_cluster_tag,
                    {
                        "Name": f"{args.cluster_name}-private-{az}",
                        "kubernetes.io/role/internal-elb": "1",  # internal LB
                    },
                ),
                opts=parent_opts,
            )
            private_subnets.append(pri)

        # --- NAT gateways (HA or single) ---
        nat_count = len(az_list) if args.enable_ha_nat else 1
        nat_gws: List[aws.ec2.NatGateway] = []

        for i in range(nat_count):
            eip = aws.ec2.Eip(
                f"{name}-nat-eip-{i}",
                domain="vpc",
                tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-nat-eip-{i}"}),
                opts=parent_opts,
            )
            nat = aws.ec2.NatGateway(
                f"{name}-natgw-{i}",
                allocation_id=eip.id,
                subnet_id=public_subnets[i].id,
                tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-natgw-{i}"}),
                opts=parent_opts,
            )
            nat_gws.append(nat)

        # --- Private RTs (per AZ) ---
        private_rts: List[aws.ec2.RouteTable] = []
        for i, pri in enumerate(private_subnets):
            nat_index = i if args.enable_ha_nat else 0
            rt = aws.ec2.RouteTable(
                f"{name}-private-rt-{i}",
                vpc_id=vpc.id,
                routes=[aws.ec2.RouteTableRouteArgs(cidr_block="0.0.0.0/0", nat_gateway_id=nat_gws[nat_index].id)],
                tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-private-rt-{i}"}),
                opts=parent_opts,
            )
            aws.ec2.RouteTableAssociation(
                f"{name}-private-rta-{i}",
                subnet_id=pri.id,
                route_table_id=rt.id,
                opts=parent_opts,
            )
            private_rts.append(rt)

        # --- VPC Endpoints (optional) ---
        vpce_sg: Optional[aws.ec2.SecurityGroup] = None

        if args.enable_endpoints:
            # S3 gateway endpoint -> attach to private route tables
            aws.ec2.VpcEndpoint(
                f"{name}-vpce-s3",
                vpc_id=vpc.id,
                vpc_endpoint_type="Gateway",
                service_name=f"com.amazonaws.{aws.config.region}.s3",
                route_table_ids=[rt.id for rt in private_rts],
                tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-vpce-s3"}),
                opts=parent_opts,
            )

            # Interface endpoints need SG and subnets
            vpce_sg = aws.ec2.SecurityGroup(
                f"{name}-vpce-sg",
                vpc_id=vpc.id,
                description="VPC Endpoint SG (allow 443 from within VPC)",
                ingress=[
                    aws.ec2.SecurityGroupIngressArgs(
                        protocol="tcp",
                        from_port=443,
                        to_port=443,
                        cidr_blocks=[args.vpc_cidr],
                    )
                ],
                egress=[
                    aws.ec2.SecurityGroupEgressArgs(
                        protocol="-1",
                        from_port=0,
                        to_port=0,
                        cidr_blocks=["0.0.0.0/0"],
                    )
                ],
                tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-vpce-sg"}),
                opts=parent_opts,
            )

            for svc in args.interface_endpoints:
                aws.ec2.VpcEndpoint(
                    f"{name}-vpce-{svc.replace('.', '-')}",
                    vpc_id=vpc.id,
                    vpc_endpoint_type="Interface",
                    service_name=f"com.amazonaws.{aws.config.region}.{svc}",
                    subnet_ids=[s.id for s in private_subnets],
                    private_dns_enabled=True,
                    security_group_ids=[vpce_sg.id],
                    tags=_merge_tags(base_tags, {"Name": f"{args.cluster_name}-vpce-{svc}"}),
                    opts=parent_opts,
                )

        # --- Exposed outputs ---
        self.vpc = vpc
        self.vpc_id = vpc.id
        self.public_subnets = public_subnets
        self.private_subnets = private_subnets
        self.public_subnet_ids = pulumi.Output.all(*[s.id for s in public_subnets])
        self.private_subnet_ids = pulumi.Output.all(*[s.id for s in private_subnets])
        self.vpce_sg_id = vpce_sg.id if vpce_sg else None

        self.register_outputs(
            {
                "vpcId": self.vpc_id,
                "publicSubnetIds": self.public_subnet_ids,
                "privateSubnetIds": self.private_subnet_ids,
                "vpceSecurityGroupId": self.vpce_sg_id,
            }
        )
