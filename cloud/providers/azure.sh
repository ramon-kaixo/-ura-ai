#!/bin/bash
create_instance() {
    local IT="${1:-Standard_D2s_v3}" R="${2:-eastus}" NM="${3:-ura-cloud}"
    az vm create --resource-group ura-rg --name "$NM" --image Ubuntu2204 --size "$IT" --location "$R" --generate-ssh-keys 2>/dev/null
    INSTANCE_IP=$(az vm show --name "$NM" --resource-group ura-rg --query publicIps -o tsv 2>/dev/null)
    echo "$INSTANCE_IP" > "${CLOUD_DIR}/.instance_id"
    echo "✅ VM Azure: $INSTANCE_IP"
}
destroy_instance() { az vm delete --name "$1" --resource-group ura-rg --yes 2>/dev/null; echo "✅ VM Azure $1 destruida"; }
