# Kubernetes Deployment for Demo Command Center Agent

This directory contains Kubernetes manifests to deploy the Demo Command Center Agent application to a Kubernetes cluster.

## Files

- `k8s-deployment.yaml`: Complete set of Kubernetes manifests for deployment

## Contents

The `k8s-deployment.yaml` file includes:

1. **Namespace**: `demo-command-center`
2. **ServiceAccount**: For pod identity
3. **Role & RoleBinding**: Basic Kubernetes API access (adjust as needed)
4. **ConfigMap**: Non-sensitive configuration parameters
5. **Secret**: Placeholder for sensitive configuration (replace with actual values or use ExternalSecrets)
6. **Deployments**:
   - `demo-command-center-api`: The main API service
   - `demo-command-center-worker`: Worker processes for SQS consumption
7. **Services**:
   - `demo-command-center-api`: ClusterIP service for API access
8. **Ingress** (commented out): Example Ingress configuration (uncomment and customize)
9. **CronJobs**: Scheduled jobs replacing AWS EventBridge Scheduler:
   - `model-evaluation`: Daily at 2:00 AM UTC
   - `payment-reconciliation`: Every 15 minutes
   - `retention-cleanup`: Daily at 2:30 AM UTC
10. **HorizontalPodAutoscaler**: For API scaling based on CPU utilization
11. **PodDisruptionBudgets**: For both API and worker deployments
12. **Notes**: Guidance for production deployment considerations

## Prerequisites

Before deploying, ensure you have:

1. A running Kubernetes cluster (EKS, GKE, AKS, etc.)
2. `kubectl` configured to connect to your cluster
3. External dependencies provisioned and accessible:
   - Database (PostgreSQL/Aurora)
   - Redis (or ElastiCache)
   - Object storage (S3 or compatible)
   - Message queue (SQS or compatible)
   - Secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
   - Email service (SES or compatible)
4. Required controllers/operators installed:
   - Metrics Server (for HPA)
   - Ingress Controller (NGINX, ALB, etc.) - if using Ingress
   - Optional: KEDA (for queue-based worker autoscaling)
   - Optional: ExternalSecrets or similar (for syncing with AWS Secrets Manager)
   - Optional: Cert-manager (for TLS certificates)

## Usage

### 1. Update Image References

Replace the placeholder image in the manifests:
```
REPLACE_WITH_ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/demo-command-center:SHA256_DIGEST
```

With your actual ECR image URI containing the SHA256 digest (for immutability).

### 2. Configure Secrets

**Option A: Manual Secrets (for testing)**
```bash
kubectl create secret generic demo-command-center-secrets \
  --namespace=demo-command-center \
  --from-literal=DATABASE_URL="your-db-url" \
  --from-literal=REDIS_URL="your-redis-url" \
  --from-literal=FIELD_ENCRYPTION_KEY="your-encryption-key" \
  --from-literal=AUDIT_HASH_KEY="your-hash-key" \
  --from-literal=INTERNAL_HMAC_KEY_GRANTS='{"key-id":{"secret":"secret-value","source":"source","scopes":["read","write"]}}' \
  --from-literal=LEAD_INTAKE_SHARED_SECRET="your-lead-intake-secret" \
  --from-literal=ONBOARDING_AGENT_SHARED_SECRET="your-onboarding-agent-secret" \
  --from-literal=NXTUTORS_WEBSITE_SHARED_SECRET="your-website-shared-secret" \
  --from-literal=META_WHATSAPP_ACCESS_TOKEN="your-whatsapp-token" \
  --from-literal=META_WHATSAPP_APP_SECRET="your-app-secret" \
  --from-literal=META_WHATSAPP_VERIFY_TOKEN="your-verify-token" \
  --from-literal=CASHFREE_APP_ID="your-cashfree-app-id" \
  --from-literal=CASHFREE_SECRET_KEY="your-cashfree-secret-key" \
  --from-literal=OPENAI_API_KEY="your-openai-api-key"
```

**Option B: ExternalSecrets Operator (recommended for production)**
1. Install ExternalSecrets Operator in your cluster
2. Create a SecretStore or ClusterSecretStore pointing to your AWS Secrets Manager
3. Create ExternalSecret resources that match the secret keys in the manifest
4. Remove the `stringData` section from the Secret manifest and let ExternalSecrets populate it

### 3. Deploy

```bash
kubectl apply -f k8s-deployment.yaml
```

### 4. Verify Deployment

```bash
# Check all resources
kubectl get all -n demo-command-center

# Check specific resources
kubectl get deploy -n demo-command-center
kubectl get pods -n demo-command-center
kubectl get svc -n demo-command-center
kubectl get hpa -n demo-command-center
kubectl get cronjob -n demo-command-center
```

### 5. Access the Application

If you uncommented and configured the Ingress section:
- Configure DNS to point to your ingress controller
- Access via the hostname you specified

Otherwise, access the service within the cluster or port-forward for testing:
```bash
kubectl port-forward svc/demo-command-center-api 8080:80 -n demo-command-center
# Then access at http://localhost:8080
```

## Customization

### Resource Adjustments
Adjust resource requests/limits in the deployments based on your actual usage profiles. The current values match the ECS task definitions from the Terraform configuration:
- CPU: 500m request, 1000m limit (0.5-1 vCPU)
- Memory: 1Gi request, 2Gi limit

### Scaling
- API HorizontalPodAutoscaler scales based on CPU utilization (target 60%)
- For worker scaling based on SQS queue depth, consider using KEDA (see commented example in worker deployment)
- Manual scaling: `kubectl scale deployment demo-command-center-worker --replicas=5 -n demo-command-center`

### Environment Specific Configuration
Override ConfigMap values per environment using:
- Kustomize overlays
- Helm values files
- Customizing the ConfigMap per namespace/environment

## Maintenance

### Updating Images
Update the image tag and roll out:
```bash
kubectl set image deployment/demo-command-center-api api=NEW_IMAGE_URL -n demo-command-center
kubectl set image deployment/demo-command-center-worker worker=NEW_IMAGE_URL -n demo-command-center
```

### Database Migrations
Run migrations as needed:
```bash
kubectl create job --from=cronjob/model-evaluation migrate-db-$(( $(date +%s) )) \
  --namespace=demo-command-center \
  --image=YOUR_IMAGE_URL \
  -- python -m alembic upgrade head
```

### Viewing Logs
```bash
kubectl logs -f deployment/demo-command-center-api -n demo-command-center
kubectl logs -f deployment/demo-command-center-worker -n demo-command-center
```

## Troubleshooting

### CrashLoopBackOff
Check logs:
```bash
kubectl logs <pod-name> -n demo-command-center
```

### ImagePullBackOff
Verify image URL and pull secrets:
```bash
kubectl describe pod <pod-name> -n demo-command-center
```

### Service Unavailable
Check endpoints and readiness probes:
```bash
kubectl get endpoints -n demo-command-center
kubectl describe svc demo-command-center-api -n demo-command-center
```

## Security Considerations

1. **Images**: Use trusted base images, scan for vulnerabilities
2. **Network**: Consider Network Policies to restrict traffic
3. **Secrets**: Never commit actual secrets; use secret management tools
4. **Permissions**: Run as non-root user (configured as UID 10001)
5. **Filesystem**: Read-only root filesystem where possible
6. **Capabilities**: Drop all Linux capabilities
7. **Resource Limits**: Set appropriate CPU/memory limits to prevent resource starvation
8. **Audit**: Enable audit logging at the API server level