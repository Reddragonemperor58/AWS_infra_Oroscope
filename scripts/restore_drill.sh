#!/usr/bin/env bash
# Backup restore drill: proves a snapshot of the live database can be restored and read.
#
# 1. Takes a snapshot of the live cluster.
# 2. Restores it into a NEW throwaway cluster (scales to zero, so it costs almost nothing).
# 3. Counts rows in the main tables on both clusters and compares them.
# It never changes the live cluster. It does NOT delete anything: cleanup commands are printed
# at the end for you to run when you are happy.
#
# Run from the repo root in Git Bash:   bash scripts/restore_drill.sh
# To reuse a snapshot you already took (skips step 1):
#   REUSE_SNAPSHOT=oroscope-drill-202610231621 bash scripts/restore_drill.sh
set -euo pipefail

REGION="ap-south-2"
DB_NAME="oroscope_aurora"
LIVE_CLUSTER="oroscope-dev-aurora-cluster"
STAMP="$(date +%Y%m%d%H%M)"
SNAP="oroscope-drill-$STAMP"
DRILL_CLUSTER="oroscope-drill-restore-$STAMP"
DRILL_INSTANCE="oroscope-drill-instance-$STAMP"
TABLES="users patients diagnoses clinical_rules"

say() { printf '\n== %s\n' "$*"; }

say "Reading the live cluster's network settings"
SUBNET_GROUP=$(aws rds describe-db-clusters --region "$REGION" --db-cluster-identifier "$LIVE_CLUSTER" \
  --query 'DBClusters[0].DBSubnetGroup' --output text)
SG_IDS=$(aws rds describe-db-clusters --region "$REGION" --db-cluster-identifier "$LIVE_CLUSTER" \
  --query 'DBClusters[0].VpcSecurityGroups[].VpcSecurityGroupId' --output text)
LIVE_ARN=$(aws rds describe-db-clusters --region "$REGION" --db-cluster-identifier "$LIVE_CLUSTER" \
  --query 'DBClusters[0].DBClusterArn' --output text)
LIVE_SECRET=$(aws rds describe-db-clusters --region "$REGION" --db-cluster-identifier "$LIVE_CLUSTER" \
  --query 'DBClusters[0].MasterUserSecret.SecretArn' --output text)
echo "subnet group: $SUBNET_GROUP   security groups: $SG_IDS"

if [ -n "${REUSE_SNAPSHOT:-}" ]; then
  SNAP="$REUSE_SNAPSHOT"
  say "1/5 Reusing snapshot $SNAP"
else
  say "1/5 Taking snapshot $SNAP (about 1-3 minutes)"
  aws rds create-db-cluster-snapshot --region "$REGION" \
    --db-cluster-snapshot-identifier "$SNAP" --db-cluster-identifier "$LIVE_CLUSTER" >/dev/null
fi
aws rds wait db-cluster-snapshot-available --region "$REGION" --db-cluster-snapshot-identifier "$SNAP"

say "2/5 Restoring into a new cluster $DRILL_CLUSTER"
# shellcheck disable=SC2086
aws rds restore-db-cluster-from-snapshot --region "$REGION" \
  --db-cluster-identifier "$DRILL_CLUSTER" --snapshot-identifier "$SNAP" \
  --engine aurora-postgresql \
  --db-subnet-group-name "$SUBNET_GROUP" --vpc-security-group-ids $SG_IDS \
  --serverless-v2-scaling-configuration MinCapacity=0,MaxCapacity=1 >/dev/null
aws rds create-db-instance --region "$REGION" \
  --db-instance-identifier "$DRILL_INSTANCE" --db-cluster-identifier "$DRILL_CLUSTER" \
  --db-instance-class db.serverless --engine aurora-postgresql >/dev/null
echo "Waiting for the instance (about 5-10 minutes)..."
aws rds wait db-instance-available --region "$REGION" --db-instance-identifier "$DRILL_INSTANCE"

say "3/5 Switching on the Data API and a managed password for the restored cluster"
DRILL_ARN=$(aws rds describe-db-clusters --region "$REGION" --db-cluster-identifier "$DRILL_CLUSTER" \
  --query 'DBClusters[0].DBClusterArn' --output text)
aws rds enable-http-endpoint --region "$REGION" --resource-arn "$DRILL_ARN" >/dev/null
aws rds modify-db-cluster --region "$REGION" --db-cluster-identifier "$DRILL_CLUSTER" \
  --manage-master-user-password --apply-immediately >/dev/null
sleep 20
aws rds wait db-cluster-available --region "$REGION" --db-cluster-identifier "$DRILL_CLUSTER"
DRILL_SECRET=$(aws rds describe-db-clusters --region "$REGION" --db-cluster-identifier "$DRILL_CLUSTER" \
  --query 'DBClusters[0].MasterUserSecret.SecretArn' --output text)

count_rows() { # cluster-arn secret-arn table
  local out
  for attempt in 1 2 3 4 5 6 7 8; do
    if out=$(aws rds-data execute-statement --region "$REGION" --database "$DB_NAME" \
         --resource-arn "$1" --secret-arn "$2" --sql "SELECT count(*) FROM $3" \
         --query 'records[0][0].longValue' --output text 2>/dev/null); then
      echo "$out"; return 0
    fi
    sleep 10   # the database may still be waking up
  done
  echo "ERROR"; return 1
}

say "4/5 Comparing row counts"
printf '%-16s %10s %10s\n' table live restored
FAIL=0
for t in $TABLES; do
  L=$(count_rows "$LIVE_ARN" "$LIVE_SECRET" "$t") || true
  R=$(count_rows "$DRILL_ARN" "$DRILL_SECRET" "$t") || true
  if [ "$L" = "$R" ] && [ "$L" != "ERROR" ]; then M="match"; else M="MISMATCH"; FAIL=1; fi
  printf '%-16s %10s %10s   %s\n' "$t" "$L" "$R" "$M"
done

say "5/5 Result"
if [ "$FAIL" = 0 ]; then
  echo "RESTORE DRILL PASSED: the restored copy has the same row counts as the live database."
else
  echo "RESTORE DRILL FAILED: see the MISMATCH rows above. Do not delete anything yet; paste this output."
fi

cat <<CLEANUP

When you are done, remove the drill resources (these are the only things the drill created):

aws rds delete-db-instance --region $REGION --db-instance-identifier $DRILL_INSTANCE --skip-final-snapshot
aws rds wait db-instance-deleted --region $REGION --db-instance-identifier $DRILL_INSTANCE
aws rds delete-db-cluster --region $REGION --db-cluster-identifier $DRILL_CLUSTER --skip-final-snapshot
aws rds delete-db-cluster-snapshot --region $REGION --db-cluster-snapshot-identifier $SNAP
CLEANUP
