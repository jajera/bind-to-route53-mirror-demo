data "terraform_remote_state" "workload" {
  count = fileexists(local.workload_state_path) ? 1 : 0

  backend = "local"

  config = {
    path = local.workload_state_path
  }
}
