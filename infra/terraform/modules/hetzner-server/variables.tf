variable "server_name" {
  description = "Name of the Hetzner Cloud server"
  type        = string
}

variable "server_type" {
  description = "Hetzner server type (e.g. cx21, cx31)"
  type        = string
  default     = "cx31"

  validation {
    condition     = contains(["cx11", "cx21", "cx31", "cx41", "cx51"], var.server_type)
    error_message = "server_type must be a valid Hetzner shared CPU type (cx11–cx51)."
  }
}

variable "location" {
  description = "Hetzner datacenter location"
  type        = string
  default     = "nbg1"

  validation {
    condition     = contains(["nbg1", "fsn1", "hel1", "ash", "hil"], var.location)
    error_message = "location must be a valid Hetzner datacenter (nbg1, fsn1, hel1, ash, hil)."
  }
}

variable "image" {
  description = "OS image for the server"
  type        = string
  default     = "ubuntu-22.04"
}

variable "ssh_key_ids" {
  description = "List of Hetzner SSH key IDs to inject into the server"
  type        = list(number)
  default     = []
}

variable "labels" {
  description = "Key-value labels to attach to the server"
  type        = map(string)
  default     = {}
}

variable "user_data" {
  description = "Cloud-init user data script (base64 or plain text)"
  type        = string
  default     = ""
}
