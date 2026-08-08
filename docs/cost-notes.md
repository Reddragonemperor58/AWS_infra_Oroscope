# Cost Notes

| Service | Cost | Why |
|---|---|---|
| Secrets Manager | ~$0.40/month, prorated | Flat per-secret fee, no free tier tied to usage — the one guaranteed recurring cost in this stack |
NAT Gateway | $0 | Deliberately never provisioned — nothing inside the VPC ever needs outbound internet access. The database only responds to inbound Data API queries (stateful security group, confirmed no egress needed); the Lambda that needs S3 access is kept entirely outside the VPC, so it never required a NAT Gateway or a VPC endpoint to reach anything. |
| Aurora Serverless v2 | $0.14 for the entire first build day (creation + retries + live testing + 2 migrations) | Driven by active use resetting the 3600s auto-pause timer, not a steady-state rate. Once genuinely idle for an hour, drops to 0 ACU — near-$0 at rest |
| Data API | $0 so far | 1M requests/month free for account's first year; $0.20-0.70/million after. Not "free" as a feature — just cheap and within the allowance at this volume |
| Lambda | $0, expected to stay $0 at this scale | 1M requests + 400,000 GB-seconds/month, permanently free (not a 12-month trial) |
| CloudFront | $0 expected | ~1TB egress + 10M requests/month, permanently free |
| API Gateway | $0 expected | 1M requests/month free tier |
| Cognito | $0 expected | Free up to 10,000 monthly active users — nowhere close at this scale |

**Steady-state floor once idle:** ~$0.40-something/month (Secrets Manager), plus small
RDS blips every time the app is actively used. Everything else genuinely rounds to zero
at this traffic volume.