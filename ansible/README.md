pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

ansible-playbook playbooks/bootstrap.yml

