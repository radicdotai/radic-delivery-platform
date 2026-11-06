terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    bucket = "radicai-terraform-state-dev"
    prefix = "delivery-platform/poc-1"
  }
}

variable "operator" {
  type    = string
  default = "user:aditya.kasaudhan@radic.ai"
}

variable "platform_ref_suffix" {
  type    = string
  default = "@refs/tags/poc1-canary"
}

locals {
  project    = "radicai"
  region     = "us-central1"
  deployable = "ops-console-cdpoc"
  repository = "radicdotai/operations-console-cdpoc"
  bucket     = "radicai-cd-source-cdpoc"
  envs = {
    dev   = { pipeline = "dev", order = 1, needs_approve = false }
    stage = { pipeline = "rel", order = 1, needs_approve = false }
    prod  = { pipeline = "rel", order = 2, needs_approve = true }
  }
  duties = ["build", "rel-dev", "rel-stage", "prod-promoter", "prod-approver", "rollback"]
}

provider "google" {
  project = local.project
  region  = local.region
}

resource "google_service_account" "duty" {
  for_each     = toset(local.duties)
  account_id   = "cdpoc-${each.key}"
  display_name = "PoC-1 ${each.key}"
}

resource "google_service_account" "exec" {
  for_each     = local.envs
  account_id   = "cdpoc-exec-${each.key}"
  display_name = "PoC-1 Cloud Deploy execution ${each.key}"
}

resource "google_service_account" "runtime" {
  account_id   = "cdpoc-runtime"
  display_name = "PoC-1 sandbox runtime"
}

resource "google_artifact_registry_repository" "images" {
  location      = local.region
  repository_id = local.deployable
  format        = "DOCKER"
  labels        = { svc = local.deployable }
}

resource "google_artifact_registry_repository_iam_member" "build_writer" {
  location   = local.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.duty["build"].member
}

resource "google_storage_bucket" "source" {
  name                        = local.bucket
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true
  force_destroy               = true
  lifecycle_rule {
    condition { age = 30 }
    action { type = "Delete" }
  }
}

resource "google_storage_bucket_iam_member" "source" {
  for_each = merge(
    { for d in ["rel-dev", "rel-stage", "prod-promoter", "rollback"] : d => google_service_account.duty[d].member },
    { for e in keys(local.envs) : "exec-${e}" => google_service_account.exec[e].member },
  )
  bucket = google_storage_bucket.source.name
  role   = "roles/storage.objectAdmin"
  member = each.value
}

resource "google_storage_bucket_iam_member" "source_bucket_get" {
  for_each = google_storage_bucket_iam_member.source
  bucket   = google_storage_bucket.source.name
  role     = "roles/storage.legacyBucketReader"
  member   = each.value.member
}

resource "google_storage_bucket_iam_member" "approver_reads" {
  bucket = google_storage_bucket.source.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.duty["prod-approver"].member
}

resource "google_cloud_run_v2_service" "sandbox" {
  for_each            = local.envs
  name                = "${local.deployable}-${each.key}"
  location            = local.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = { svc = local.deployable, env = each.key }

  template {
    service_account = google_service_account.runtime.email
    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
    }
  }

  lifecycle {
    ignore_changes = [template, traffic, client, client_version, scaling]
  }
}

resource "google_cloud_run_v2_service_iam_member" "operator_invoker" {
  for_each = local.envs
  name     = google_cloud_run_v2_service.sandbox[each.key].name
  location = local.region
  role     = "roles/run.invoker"
  member   = var.operator
}

resource "google_cloud_run_v2_service_iam_member" "exec_developer" {
  for_each = local.envs
  name     = google_cloud_run_v2_service.sandbox[each.key].name
  location = local.region
  role     = "roles/run.developer"
  member   = google_service_account.exec[each.key].member
}

resource "google_cloud_run_v2_service_iam_member" "viewer" {
  for_each = {
    "dev:rel-dev"        = ["dev", "rel-dev"]
    "dev:rollback"       = ["dev", "rollback"]
    "stage:rel-stage"    = ["stage", "rel-stage"]
    "stage:rollback"     = ["stage", "rollback"]
    "prod:prod-promoter" = ["prod", "prod-promoter"]
    "prod:prod-approver" = ["prod", "prod-approver"]
    "prod:rollback"      = ["prod", "rollback"]
  }
  name     = google_cloud_run_v2_service.sandbox[each.value[0]].name
  location = local.region
  role     = "roles/run.viewer"
  member   = google_service_account.duty[each.value[1]].member
}

resource "google_service_account_iam_member" "exec_uses_runtime" {
  for_each           = local.envs
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.exec[each.key].member
}

