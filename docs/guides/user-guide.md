# Product User Guide

## Overview

This document describes how to use the deployed product system.

## Getting Started

*This is a template. Replace with actual product-specific user documentation.*

### Prerequisites

- Kubernetes cluster with Helm 3.x installed
- Access to the internal container registry
- Network connectivity to required external systems

### Installation

```bash
helm install product ./helm/product-chart \
    --namespace production \
    --values helm/product-chart/values-prod.yaml
```

### Configuration

Configuration is managed through Helm values. See `values.yaml` for all available options.

### Verifying Deployment

```bash
kubectl get pods -n production -l app=product
kubectl logs -n production -l app=product
```
