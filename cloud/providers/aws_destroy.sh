destroy_instance() {
    local INSTANCE_ID="$1"
    aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"
    aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
    echo "✅ Instancia $INSTANCE_ID terminada"
}
