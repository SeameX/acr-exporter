# ACR Exporter – Prometheus Exporter for Azure Container Registry

Exports image size metrics from Azure Container Registry (`az acr`) for Prometheus scraping.

---

## 🚀 Installation

### Prerequisites

- Kubernetes cluster  
- Helm v3+  
- Azure credentials with permissions to access the ACR  
- Kubernetes Secret containing Azure credentials (managed outside Helm)  
- Prometheus Operator
- Grafana Operator

---

## 🔐 Secret Handling

You must create and manage the Azure credentials secret outside of Helm.

Create the Kubernetes Secret manually with your Azure credentials:

```bash
kubectl create secret generic azure-credentials-secret \
  --from-literal=clientId=<your-client-id> \
  --from-literal=clientSecret=<your-client-secret> \
  --from-literal=tenantId=<your-tenant-id>
````

---

## 🧭 Quick Install & Metrics Endpoint

Install the chart referencing your existing secret:

```bash
helm install acr-exporter oci://ghcr.io/seamex/helm/acr-exporter \
  --version 0.1.0 \
  --set acrName=<your-acr-name> \
  --set secretName=azure-credentials-secret
```

Make sure your Prometheus server is configured to scrape this endpoint.

---

## ⚙️ Values

| Key                      | Type   | Default                   | Description                             |
|--------------------------|--------|---------------------------|---------------------------------------|
| `acrName`                | string | (required)                | Name of your Azure Container Registry |
| `refreshInterval`        | string | `"43200"`                 | Scraping interval in seconds           |
| `secretName`             | string | `azure-credentials-secret`| Name of the Kubernetes Secret          |
| `podMonitorAdditionalLabels` | object | `{}`                     | Additional labels to add to PodMonitor |
