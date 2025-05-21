# Runbook: Daily Random Pod Kill Chaos Experiment

**Objective:** To proactively identify weaknesses and verify the resilience of the `valuation`, `payouts`, and `offers` applications by randomly terminating their pods and observing system behavior, specifically SLO adherence via Prometheus alerts.

**Target Services:**
- `valuation` (pods labeled `app: valuation`)
- `payouts` (pods labeled `app: payouts`)
- `offers` (pods labeled `app: offers`)

**Chaos Experiment Details:**
- **Kind:** `PodChaos` (via Litmus `ChaosEngine`)
- **Action:** `pod-delete` (randomly kills selected pods)
- **Frequency:** Daily at 03:00 UTC (scheduled via `CronWorkflow`)
- **Duration:** 5 minutes (`TOTAL_CHAOS_DURATION: '300'`)
- **Impact:** 50% of the matching pods will be targeted in each iteration (`PODS_AFFECTED_PERC: '50'`).
- **Interval:** New pod kill attempts every 60 seconds (`CHAOS_INTERVAL: '60'`).
- **Target Namespace:** `your-apps-namespace` (Update this to your actual application namespace).

**Detection & Verification:**
- **Primary Check:** Prometheus Probe within the `ChaosEngine`.
  - **Probe Type:** `promProbe`
  - **Prometheus Endpoint:** `http://prometheus-k8s.monitoring.svc:9090` (Adjust if your endpoint differs).
  - **Query:** `sum(ALERTS{alertname='MySLOBreachAlert', alertstate='firing'}) > 0`
    - This query checks if the `MySLOBreachAlert` (you must define this alert in Prometheus) is actively firing.
    - **Success Condition:** The probe expects this query to return `1` (meaning the alert *is* firing). This setup implies the experiment *expects* an SLO breach to test the alerting mechanism itself.
    - **To test resilience (i.e., alert *should not* fire):** Change `comparator.value` to `"0"` in the `ChaosEngine`'s `promProbe` definition.
  - **Mode:** `EOT` (End Of Test) - The check is performed after the chaos duration.

**Associated Kubernetes Resources:**
1.  **`ChaosEngine`:** `infra/helm/litmus/chaos_kill_random.yaml` (defines the experiment itself).
2.  **`CronWorkflow`:** (Example below, to be created separately) Schedules the `ChaosEngine` execution.

---

## Pre-requisites

1.  **Litmus Chaos Installed:** Ensure Litmus (v2.0.0+) is installed in your Kubernetes cluster (typically in `litmus` namespace).
2.  **Chaos Hub Experiments:** The `pod-delete` experiment (from `generic` hub or your custom hub) must be available.
3.  **`ChaosServiceAccount`:** A service account (e.g., `litmus-admin`) with permissions to:
    - Get, create, patch, delete `ChaosEngine`, `ChaosResult`, `ChaosExperiment` resources in the Litmus namespace.
    - Get, list, delete pods in the target application namespace (`your-apps-namespace`).
    - Potentially other permissions depending on the probes used.
4.  **Target Applications Labeled:** Pods for `valuation`, `payouts`, and `offers` services must have the label `app` correctly set (e.g., `app: valuation`).
5.  **Prometheus Setup:** Prometheus must be running and scraping metrics from your applications.
6.  **SLO Alert (`MySLOBreachAlert`):** An alert named `MySLOBreachAlert` (or your chosen name, update YAML accordingly) must be configured in Prometheus. This alert should fire if the SLOs for the target services are breached.

---

## Scheduling with CronWorkflow

To run this chaos experiment daily at 03:00 UTC, you'll need to create a `CronWorkflow` resource. This resource uses Argo Workflows (which Litmus leverages for scheduling).

**Example `CronWorkflow` YAML (`infra/helm/litmus/cron_chaos_random_pod.yaml` - create this file):**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: CronWorkflow
metadata:
  name: daily-random-pod-kill-cron
  namespace: litmus # Or your Litmus control plane namespace
