# Ansible playbooks

## Prerequisites

On the computer running the playbooks:
  - A Python virtualenv with the [requirements](./requirements.txt) installed
  - `figlet` and `lolcat-c` installed, to generate the ASCII art used in the MOTD banner

On the servers:
  - a `ansible` user account with passwordless sudo (run the
    [`create-ansible-user`](./create-ansible-user.yml) playbook for this)

## Usage

1. Export the Vault URL: `export VAULT_ADDR=https://<vault URL>`
2. Login to Vault: `vault login -method=userpass username=<username>` (you can use any other method)
3. Retrieve the SSH private key from Vault and save it as `id_ed25519_ansible`
4. Execute a playbook: `ansible-playbook --inventory hosts deploy-server.yml`

## How to create the inventory

TODO: still useful?
