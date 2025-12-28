這是一個基於 **AWS EKS** 的完整 DevOps 平台專案。目標是在一個乾淨的 AWS 帳號上，透過 **CI Driven Infrastructure** 的方式，一鍵完成 EKS 平台、ECR、Addons、Observability 以及 Chatbot 應用程式的完整生命週期管理。

---

## 🏗️ 系統架構 (Architecture)

### Service Architecture
使用者流量經由 Cloudflare Proxy (CDN/WAF) 接入，經過安全過濾與快取後，轉發至 AWS ALB，再路由至 EKS 內部的 Chatbot Pod，最終由後端調用 Amazon Bedrock 進行 AI 推論。

---

## 🚀 使用指南 (Lifecycle Management)
本專案採用 **GitHub Actions** 作為唯一的基礎設施操作入口。
### 0. 先決條件 (Prerequisites)
在開始之前，請確保 AWS 帳號已完成以下設定：
1.  建立 **GitHub OIDC Identity Provider**。
2.  建立一個 **IAM Role** 供 GitHub Actions 使用 (`AssumeRoleWithWebIdentity`)。
3.  該 IAM Role 需具備：
    * 建立 Pulumi 定義之 AWS 資源的 API 權限。
    * EKS Cluster 的操作與管理權限。

### 核心操作流程:
這個 Repo 的設計哲學是 "CI Driven Infrastructure"。所有的建置與銷毀操作，最標準的方式是透過 GitHub Actions 觸發

### 1. 啟動環境 (Provisioning)
建立 VPC、EKS Cluster、Node Groups 以及基礎 Addons。
1.  前往 GitHub Repo 的 **Actions** 頁面。
2.  選擇 Workflow: **"Platform Lifecycle Management"**。
3.  點擊 **Run workflow**。
4.  在 Action 下拉選單選擇：`up` 並執行。

### 2. 連線與驗證 (Access & Verify)
環境建立完成後，設定本機存取權限：
1.  更新 kubeconfig：
    ```bash
    aws eks update-kubeconfig --name eks-dev --region ap-northeast-1
    ```
2.  **設定權限**：建立 Access Entry 並綁定 Admin Policy (可透過修改 Pulumi 程式碼或 AWS CLI 手動加入)。

#### 3. 部署應用程式 (Deploy Apps via GitOps)
1.  **上傳靜態資源**：
    * 在 Actions 頁面選擇 `artifact` 並執行 (上傳至 S3/CloudFront)。
2.  **觸發部署**：
    * 在 Actions 頁面選擇 `deploy` 並執行。
    * 此步驟會觸發 ArgoCD 自動同步。
3.  **持續交付流程**：
    * App 程式碼更新後，CI 自動 Build Docker Image 並推送到 ECR。
    
### 4. 銷毀環境 (Destroy)
**⚠️ 注意：此操作將刪除所有資源。**
1.  前往 GitHub Repo 的 **Actions** 頁面。
2.  選擇 Workflow: **"Platform Lifecycle Management"**。
3.  在 Action 下拉選單選擇：`destroy` 並執行。 

> If destroy is slow or stuck (e.g., ALB/Ingress finalizers), refer to [`docs/troubleshooting.md`](docs/troubleshooting.md).

---

## 📂 專案目錄結構 (Project Structure)

* `ansible/` - **流程編排核心**：負責串聯 Bootstrap → Platform Up → Upload Static → Destroy 等流程。
* `app/` - **應用程式源碼**：包含 Chatbot 的 Dockerfile、靜態檔案與 Streamlit App Code。
* `infra/` - **基礎設施代碼 (IaC)**：使用 Pulumi (Python) 建立 AWS 雲端資源與 EKS 附加元件。
* `k8s/` - **Kubernetes Manifests**：Kustomize 設定檔與應用程式部署定義。
* `scripts/` - **輔助工具**：Chatbot 服務容器化相關的 Helper Scripts。

---

### Chatbot 服務架構圖
![service](./docs/images/service_arch.png)

####  My URL : https://dev.hrscyj.uk 

User (Chrome) ➡️ Cloudflare DNS ➡️ AWS ALB (Ingress) ➡️ [EKS Cluster] -> Service -> Chatbot Pod > ➡️ AWS Bedrock

![chatbot](./docs/images/chatbot_interface.png)
![chatbot](./docs/images/chatbot_interface_2.png)
![chatbot](./docs/images/chatbot_interface_3.png)

## 🛠️ 技術堆疊 (Tech Stack)

