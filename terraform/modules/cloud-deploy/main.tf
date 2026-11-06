variable "project_id" { type = string }
variable "region" { type = string }
variable "deployable" { type = string }
variable "artifact_storage" { type = string }
variable "targets" {
  type = map(object({
    service_name  = string
    execution_sa  = string
    pipeline      = string
    order         = number
    needs_approve = bool
  }))
}

resource "google_clouddeploy_target" "this" {
  for_each         = var.targets
  project          = var.project_id
  location         = var.region
  name             = "${var.deployable}-${each.key}"
  require_approval = each.value.needs_approve
  labels           = { svc = var.deployable, env = each.key }

  run {
    location = "projects/${var.project_id}/locations/${var.region}"
  }

  execution_configs {
    usages           = ["RENDER", "DEPLOY"]
    service_account  = each.value.execution_sa
    artifact_storage = var.artifact_storage
  }
}

locals {
  pipelines = distinct([for t in var.targets : t.pipeline])
}

resource "google_clouddeploy_delivery_pipeline" "this" {
  for_each = toset(local.pipelines)
  project  = var.project_id
  location = var.region
  name     = "${var.deployable}-${each.key}"
  labels   = { svc = var.deployable }

  serial_pipeline {
    dynamic "stages" {
      for_each = [for o in sort([for k, t in var.targets : format("%03d:%s", t.order, k) if t.pipeline == each.key]) : split(":", o)[1]]
      iterator = st
      content {
        target_id = google_clouddeploy_target.this[st.value].name
        profiles  = [st.value]
      }
    }
  }
}

output "pipelines" {
  value = { for k, p in google_clouddeploy_delivery_pipeline.this : k => p.name }
}

output "targets" {
  value = { for k, t in google_clouddeploy_target.this : k => t.name }
}
