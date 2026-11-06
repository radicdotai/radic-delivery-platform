variable "project_id" { type = string }
variable "pool_id" { type = string }
variable "provider_id" { type = string }
variable "repository" { type = string }
variable "environments" { type = list(string) }
variable "platform_workflow_ref_suffix" { type = string }
variable "service_accounts" {
  type = map(object({ name = string, environment = string }))
}

locals {
  owner = split("/", var.repository)[0]
}

resource "google_iam_workload_identity_pool" "this" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = var.pool_id
}

resource "google_iam_workload_identity_pool_provider" "this" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.this.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.environment"      = "assertion.environment"
    "attribute.ref"              = "assertion.ref"
    "attribute.job_workflow_ref" = "assertion.job_workflow_ref"
    "attribute.repo_env"         = "assertion.repository + '@' + assertion.environment"
  }
  attribute_condition = join(" && ", [
    "assertion.repository_owner == '${local.owner}'",
    "assertion.repository == '${var.repository}'",
    "assertion.environment in ${jsonencode(var.environments)}",
    "assertion.job_workflow_ref.startsWith('radicdotai/radic-delivery-platform/.github/workflows/')",
    "assertion.job_workflow_ref.endsWith('${var.platform_workflow_ref_suffix}')",
  ])
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "wif" {
  for_each           = var.service_accounts
  service_account_id = each.value.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.this.name}/attribute.repo_env/${var.repository}@${each.value.environment}"
}

output "provider_name" {
  value = google_iam_workload_identity_pool_provider.this.name
}
