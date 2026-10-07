# 01 – IAM (Identity and Access Management) – Governance

## What is IAM?
IAM is the AWS service that answers two questions for every API call: **who is calling?** (authentication) and **are they allowed to do this to that resource?** (authorization). It is global (not per region), free, and every other AWS service checks with it before doing anything. Nothing in AWS happens without an IAM identity behind it, including Terraform runs and EC2 instances calling S3.

```text
Request  →  authenticate (user / role credentials)
         →  evaluate all applicable policies
         →  explicit Deny?  → DENY
         →  explicit Allow? → ALLOW
         →  otherwise       → DENY (default)
```

## Users
A **user** is a permanent identity for one person or one application: a name, optional console password, and up to two long-lived access keys (`AKIA…` + secret) for CLI/SDK/Terraform.

- Good for: a human who needs the console, a legacy app that cannot assume roles.
- Bad for: anything that can use a role instead. Long-lived keys leak (Git commits, laptops).
- The **root user** (the e-mail you signed up with) can do everything, including closing the account. Lock it with MFA and never use it day to day.

```bash
aws iam create-user --user-name gaurav
aws iam create-access-key --user-name gaurav      # returns AccessKeyId + SecretAccessKey once
```

## Groups
A **group** is a collection of users that share permissions. Policies are attached to the group; users inherit them. A user can be in several groups; groups cannot be nested and cannot be a principal in a policy.

```text
group: developers  ──policy──> AmazonS3ReadOnlyAccess, AmazonEC2ReadOnlyAccess
   ├── user: gaurav
   └── user: arnav
group: admins      ──policy──> AdministratorAccess
```

Rule: attach policies to groups, not to individual users, so permissions are managed in one place.

## Roles
A **role** is an identity with permissions but **no long-term credentials**. Something *assumes* the role and gets temporary credentials (15 min to 12 h) from STS. Who may assume it is defined by the role's **trust policy**.

Typical principals that assume roles:
- an EC2 instance (instance profile) → the app on it calls S3 without any keys on disk,
- a Lambda function, an EKS Pod (IRSA), an ECS task,
- a user from another AWS account (cross-account access),
- GitHub Actions through OIDC (no secrets stored in the repo),
- a human switching into an admin role only when needed.

```json
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
                  "Principal": { "Service": "ec2.amazonaws.com" },
                  "Action": "sts:AssumeRole" }] }
```

## Policies
A **policy** is a JSON document that lists what is allowed or denied. Types:

| Type | Attached to | Notes |
|---|---|---|
| AWS managed | users/groups/roles | maintained by AWS, e.g. `AmazonS3ReadOnlyAccess` |
| Customer managed | users/groups/roles | your own reusable policies |
| Inline | one identity | dies with the identity; avoid except for tight one-offs |
| Resource-based | the resource (S3 bucket policy, SQS, KMS) | has a `Principal` field; enables cross-account access |
| Permission boundary | user/role | the *maximum* permissions an identity can ever get |
| SCP (Organizations) | account/OU | guardrail across whole accounts |

Anatomy of a statement:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "ReadOneBucket",
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:ListBucket"],
    "Resource": ["arn:aws:s3:::gaurav-session18-tf-demo",
                 "arn:aws:s3:::gaurav-session18-tf-demo/*"],
    "Condition": { "Bool": { "aws:SecureTransport": "true" } }
  }]
}
```

## Permissions
How a request is evaluated:
1. Everything is **denied by default**.
2. An **explicit Deny** anywhere (identity policy, resource policy, SCP, boundary) wins over any Allow.
3. Otherwise the request needs an **Allow** from an identity policy *and* must not be cut off by an SCP or a permission boundary. For cross-account access, both the identity's account and the resource policy must allow it.
4. `Condition` keys refine it: source IP, MFA present, tags, time, TLS.

`aws sts get-caller-identity` shows who you are; the IAM Policy Simulator and CloudTrail show why something was denied.

## Least privilege
Give every identity only the actions, on only the resources, that its job needs, for only as long as it needs them.

- Start from zero and add; do not start from `AdministratorAccess` and subtract.
- Scope `Resource` to ARNs, not `"*"`, wherever the service supports it.
- Prefer read-only managed policies for humans who only look.
- Use IAM Access Analyzer "generate policy" from CloudTrail to see what an app really used, then tighten.
- Review and remove unused users, keys and roles (credential report, last-used columns).

## IAM best practices
1. Lock the **root user**: MFA, no access keys, use it only for billing/account tasks.
2. **MFA** for every human user.
3. **Roles instead of access keys** for EC2, Lambda, EKS, CI/CD (GitHub OIDC).
4. **Groups** for humans; policies on groups.
5. **Rotate** any long-lived keys regularly; never commit them (this is what the Session 17 secret scan is for).
6. **Permission boundaries / SCPs** to stop privilege escalation in multi-team accounts.
7. **CloudTrail on** in every region; alert on root usage and `iam:*` changes.
8. Use **conditions** (`aws:MultiFactorAuthPresent`, `aws:SourceIp`, `aws:PrincipalTag`).
9. Separate accounts per environment (dev / staging / prod) under AWS Organizations.
10. Prefer **IAM Identity Center** (SSO) over individual IAM users for people.

## Common use cases
- **Terraform / CLI on a laptop**: a user in a `terraform` group with scoped permissions, or better, `aws sso login` and a role.
- **EC2 web server reading from S3**: instance profile role with `s3:GetObject` on one bucket; no keys on the box.
- **GitHub Actions deploying to EKS**: OIDC trust policy on a role; the workflow calls `aws-actions/configure-aws-credentials` and gets 1-hour credentials.
- **Cross-account**: a prod bucket policy that allows `arn:aws:iam::<dev-account>:role/reader` to read logs.
- **Break-glass admin**: an admin role that requires MFA to assume; normal work uses a less privileged role.
- **Service-to-service**: Lambda role allowed to `dynamodb:PutItem` on one table only.

## Terraform snippet (what the S3 demo would need)
```hcl
resource "aws_iam_role" "ec2_s3_reader" {
  name = "session18-ec2-s3-reader"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole",
                   Principal = { Service = "ec2.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "read_demo_bucket" {
  role = aws_iam_role.ec2_s3_reader.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["s3:GetObject", "s3:ListBucket"],
                   Resource = [aws_s3_bucket.devops553.arn, "${aws_s3_bucket.devops553.arn}/*"] }]
  })
}
```
