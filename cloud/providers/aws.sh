#!/bin/bash
get_latest_ami() {
    aws ec2 describe-images --owners 099720109477 \
        --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-noble-24.04-amd64-server-*" \
        --query 'Images | sort_by(@, &CreationDate)[-1].ImageId' --output text
}
create_instance() {
    local IT="$1" R="$2" NM="$3"
    AMI_ID=$(get_latest_ami)
    [ -z "$AMI_ID" ] && echo "🔴 No se pudo obtener AMI. Verifica credenciales AWS." && exit 1
    INSTANCE_ID=$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type "$IT" --region "$R" --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NM}]" --query 'Instances[0].InstanceId' --output text)
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$R"
    INSTANCE_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$R" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
    echo "$INSTANCE_ID" > "${CLOUD_DIR}/.instance_id" 2>/dev/null || true
    echo "✅ Instancia $INSTANCE_ID en $INSTANCE_IP"
}
wait_for_ssh() {
    for i in $(seq 30); do sleep 10; ssh -o StrictHostKeyChecking=no "ubuntu@$1" uptime 2>/dev/null && return 0; done; return 1
}
