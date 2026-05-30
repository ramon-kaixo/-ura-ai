#!/bin/bash
create_instance() {
    local IT="${1:-e2-medium}" R="${2:-us-central1}" NM="${3:-ura-cloud}"
    gcloud compute instances create "$NM" --machine-type="$IT" --zone="$R" --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud 2>/dev/null
    INSTANCE_IP=$(gcloud compute instances describe "$NM" --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null)
    echo "$INSTANCE_IP" > "${CLOUD_DIR}/.instance_id"
    echo "✅ VM GCP: $INSTANCE_IP"
}
destroy_instance() { gcloud compute instances delete "$1" --quiet 2>/dev/null; echo "✅ VM GCP $1 destruida"; }
