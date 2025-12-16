import pulumi
import pulumi_aws as aws
import pulumi_synced_folder as synced_folder


class StaticAssetsCdn(pulumi.ComponentResource):
    """
    S3 (private) as origin + CloudFront (OAC) as public CDN endpoint.
    Uploads a local folder into S3, then serves via CloudFront HTTPS domain.
    """

    def __init__(
        self,
        name: str,
        folder_path: str,
        *,
        web_acl_id: pulumi.Input[str] | None = None,
        default_root_object: str | None = None,
        force_destroy: bool = True,
        tags: dict[str, str] | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("custom:resource:StaticAssetsCdn", name, None, opts)

        origin_id = f"{name}-s3-origin"

        # 1) Private S3 bucket (origin only)
        self.bucket = aws.s3.Bucket(
            f"{name}-bucket",
            force_destroy=force_destroy,
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.log_bucket = aws.s3.Bucket(
            f"{name}-cf-logs",
            force_destroy=True,
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # NOTE: pulumi_synced_folder 目前 acl 是 required，所以我們維持 bucket 允許 ACL，
        # 但所有物件都用 "private" ACL + public access block 全開（不允許 public）。
        ownership_controls = aws.s3.BucketOwnershipControls(
            f"{name}-ownership",
            bucket=self.bucket.id,
            rule=aws.s3.BucketOwnershipControlsRuleArgs(
                object_ownership="BucketOwnerPreferred",
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        public_access_block = aws.s3.BucketPublicAccessBlock(
            f"{name}-public-access-block",
            bucket=self.bucket.id,
            block_public_acls=True,
            ignore_public_acls=True,
            block_public_policy=True,
            restrict_public_buckets=True,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # 2) Upload local folder to S3 (private objects)
        synced_folder.S3BucketFolder(
            f"{name}-sync",
            path=folder_path,
            bucket_name=self.bucket.bucket,
            acl="private",
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[ownership_controls, public_access_block],
            ),
        )

        # 3) CloudFront Origin Access Control (OAC)
        self.oac = aws.cloudfront.OriginAccessControl(
            f"{name}-oac",
            name=f"{name}-oac",
            origin_access_control_origin_type="s3",
            signing_behavior="always",
            signing_protocol="sigv4",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # 4) Cache policy for static assets
        self.cache_policy = aws.cloudfront.CachePolicy(
            f"{name}-cache-policy",
            name=f"{name}-static-cache",
            default_ttl=86400,      # 1 day
            max_ttl=31536000,       # 1 year
            min_ttl=0,
            parameters_in_cache_key_and_forwarded_to_origin={
                "cookies_config": {"cookie_behavior": "none"},
                "headers_config": {"header_behavior": "none"},
                "query_strings_config": {"query_string_behavior": "none"},
                "enable_accept_encoding_brotli": True,
                "enable_accept_encoding_gzip": True,
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        # 5) CloudFront distribution
        self.distribution = aws.cloudfront.Distribution(
            f"{name}-cdn",
            enabled=True,
            default_root_object=default_root_object,
            origins=[{
                "domain_name": self.bucket.bucket_regional_domain_name,
                "origin_id": origin_id,
                "origin_access_control_id": self.oac.id,
                "s3_origin_config": {                                  
                    "origin_access_identity": "",
                },
            }],
            default_cache_behavior={
                "target_origin_id": origin_id,
                "viewer_protocol_policy": "redirect-to-https",
                "allowed_methods": ["GET", "HEAD", "OPTIONS"],
                "cached_methods": ["GET", "HEAD"],
                "compress": True,
                "cache_policy_id": self.cache_policy.id,
            },
            restrictions={
                "geo_restriction": {
                    "restriction_type": "none",
                }
            },
            viewer_certificate={
                "cloudfront_default_certificate": True,
            },
            tags=tags,
            web_acl_id=web_acl_id,
            opts=pulumi.ResourceOptions(parent=self),
            logging_config=aws.cloudfront.DistributionLoggingConfigArgs(
                bucket=self.log_bucket.bucket_domain_name,  # 類似 xxx.s3.amazonaws.com
                include_cookies=False,
                prefix=f"{name}/",                     # log 檔案前綴
            ),
        )

        # 6) S3 bucket policy: only allow CloudFront (service principal) to read objects
        origin_policy = aws.iam.get_policy_document_output(
            statements=[aws.iam.GetPolicyDocumentStatementArgs(
                sid="AllowCloudFrontRead",
                effect="Allow",
                principals=[aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                    type="Service",
                    identifiers=["cloudfront.amazonaws.com"],
                )],
                actions=["s3:GetObject"],
                resources=[pulumi.Output.concat(self.bucket.arn, "/*")],
                conditions=[aws.iam.GetPolicyDocumentStatementConditionArgs(
                    test="StringEquals",
                    variable="AWS:SourceArn",
                    values=[self.distribution.arn],
                )],
            )]
        )

        aws.s3.BucketPolicy(
            f"{name}-bucket-policy",
            bucket=self.bucket.bucket,
            policy=origin_policy.json,
            opts=pulumi.ResourceOptions(parent=self),
        )


        # CloudFront legacy standard logs 寫 S3 需要 ACL enabled（不要 BucketOwnerEnforced）
        aws.s3.BucketOwnershipControls(
            f"{name}-cf-logs-ownership",
            bucket=self.log_bucket.id,
            rule=aws.s3.BucketOwnershipControlsRuleArgs(object_ownership="BucketOwnerPreferred"),
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.s3.BucketPublicAccessBlock(
            f"{name}-cf-logs-pab",
            bucket=self.log_bucket.id,
            block_public_acls=True,
            ignore_public_acls=True,
            block_public_policy=True,
            restrict_public_buckets=True,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # 7) Outputs
        self.assets_base_url = self.distribution.domain_name.apply(lambda d: f"https://{d}")
        self.bucket_name = self.bucket.bucket
        self.bucket_arn = self.bucket.arn
        self.distribution_id = self.distribution.id
        self.distribution_arn = self.distribution.arn

        self.register_outputs({
            "assets_base_url": self.assets_base_url,
            "bucket_name": self.bucket_name,
            "bucket_arn": self.bucket_arn,
            "distribution_id": self.distribution_id,
            "distribution_arn": self.distribution_arn,
        })
