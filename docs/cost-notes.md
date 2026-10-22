# Cost Notes

| Service | Cost | Why |
|---|---|---|
| Secrets Manager | ~$0.40/month, prorated | Flat per-secret fee, no free tier tied to usage — the one guaranteed recurring cost in this stack |
| NAT Gateway | $0 | Deliberately never provisioned — nothing inside the VPC ever needs outbound internet access. The database only responds to inbound Data API queries (stateful security group, confirmed no egress needed); the Lambda that needs S3 access is kept entirely outside the VPC, so it never required a NAT Gateway or a VPC endpoint to reach anything. Would have been ~$33-45/month baseline just for existing, plus per-GB processing — avoided by keeping the Lambda outside the VPC and using the Data API |
| Aurora Serverless v2 | $0.14 for the entire first build day (creation + retries + live testing + 2 migrations) | Driven by active use resetting the 3600s auto-pause timer, not a steady-state rate. Once genuinely idle for an hour, drops to 0 ACU — near-$0 at rest |
| Data API | $0 so far | 1M requests/month free for account's first year; $0.20-0.70/million after. Not "free" as a feature — just cheap and within the allowance at this volume |
| Lambda | $0, expected to stay $0 at this scale | 1M requests + 400,000 GB-seconds/month, permanently free (not a 12-month trial) |
| CloudFront | $0 expected | Provisioned (PriceClass_200, default certificate, caching disabled). ~1TB egress + 10M requests/month, permanently free |
| S3 frontend bucket | ~$0 | A few hundred KB of static files |
| API Gateway | $0 expected | 1M requests/month free tier |
| Cognito | $0 expected | Free up to 10,000 monthly active users — nowhere close at this scale |

**Steady-state floor once idle:** ~$0.40-something/month (Secrets Manager), plus small
RDS blips every time the app is actively used. Everything else genuinely rounds to zero
at this traffic volume.

## Stage 4a additions (optical analysis) - approximate, verify on the AWS pricing page for ap-south-2

| Item | Cost driver | Estimate |
|---|---|---|
| S3 images bucket | Storage + requests | Fractions of a cent per GB-month; a pair of photos is ~2-10 MB. Objects expire after **30 days** (placeholder retention - confirm with the clinic) |
| Lambda (1024 MB, 30 s timeout) | GB-seconds per invocation | ~4 s for a 12 MP pair => ~4 GB-s (~$0.0001/analysis); the monthly free tier (400,000 GB-s) covers thousands of analyses |
| API Gateway HTTP API | Per request | Negligible at prototype volume |
| Presigned URL generation | No separate charge | Done inside the Lambda |

**Costs avoided by design:** no ECR repository, no second Lambda, no container image storage, no NAT gateway, no SageMaker endpoint (DL skipped). The memory increase from 256 MB to 1024 MB only costs money while a request runs.

**Still the dominant cost:** Aurora Serverless v2. Scale-to-zero (min 0 ACU, pause after 3600 s) means an idle database costs only storage; the first request after a pause returns 503 while it resumes.

**Frontend (ADR 0013):** S3 + CloudFront stay inside the permanent free tiers at prototype volume. Caching is disabled so a deploy shows immediately; this only costs requests to the S3 origin, which are negligible here. Revisit if traffic grows (enable caching + invalidate on deploy).

**Recommended guard:** an AWS Budgets alert (e.g. $5/month) so a mistake or a left-on resource cannot surprise you.

**Cost risks to watch:** the future DL endpoint (a real-time SageMaker endpoint bills continuously; use Serverless Inference or a container Lambda instead), and the 6 MB / 10 MB payload limits pushing anyone toward a bigger architecture than needed.