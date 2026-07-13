data "terraform_remote_state" "onprem" {
  backend = "local"

  config = {
    path = local.onprem_state_path
  }
}
