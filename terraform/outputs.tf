output "public_ip" {
  value       = google_compute_instance.vm.network_interface[0].access_config[0].nat_ip
  description = "Public IP of the VM"
}

output "ssh_command" {
  value       = "ssh ubuntu@${google_compute_instance.vm.network_interface[0].access_config[0].nat_ip}"
  description = "SSH connection command"
}