resource "google_project_iam_member" "exec_job_runner" {
  for_each = local.envs
  project  = local.project
  role     = "roles/clouddeploy.jobRunner"
  member   = google_service_account.exec[each.key].member
}

resource "google_service_account_iam_member" "acts_as_exec" {
  for_each = {
    "rel-dev:dev"        = ["rel-dev", "dev"]
    "rel-stage:stage"    = ["rel-stage", "stage"]
    "prod-promoter:prod" = ["prod-promoter", "prod"]
    "rollback:dev"       = ["rollback", "dev"]
    "rollback:stage"     = ["rollback", "stage"]
    "rollback:prod"      = ["rollback", "prod"]
  }
  service_account_id = google_service_account.exec[each.value[1]].name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.duty[each.value[0]].member
}

module "cloud_deploy" {
  source           = "../../modules/cloud-deploy"
  project_id       = local.project
  region           = local.region
  deployable       = local.deployable
  artifact_storage = "gs://${local.bucket}/artifacts"
  targets = {
    for e, v in local.envs : e => merge(v, {
      service_name = google_cloud_run_v2_service.sandbox[e].name
      execution_sa = google_service_account.exec[e].email
    })
  }
}

locals {
  rollout_target = "api.getAttribute('clouddeploy.googleapis.com/rolloutTarget', '')"
  pipeline_grants = {
    rel-dev = {
      pipeline = "dev", role = "roles/clouddeploy.releaser", targets = null
    }
    rel-stage = {
      pipeline = "rel", role = "roles/clouddeploy.releaser", targets = ["", "${local.deployable}-stage"]
    }
    prod-promoter = {
      pipeline = "rel", role = "roles/clouddeploy.releaser", targets = ["", "${local.deployable}-prod"]
    }
    prod-approver = {
      pipeline = "rel", role = "roles/clouddeploy.approver", targets = ["", "${local.deployable}-prod"]
    }
    rollback-dev = {
      pipeline = "dev", role = "roles/clouddeploy.releaser", targets = null
    }
    rollback-rel = {
      pipeline = "rel", role = "roles/clouddeploy.releaser", targets = null
    }
  }
}

resource "google_clouddeploy_delivery_pipeline_iam_member" "duty" {
  for_each = local.pipeline_grants
  project  = local.project
  location = local.region
  name     = module.cloud_deploy.pipelines[each.value.pipeline]
  role     = each.value.role
  member   = google_service_account.duty[startswith(each.key, "rollback") ? "rollback" : each.key].member

  dynamic "condition" {
    for_each = each.value.targets == null ? [] : [each.value.targets]
    content {
      title      = "only-${each.key}-targets"
      expression = join(" || ", [for t in condition.value : "${local.rollout_target} == '${t}'"])
    }
  }
}

resource "google_project_iam_custom_role" "operations_reader" {
  role_id     = "cdpocDeployOperationsReader"
  title       = "PoC-1 Cloud Deploy operation reader"
  permissions = ["clouddeploy.operations.get"]
}

resource "google_project_iam_member" "operations_reader" {
  for_each = toset(["rel-dev", "rel-stage", "prod-promoter", "prod-approver", "rollback"])
  project  = local.project
  role     = google_project_iam_custom_role.operations_reader.id
  member   = google_service_account.duty[each.key].member
}

resource "google_service_account_iam_member" "operator_impersonates" {
  for_each = merge(
    { for d, sa in google_service_account.duty : d => sa.name },
    { for e, sa in google_service_account.exec : "exec-${e}" => sa.name },
  )
  service_account_id = each.value
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.operator
}

module "wif" {
  source                       = "../../modules/wif"
  project_id                   = local.project
  pool_id                      = "gh-delivery"
  provider_id                  = "gh-delivery-nonprod"
  repository                   = local.repository
  environments                 = ["dev", "stage"]
  platform_workflow_ref_suffix = var.platform_ref_suffix
  service_accounts = {
    build-dev   = { name = google_service_account.duty["build"].name, environment = "dev" }
    build-stage = { name = google_service_account.duty["build"].name, environment = "stage" }
    rel-dev     = { name = google_service_account.duty["rel-dev"].name, environment = "dev" }
    rel-stage   = { name = google_service_account.duty["rel-stage"].name, environment = "stage" }
  }
}

output "wif_provider" {
  value = module.wif.provider_name
}

output "service_accounts" {
  value = merge(
    { for d, sa in google_service_account.duty : d => sa.email },
    { for e, sa in google_service_account.exec : "exec-${e}" => sa.email },
  )
}
