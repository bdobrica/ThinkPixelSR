terraform {
  source = find_in_parent_folders("infra")
}

locals {
  # Optional local path overrides; unset variables retain the original contract.
  secrets = read_terragrunt_config(get_env("TPSR_SECRETS_FILE", ".secrets.hcl"))
  ssh_keys = {
    master_public_ssh_key     = file(get_env("TPSR_MASTER_PUBLIC_KEY_FILE", ".master.key.pub"))
    master_private_ssh_key    = file(get_env("TPSR_MASTER_PRIVATE_KEY_FILE", ".master.key"))
    worker_public_ssh_key     = file(get_env("TPSR_WORKER_PUBLIC_KEY_FILE", ".worker.key.pub"))
    worker_private_ssh_key    = file(get_env("TPSR_WORKER_PRIVATE_KEY_FILE", ".worker.key"))
    management_public_ssh_key = file(get_env("TPSR_MANAGEMENT_PUBLIC_KEY_FILE", ".management.key.pub"))
  }
}

inputs = merge(
  {
    hcloud_token           = "dummy"
    cluster_domain         = "dev.thinkpixel.io"
    cluster_domain_aliases = ["thinkpixel.io"]
    cluster_prefix         = "k8s"
    location               = "fsn1"
    os_image               = "debian-12"
    master_pool = {
      server_type = "cax21"
      count       = 1
    }
    worker_pools = {
      api = {
        server_type = "cax21"
        count       = 3
      }
      monitor = {
        server_type = "cax21"
        count       = 1
      }
    }
    admin_ips = ["135.181.209.167"]
    exposed_apps = {
      "api" = {
        protocol      = "https"
        external_port = 8080
        internal_port = 30080
        health_check = {
          path = "/ping"
        }
      },
      "monitor" = {
        protocol      = "https"
        external_port = 3000
        internal_port = 30030
        health_check = {
          path = "/api/health"
        }
      }
    }
  },
  local.secrets.inputs,
  local.ssh_keys
)
