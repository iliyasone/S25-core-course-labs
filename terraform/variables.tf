variable "project_id" {}
variable "region"     { default = "us-central1" }
variable "zone"       { default = "us-central1-a" }

variable "credentials_file" {
  description = "Path to GCP service account JSON key"
}

variable "ssh_user" {
  description = "Username for SSH access"
  default     = "ubuntu"
}

variable "ssh_public_key_path" {
  description = "Path to local SSH public key"
  default     = "~/.ssh/id_rsa.pub"
}