# ADR 0001: Infrastructure-as-Code Tool Selection

## Context
Building all AWS infrastructure for Oroscope requires an IaC tool rather than manual console configuration, to keep infrastructure reproducible, reviewable, and free of undocumented manual changes.

## Options Considered
- **Terraform** — HCL-based, multi-cloud, provider-agnostic.
- **AWS CDK** — infrastructure defined in a general-purpose language, AWS-only, compiles to CloudFormation.

## Decision
**Terraform.**

## Reasoning
Terraform isn't tied to AWS specifically, keeping the underlying knowledge portable rather than locked to one vendor, and it appears far more broadly across job postings than CDK, which is AWS-only. Writing raw Terraform resources instead of reaching for a pre-built module also forces direct visibility into each AWS resource's actual shape and default behavior, rather than trusting an abstraction to decide on our behalf.

Validated concretely during the network module build: we nearly used the popular community module `terraform-aws-modules/vpc/aws`, which by default sets `enable_nat_gateway = true`. Used as-is, it would have silently reintroduced the exact ~$33-45/month NAT Gateway cost this project deliberately architected around avoiding, with nothing in the resulting code looking obviously wrong. Writing the VPC, subnets, DB subnet group, and security group as raw resources made that omission a deliberate, visible choice instead of an invisible default.

## Trade-offs Accepted
Raw resource authorship has a steeper immediate learning curve than a module or CDK construct. Accepted deliberately, in exchange for transferable understanding of what's actually being provisioned — module adoption remains a legitimate future option once the underlying resources are well understood.