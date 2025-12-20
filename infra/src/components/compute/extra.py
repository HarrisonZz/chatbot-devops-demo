import pulumi
import pulumi_aws as aws
import pulumi_cloudflare as cloudflare

class CloudflareValidatedCert(pulumi.ComponentResource):
    def __init__(self, name: str, domain_name: str, zone_id: str, opts: pulumi.ResourceOptions = None):
        super().__init__('custom:cert:CloudflareValidatedCert', name, {}, opts)

        # 1. 申請 ACM 憑證
        self.certificate = aws.acm.Certificate(f"{name}-cert",
            domain_name=domain_name,
            validation_method="DNS",
            opts=pulumi.ResourceOptions(parent=self)
        )

        # 處理異步數據：提取驗證資訊並修剪域名末尾的點 (Cloudflare 不接受結尾的點)
        val_options = self.certificate.domain_validation_options.apply(lambda opts: opts[0])
        clean_name = val_options.resource_record_name.apply(lambda n: n.rstrip('.'))

        # 2. 在 Cloudflare 建立驗證紀錄 (使用最新的 DnsRecord)
        validation_record = cloudflare.DnsRecord(f"{name}-validation-record",
            zone_id=zone_id,
            name=clean_name,
            type=val_options.resource_record_type,
            content=val_options.resource_record_value,
            ttl=60,
            proxied=False, # 驗證紀錄必須關閉代理
            opts=pulumi.ResourceOptions(
                parent=self, 
                provider=opts.provider if opts else None
            )
        )

        # 3. 觸發「等待驗證成功」的資源
        # 這裡需要等待 DNS 紀錄在 Cloudflare 生效
        self.validation = aws.acm.CertificateValidation(f"{name}-cert-validation",
            certificate_arn=self.certificate.arn,
            validation_record_fqdns=[validation_record.name],
            opts=pulumi.ResourceOptions(parent=self)
        )

        # 4. 將驗證通過後的 ARN 存入 SSM Parameter Store
        # 使用 self.validation.certificate_arn 確保存入的是已生效的 ARN
        self.ssm_param = aws.ssm.Parameter(f"{name}-cert-arn-ssm",
            name=f"/network/cert/{name}/alb-cert-arn", # 建議的路徑格式
            type="String",
            value=self.validation.certificate_arn,
            opts=pulumi.ResourceOptions(parent=self)
        )

        # 輸出最終可用的 ARN
        self.arn = self.validation.certificate_arn
        self.register_outputs({"arn": self.arn})