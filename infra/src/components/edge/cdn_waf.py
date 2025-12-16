import pulumi
import pulumi_aws as aws

class CdnWaf(pulumi.ComponentResource):
    """
    WAFv2 WebACL for CloudFront (scope=CLOUDFRONT).
    IMPORTANT: must be created in us-east-1.
    """

    def __init__(
        self,
        name: str,
        rate_limit: int = 300,              # per-IP within evaluation window
        evaluation_window_sec: int = 300,    # 60/120/300/600
        scope_down_path_prefix: str | None = None,  # e.g. "/api" to limit only API
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("custom:edge:CdnWaf", name, None, opts)

        # CloudFront-scoped WAF must be in us-east-1
        waf_provider = aws.Provider(f"{name}-waf-us-east-1", region="us-east-1",
                                    opts=pulumi.ResourceOptions(parent=self))

        rate_stmt: dict = {
            "limit": rate_limit,
            "aggregate_key_type": "IP",
            "evaluation_window_sec": evaluation_window_sec,
        }

        if scope_down_path_prefix:
            rate_stmt["scope_down_statement"] = {
                "byte_match_statement": {
                    "field_to_match": {"uri_path": {}},
                    "positional_constraint": "STARTS_WITH",
                    "search_string": scope_down_path_prefix,
                    "text_transformations": [{"priority": 0, "type": "NONE"}],
                }
            }

        self.web_acl = aws.wafv2.WebAcl(
            f"{name}-web-acl",
            scope="CLOUDFRONT",
            default_action={"allow": {}},
            visibility_config={
                "cloudwatch_metrics_enabled": True,
                "metric_name": f"{name}-web-acl",
                "sampled_requests_enabled": True,
            },
            rules=[{
                "name": "rate-limit-per-ip",
                "priority": 1,
                "action": {"block": {}},
                "visibility_config": {
                    "cloudwatch_metrics_enabled": True,
                    "metric_name": f"{name}-rate-limit",
                    "sampled_requests_enabled": True,
                },
                "statement": {"rate_based_statement": rate_stmt},
            }],
            opts=pulumi.ResourceOptions(parent=self, provider=waf_provider),
        )

        self.web_acl_arn = self.web_acl.arn

        self.register_outputs({
            "web_acl_arn": self.web_acl_arn,
        })