### 1. 基礎設施層 (Infra Layer)
| 元件 | 用途 |
| :--- | :--- |
| **Amazon EKS** | 核心控制平面，託管所有工作負載 |
| **Amazon ECR** | 儲存 Chatbot 服務的 Docker Image |
| **Amazon VPC** | 建構隔離且安全的網路環境 |
| **AWS ALB** | 透過 Load Balancer Controller 自動建立，負責 Ingress 流量轉發 |
| **CloudFront** | CDN 服務與 WAF，負責快取靜態資源並提供邊緣安全防護 |
| **AWS IAM** | 權限管理 (整合 OIDC 與 IRSA) |
| **Amazon S3** | 儲存靜態網頁素材 |
| **Amazon Bedrock** | AI 基礎模型服務 (Claude/Titan) |
| **AWS SSM** | Parameter Store，儲存基礎設施配置變數 |

### 2. 平台服務層 (Platform Layer)
| 類別 | 核心元件 | 功能描述 |
| :--- | :--- | :--- |
| **GitOps** | **ArgoCD** | 自動同步、漂移檢測、App of Apps 管理模式 |
| **Secret Mgmt** | **External Secrets (ESO)** | 實現 Secret Zero，從 SSM 動態注入機密資訊 |
| **Ingress** | **ALB Controller** | 橋接 AWS ALB，提供 Layer 7 路由與 SSL 卸載 |
| **Security** | **Cert-Manager** | 管理叢集內憑證 (Webhook 驗證) |
| **Observability**| **ADOT Collector** | 收集 Logs, Metrics, Traces 並發送至 AWS CloudWatch/X-Ray |
| **AI Auth** | **EKS Pod Identity** | 簡化 Bedrock 調用的身份驗證 |
| **Workload** | **AI Chatbot** | **Bedrock 服務介面化 API**。封裝了與 Amazon Bedrock 的溝通邏輯，透過 Streamlit 提供使用者友善的對話介面。 |
---

### CI/CD : 
本專案採用 "CI 推送 (Push) + CD 拉取 (Pull)" 的混合模式，並結合 GitHub Actions 與 ArgoCD 來實現全自動化的軟體交付流程
**CI 階段：持續整合 (GitHub Actions)**
當開發者將程式碼 Push 到 main 分支時，GitHub Actions 會觸發 Build & Push 流程

**CD 階段：持續部署 (ArgoCD)**
Git Repo 中的 Manifest 檔案被 CI 更新，ArgoCD 就會接手

## 📊 可觀測性 (Observability)

本專案採用 **ADOT (AWS Distro for OpenTelemetry)** 建構遙測數據中轉站 (Telemetry Gateway)。

* **Logs (日誌)**: 透過 OTLP 收集並轉送至 **CloudWatch Logs**。
![log](./docs/images/log.png)

* **Traces (追蹤)**: 利用 TraceID 與 Span 繪製請求路徑圖，透過 **AWS X-Ray Service Map** 分析效能瓶頸。
透過 TraceID 和 Span 能畫出「請求路徑圖」
![trace](./docs/images/trace.png)

當使用者說「聊天機器人回應很慢」時，你可以去 AWS X-Ray 看服務地圖 (Service Map)
![traceMap](./docs/images/TraceMap.png)

* **Metrics (指標)**: ADOT Collector 自動收集系統指標。
ADOT Collector 自動收集與發送系統指標
![metric](./docs/images/metric.png)

* **SLI/SLO**: 定義 **服務成功率** 與 **延遲 (Latnecy p95)** 作為關鍵指標，並針對異常設定 CloudWatch Alarm 告警。
![customSLI](./docs/images/custom_SLI.png)

* **Alarm 告警**
透過自訂 SLI 將 Latency 和 Fallback 率設置告警
![p95](./docs/images/p95_alarm.png)
![svc_success](./docs/images/svc_success.png)

---

## 💡 架構亮點 (Key Highlights)

* **無金鑰架構 (Keyless Security)** 🔐
    * **CI 端**: 全面採用 **GitHub OIDC**，無需長效 AWS Access Key。
    * **Runtime 端**: 使用 **IRSA** 與 **Pod Identity** 實現最小權限原則。
    * **Secret 端**: 結合 **ESO** 與 **SSM Parameter Store**，達成 Git 內不存敏感資料 (Secret Zero)。
* **平台工程思維 (Platform Engineering)** ⚙️
    * 結合 **Pulumi (IaC)** 與 **Ansible**，將複雜的建置流程標準化，實現「一鍵建置、一鍵銷毀」。
* **GitOps 安全模型** 🛡️
    * 應用程式部署採用 **Pull Model (ArgoCD)**，CI Server 無需持有叢集管理權限，大幅提升安全性。

---

