# Troubleshooting & Recovery Runbook

1) Destroy 卡住（常見：ALB/Ingress finalizer）

### 清理 Pulumi Addons Stack state（高風險）

⚠️ 僅在以下條件同時成立時使用：

已確認相關 AWS 資源（ALB/TargetGroup/SecurityGroup 等）實體上已刪除或你接受它們已不再由該 stack 管理

pulumi -s addons-dev destroy 仍因 state 殘留而卡住/失敗（例如一直等某些 k8s/AWS 資源）

你接受此操作可能造成 state 與現況短暫不一致，並願意做驗證/收尾
    
    ```bash
    # 1. 匯出目前的壞掉的 State
    pulumi stack export --stack addons-dev > state.json

    # 2. (關鍵步驟) 使用 jq 清空資源列表
    # 這會把 resources 變成空陣列 []，但保留 Stack 的 config 和版本資訊
    jq '.deployment.resources = []' state.json > state_clean.json

    # 3. 把乾淨的 State 匯入回去
    pulumi stack import --stack addons-dev < state_clean.json

    # 4. 驗證 (應該要看到 Resources: 0)
    pulumi stack --stack addons-dev

    # 5. 刪除暫存檔 (選做)
    rm state.json state_clean.json
    ```