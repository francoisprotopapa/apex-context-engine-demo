#!/usr/bin/env bash
# Azure side of the LLM observability layer: what Elastic needs to read Azure OpenAI metrics, logs and costs.
# Run after `az login`. Nothing is printed except resource names; secrets go to demo/.env.azure-monitor (git-ignored, chmod 600).
#
#   RG=rg-apex-demo AOAI=apex-demo-aoai-xxxxx LOC=germanywestcentral ./azure/setup_monitoring.sh
#
# Creates: service principal (Monitoring Reader on the resource group + Cost Management Reader on the subscription),
#          Event Hub namespace + hub, storage account + container (checkpoints), diagnostic setting on the Azure OpenAI
#          resource (logs + metrics -> Event Hub), Elastic Agent in Azure Container Instances (reads the Event Hub).
# Costs: Event Hub Standard and the container are billed hourly (a few EUR per month): delete everything after the event.
set -euo pipefail
export PYTHONWARNINGS=ignore
RG="${RG:?set RG}"; AOAI="${AOAI:?set AOAI (Azure OpenAI resource name)}"; LOC="${LOC:-germanywestcentral}"
SFX="$(LC_ALL=C tr -dc a-z0-9 </dev/urandom | head -c5)"
EHNS="apexdemoeh$SFX"; HUB="azure-openai-logs"; SA="apexdemosa$SFX"; CONTAINER="elastic-checkpoints"
OUT="$(cd "$(dirname "$0")/.." && pwd)/demo/.env.azure-monitor"
SUB="$(az account show --query id -o tsv)"; TEN="$(az account show --query tenantId -o tsv)"

az provider register -n Microsoft.EventHub --wait
az provider register -n Microsoft.ContainerInstance --wait

echo "== Event Hub + storage"
az eventhubs namespace create -g "$RG" -n "$EHNS" -l "$LOC" --sku Standard --capacity 1 -o none
az eventhubs eventhub create -g "$RG" --namespace-name "$EHNS" -n "$HUB" --partition-count 2 --cleanup-policy Delete --retention-time-in-hours 24 -o none
az storage account create -g "$RG" -n "$SA" -l "$LOC" --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false -o none
SAKEY="$(az storage account keys list -g "$RG" -n "$SA" --query '[0].value' -o tsv)"
az storage container create --account-name "$SA" --account-key "$SAKEY" -n "$CONTAINER" -o none
EHCS="$(az eventhubs namespace authorization-rule keys list -g "$RG" --namespace-name "$EHNS" --name RootManageSharedAccessKey --query primaryConnectionString -o tsv)"

echo "== diagnostic setting on the Azure OpenAI resource (logs + metrics -> Event Hub)"
RES="$(az cognitiveservices account show -n "$AOAI" -g "$RG" --query id -o tsv)"
RULE="$(az eventhubs namespace authorization-rule show -g "$RG" --namespace-name "$EHNS" -n RootManageSharedAccessKey --query id -o tsv)"
az monitor diagnostic-settings create --name elastic-eventhub --resource "$RES" --event-hub-rule "$RULE" --event-hub "$HUB" \
  --logs '[{"category":"Audit","enabled":true},{"category":"RequestResponse","enabled":true},{"category":"AzureOpenAIRequestUsage","enabled":true},{"category":"Trace","enabled":true}]' \
  --metrics '[{"category":"AllMetrics","enabled":true}]' -o none

echo "== service principal (Monitoring Reader on the RG, Cost Management Reader on the subscription)"
SP="$(az ad sp create-for-rbac --name apex-elastic-monitoring --role 'Monitoring Reader' --scopes "/subscriptions/$SUB/resourceGroups/$RG" --years 1 -o json)"
CID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["appId"])' "$SP")"
CSEC="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["password"])' "$SP")"
az role assignment create --assignee "$CID" --role 'Cost Management Reader' --scope "/subscriptions/$SUB" -o none

umask 077
cat > "$OUT" <<EOF
AZURE_TENANT_ID=$TEN
AZURE_SUBSCRIPTION_ID=$SUB
AZURE_CLIENT_ID=$CID
AZURE_CLIENT_SECRET=$CSEC
RESOURCE_GROUP=$RG
EVENTHUB_NAMESPACE=$EHNS.servicebus.windows.net
EVENTHUB_NAME=$HUB
EVENTHUB_CONNECTION_STRING=$EHCS
STORAGE_ACCOUNT=$SA
STORAGE_ACCOUNT_KEY=$SAKEY
STORAGE_CONTAINER=$CONTAINER
EOF
echo "secrets written to $OUT (git-ignored)"

cat <<'EOF'

Next:
  1) python3 tools/provision_obs.py --env demo/.env.obs --azure-env demo/.env.azure-monitor integrations
     -> creates the integrations and writes ./.enrollment_token (Fleet agent policy for the logs)
  2) start the Elastic Agent that reads the Event Hub (replace FLEET_URL with the URL printed in step 1):
       az container create -g "$RG" -n apex-elastic-agent-logs -l "$LOC" --os-type Linux --cpu 1 --memory 2 --restart-policy Always \
         --image docker.elastic.co/elastic-agent/elastic-agent:9.5.5 \
         --environment-variables FLEET_ENROLL=1 FLEET_URL=<fleet url> \
         --secure-environment-variables FLEET_ENROLLMENT_TOKEN="$(cat .enrollment_token)"
  3) wait ~10 min (Azure Monitor delay) and open the dashboards.
Cleanup after the event:  az group delete -n "$RG"   and   az ad sp delete --id <AZURE_CLIENT_ID>
EOF
