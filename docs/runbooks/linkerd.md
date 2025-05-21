# Linkerd Runbook

This document provides common Linkerd CLI commands for observing and debugging services within the mesh.

## Prerequisites

- Linkerd CLI installed locally.
- Kubectl configured to point to your Kubernetes cluster.
- Linkerd control plane installed in the cluster.
- Your services [injected with the Linkerd proxy](https://linkerd.io/2/tasks/adding-your-service/).

## Common Commands

Replace `<namespace>` with the namespace of your service (e.g., `default`, `your-app-namespace`) and `<service-name>` with the Kubernetes service name (e.g., `api-gateway`, `offers-api`).

### 1. Check Linkerd Status

Verify the Linkerd control plane and data plane components are healthy.

```bash
linkerd check
```

### 2. Tap: Real-time Request/Response Inspection

Tap allows you to see a live stream of requests flowing to and from a specific resource (pod, deployment, service).

**Tap a Deployment:**
```bash
linkerd viz tap deploy/<deployment-name> -n <namespace>
```
Example for `offers-api` in `default` namespace:
```bash
linkerd viz tap deploy/offers-api -n default
```

**Tap a Service:**
```bash
linkerd viz tap svc/<service-name> -n <namespace>
```
Example:
```bash
linkerd viz tap svc/api-gateway -n default
```

**Tap with specific filters (e.g., path, method):**
```bash
linkerd viz tap deploy/offers-api -n default --path /offers --method POST
```

### 3. Top: Real-time Service Metrics (Golden Metrics)

Top shows success rates, request volumes (RPS), and latencies for services in the mesh.

**Top for all services in a namespace:**
```bash
linkerd viz top -n <namespace>
```

**Top for a specific Deployment:**
```bash
linkerd viz top deploy/<deployment-name> -n <namespace>
```
Example:
```bash
linkerd viz top deploy/offers-api -n default
```

**Top showing routes (requires ServiceProfiles to be applied):**
This command is very useful once ServiceProfiles are configured, as it will break down metrics per route defined in the profile.
```bash
linkerd viz top routes deploy/<deployment-name> -n <namespace>
# or for a service
linkerd viz top routes svc/<service-name> -n <namespace>
```
Example:
```bash
linkerd viz top routes svc/offers-api -n default --to svc/api-gateway -n default
```
(The `--to` flag shows traffic from `offers-api` to `api-gateway`)

### 4. Stats: Detailed Metrics for a Resource

Provides detailed statistics, including those per route from ServiceProfiles.

```bash
linkerd viz stat deploy/<deployment-name> -n <namespace> --time-window 1m
# For routes:
linkerd viz stat routes deploy/<deployment-name> -n <namespace> --time-window 1m
```

### 5. Edges: Show Service Dependencies

Lists the upstream and downstream services for a given service.

```bash
linkerd viz edges deploy/<deployment-name> -n <namespace>
```

### 6. ServiceProfile Validation

After creating or updating a ServiceProfile, you can (and should) validate it:

```bash
linkerd profile --validate <path-to-your-serviceprofile.yaml>
```

Then apply it:
```bash
kubectl apply -f <path-to-your-serviceprofile.yaml>
```
Ensure your service is annotated to use the profile, e.g., `linkerd.io/service-profile: <profile-namespace>/<profile-name>` on the Kubernetes Service object.

## Troubleshooting

- **No metrics for routes?** Ensure your ServiceProfile is correctly applied and the service is annotated to use it. Check `linkerd viz routes ...`.
- **Tap not showing requests?** Ensure the proxy is injected and the resource name/namespace is correct.
- **High latencies or low success rates?** Use `tap` to inspect failing requests and `logs` from the Linkerd proxy container (`linkerd-proxy`) in your pods.
  ```bash
  kubectl logs <pod-name> -n <namespace> -c linkerd-proxy
  ```

Refer to the official [Linkerd Documentation](https://linkerd.io/2/reference/cli/) for more commands and details. 