spec:
  schedule: "0 3 * * *" # 03:00 UTC daily
  timezone: "UTC" # Optional, defaults to UTC if not specified
  concurrencyPolicy: "Allow" # Or "Forbid" or "Replace"
  startingDeadlineSeconds: 0 # Optional
  successfulJobsHistoryLimit: 3 # Optional
  failedJobsHistoryLimit: 3 # Optional
  workflowSpec:
    entrypoint: run-chaosengine
    serviceAccountName: argo-workflow # Or your Argo Workflow service account if different
                                     # This SA needs permission to create ChaosEngines
    templates:
    - name: run-chaosengine
      steps:
      - - name: create-chaos-engine
          template: chaosengine-creation

    - name: chaosengine-creation
      # This step submits the ChaosEngine resource defined in chaos_kill_random.yaml
      # The ChaosEngine could be embedded here directly or fetched from a URL/ConfigMap.
      # For simplicity, this example assumes you apply the ChaosEngine YAML separately
      # and the CronWorkflow acts as a trigger for an engine that might be pre-existing
      # or managed by another process that ensures it's active for the run.
      # A more robust approach is to have the workflow directly create the ChaosEngine:
      resource:
        action: create # or apply
        manifest: |-
          apiVersion: litmuschaos.io/v1alpha1
          kind: ChaosEngine
          metadata:
            # Generate a unique name for each run to avoid conflicts if previous runs are not cleaned up.
            # Use {{workflow.name}} which Argo injects.
            name: random-pod-kill-{{workflow.name}}
            namespace: litmus # Namespace where ChaosEngines are managed
          spec:
            engineState: 'active'
            chaosServiceAccount: litmus-admin # SA for chaos execution
            appinfo:
              appns: 'your-apps-namespace' # Target app namespace - IMPORTANT: CHANGE THIS
              applabel: 'app in (valuation, payouts, offers)'
              appkind: 'deployment'
            experiments:
            - name: pod-delete-random-apps
              spec:
                components:
                  env:
                  - name: TOTAL_CHAOS_DURATION
                    value: '300'
                  - name: CHAOS_INTERVAL
                    value: '60'
                  - name: PODS_AFFECTED_PERC
                    value: '50'
                  - name: APP_NAMESPACE
                    value: 'your-apps-namespace' # Target app namespace - IMPORTANT: CHANGE THIS
                  - name: LABEL_SELECTOR
                    value: "app in (valuation,payouts,offers)"
                  probe:
                  - name: "check-slo-alert-status"
                    type: "promProbe"
                    promProbe/inputs:
                      endpoint: "http://prometheus-k8s.monitoring.svc:9090" # Prometheus endpoint
                      query: "sum(ALERTS{alertname='MySLOBreachAlert', alertstate='firing'}) > 0"
                      comparator:
                        type: "=="
                        value: "1" # Expects alert to fire. Change to "0" if alert should NOT fire.
                    mode: "EOT"
                    runProperties:
                      probeTimeout: 60
                      interval: 20
                      retry: 3
                      initialDelaySeconds: 30
            jobCleanUpPolicy: 'delete'
```

**To apply the `CronWorkflow`:**
```bash
kubectl apply -f infra/helm/litmus/cron_chaos_random_pod.yaml -n litmus
```
**Note:** The `serviceAccountName` for the `workflowSpec` in `CronWorkflow` needs permissions to create `ChaosEngine` resources.

---

## Execution and Monitoring

1.  **Automatic Execution:** The `CronWorkflow` will trigger the `ChaosEngine` creation at 03:00 UTC daily.
2.  **View Workflow Status (Argo UI or CLI):**
    ```bash
    kubectl get wf -n litmus # List workflows
    kubectl get cronwf -n litmus # List cronworkflows
    # argo list -n litmus (if Argo CLI is installed)
    ```
3.  **View Chaos Results:**
    - Check `ChaosResult` custom resources: `kubectl get chaosresult -n your-apps-namespace -l chaosengine=random-pod-kill-engine` (or the generated name like `random-pod-kill-{{workflow.name}}`).
    - Examine logs of the chaos-runner pod and experiment pods created by Litmus in the application namespace (`your-apps-namespace`).
4.  **Prometheus Verification:**
    - During and after the experiment, monitor Prometheus for the `MySLOBreachAlert`.
    - The `ChaosResult` will indicate if the `promProbe` succeeded or failed based on its criteria.

---

## Interpreting Results

-   **Probe Success (`comparator.value: "1"` for alert firing):**
    -   If the `promProbe` succeeds, it means `MySLOBreachAlert` *was firing* at the end of the test. This confirms your alerting mechanism works when pods are killed.
-   **Probe Failure (`comparator.value: "1"` for alert firing):**
    -   If the `promProbe` fails, it means `MySLOBreachAlert` *was not firing*. This could mean:
        -   Your system is resilient enough that killing these pods did not cause an SLO breach.
        -   Your SLO alert `MySLOBreachAlert` is not configured correctly or its thresholds are too high.
        -   The chaos duration/intensity was insufficient to trigger the alert.
-   **If testing for resilience (alert *should not* fire, `comparator.value: "0"`):**
    -   **Probe Success:** `MySLOBreachAlert` was *not* firing. This is the desired outcome, indicating resilience.
    -   **Probe Failure:** `MySLOBreachAlert` *was* firing. This indicates an SLO breach and a potential issue with service resilience.

---

## Rollback / Stop Experiment

-   **Stop `CronWorkflow`:**
    ```bash
    kubectl delete cronworkflow daily-random-pod-kill-cron -n litmus
    ```
-   **Abort an Active `ChaosEngine` Run:**
    - Set `engineState` to `stop`: `kubectl patch chaosengine <engine-name> -n litmus --type=json -p='[{"op": "replace", "path": "/spec/engineState", "value":"stop"}]'`
    - Or delete the `ChaosEngine` CR: `kubectl delete chaosengine <engine-name> -n litmus`
      (This will also delete associated chaos pods if `jobCleanUpPolicy` is `delete`.)

---

**IMPORTANT:**
-   **Thoroughly test this in a non-production environment first.**
-   Adjust `PODS_AFFECTED_PERC`, `TOTAL_CHAOS_DURATION`, and `CHAOS_INTERVAL` based on your risk tolerance and application characteristics.
-   Ensure your Prometheus query in `promProbe` is accurate and targets the specific SLO alert you are interested in.
-   Update placeholders like `your-apps-namespace` and Prometheus endpoints/alert names. 