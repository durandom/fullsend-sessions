#!/usr/bin/env bash
set -euo pipefail

PROFILE="${AWS_PROFILE:-rhdh-qe}"
BUCKET="fullsend-sessions"
REGION="eu-north-1"
POLICY_NAME="fullsend-sessions-read-upload"
USER_NAME="fullsend-sessions-writer"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Using AWS profile: $PROFILE"
echo "==> Verifying identity..."
aws sts get-caller-identity --profile "$PROFILE"

echo ""
echo "==> Creating S3 bucket: $BUCKET (region: $REGION)..."
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" \
  --profile "$PROFILE" 2>&1 || echo "    (bucket may already exist)"

echo ""
echo "==> Creating IAM policy: $POLICY_NAME..."
POLICY_ARN=$(aws iam create-policy \
  --policy-name "$POLICY_NAME" \
  --policy-document "file://${SCRIPT_DIR}/s3-policy.json" \
  --profile "$PROFILE" \
  --query 'Policy.Arn' \
  --output text 2>&1) || {
    echo "    Policy may already exist, looking it up..."
    ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query 'Account' --output text)
    POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
  }
echo "    Policy ARN: $POLICY_ARN"

echo ""
echo "==> Creating IAM user: $USER_NAME..."
aws iam create-user \
  --user-name "$USER_NAME" \
  --profile "$PROFILE" 2>&1 || echo "    (user may already exist)"

echo ""
echo "==> Attaching policy to user..."
aws iam attach-user-policy \
  --user-name "$USER_NAME" \
  --policy-arn "$POLICY_ARN" \
  --profile "$PROFILE"

echo ""
echo "==> Creating access key..."
aws iam create-access-key \
  --user-name "$USER_NAME" \
  --profile "$PROFILE" \
  --output json | tee /dev/stderr | python3 -c "
import sys, json
key = json.load(sys.stdin)['AccessKey']
print()
print('=== SAVE THESE CREDENTIALS ===')
print(f'AWS_ACCESS_KEY_ID={key[\"AccessKeyId\"]}')
print(f'AWS_SECRET_ACCESS_KEY={key[\"SecretAccessKey\"]}')
print('S3_BUCKET=$BUCKET')
print('S3_REGION=$REGION')
print('================================')
"

echo ""
echo "==> Verifying: uploading test file..."
echo "s3 setup test $(date -u +%Y-%m-%dT%H:%M:%SZ)" > /tmp/s3-test.txt
aws s3 cp /tmp/s3-test.txt "s3://${BUCKET}/test.txt" --profile "$PROFILE"
aws s3 ls "s3://${BUCKET}/" --profile "$PROFILE"
rm -f /tmp/s3-test.txt

echo ""
echo "Done! Share the credentials above with team members."
