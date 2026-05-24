# tflint configuration for MT Pricing infrastructure.
# Reference: https://github.com/terraform-linters/tflint

plugin "terraform" {
  enabled = true
  version = "0.5.0"
  source  = "github.com/terraform-linters/tflint-ruleset-terraform"
}

# Unused locals/variables are intentional: some document planned outputs,
# others reference secrets lists used in commented-out data source blocks.
rule "terraform_unused_declarations" {
  enabled = false
}
