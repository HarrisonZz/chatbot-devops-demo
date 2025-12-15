import pulumi
import pulumi_aws as aws
import pulumi_synced_folder as synced_folder
import json

class StaticWebsite(pulumi.ComponentResource):

    def __init__(self, name: str, folder_path: str, opts=None):
        # 1. 初始化 ComponentResource (這是標準寫法)
        # "custom:resource:StaticWebsite" 是這個組件在 Pulumi Graph 顯示的類型名稱
        super().__init__('custom:resource:StaticWebsite', name, None, opts)

        # 2. 建立 S3 Bucket
        # 注意：parent=self 代表這個 Bucket 是屬於這個 Component 的子資源
        self.bucket = aws.s3.Bucket(f"{name}-bucket",
            website=aws.s3.BucketWebsiteArgs(
                index_document="index.html",
            ),
            force_destroy=True,
            opts=pulumi.ResourceOptions(parent=self) # 👈 關鍵：繼承關係
        )

        ownership_controls = aws.s3.BucketOwnershipControls(f"{name}-ownership",
            bucket=self.bucket.id,
            rule=aws.s3.BucketOwnershipControlsRuleArgs(
                object_ownership="BucketOwnerPreferred" # 允許 ACL 生效
            ),
            opts=pulumi.ResourceOptions(parent=self)
        )

        # 3. 設定公開權限 (封裝在模組內，外部使用者不用操心)
        public_access_block = aws.s3.BucketPublicAccessBlock(f"{name}-public-block",
            bucket=self.bucket.id,
            block_public_acls=False,
            block_public_policy=False,
            ignore_public_acls=False,
            restrict_public_buckets=False,
            opts=pulumi.ResourceOptions(parent=self)
        )

        aws.s3.BucketPolicy(f"{name}-policy",
            bucket=self.bucket.id,
            policy=self.bucket.id.apply(lambda id: json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{id}/*"]
                }]
            })),
            opts=pulumi.ResourceOptions(parent=self, depends_on=[public_access_block])
        )

        # 4. 同步檔案
        synced_folder.S3BucketFolder(f"{name}-sync",
            path=folder_path,
            bucket_name=self.bucket.bucket,
            acl="public-read",
            opts=pulumi.ResourceOptions(parent=self)
        )

        # 5. 輸出變數 (像是 Terraform 的 output.tf)
        self.website_url = self.bucket.website_endpoint.apply(lambda url: f"http://{url}")
        
        # 6. 註冊輸出 (讓 Pulumi 知道這個組件初始化完了)
        self.register_outputs({
            "website_url": self.website_url
        })