# Installation Guide

## Prerequisites

- Kubernetes 1.25+ cluster
- Helm 3.x
- Access to the internal container registry
- cosign (for verifying artifact signatures)

## Air-Gapped Installation

### 1. Verify Release Bundle Signature

```bash
cosign verify-blob \
    --key cosign.pub \
    --signature product-release-X.Y.Z.zip.sig \
    product-release-X.Y.Z.zip
```

### 2. Extract Release Bundle

```bash
unzip product-release-X.Y.Z.zip
```

### 3. Load Container Images

If images are not already in your registry:

```bash
# Load images from the release bundle into your local registry
docker load < images/container-a.tar
docker tag product/container-a:X.Y.Z your-registry/product/container-a:X.Y.Z
docker push your-registry/product/container-a:X.Y.Z
# Repeat for all images
```

### 4. Install with Helm

```bash
helm install product ./helm/product-chart-X.Y.Z.tgz \
    --namespace production \
    --values custom-values.yaml \
    --create-namespace
```

### 5. Verify Installation

```bash
kubectl get pods -n production -l app=product
helm test product -n production
```

## Troubleshooting

*Add common issues and resolutions here.*
