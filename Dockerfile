FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

ARG ANSIBLE_VERSION=2.17.14
ARG AWSCLI_VERSION=2.31.19
ARG KUBECTL_VERSION=v1.32.2
ARG HELM_VERSION=v3.19.0
ARG PULUMI_VERSION=3.212.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl unzip tar gzip \
    git jq bash \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# ---- upgrade pip + install pipx ----
RUN python3 -m pip install --upgrade pip \
 && python3 -m pip install --no-cache-dir pipx \
 && pipx ensurepath

ENV PATH="/root/.local/bin:${PATH}"

RUN pipx install "ansible-core==${ANSIBLE_VERSION}" \
 && ansible --version

COPY ansible/requirements.txt /tmp/requirements.txt
#RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt
RUN pipx runpip ansible-core install -r /tmp/requirements.txt

COPY ansible/requirements.yml /tmp/requirements.yml
RUN ansible-galaxy collection install -r /tmp/requirements.yml -p /opt/ansible/collections \
 && ansible-galaxy role install -r /tmp/requirements.yml -p /opt/ansible/roles || true

ENV ANSIBLE_COLLECTIONS_PATHS="/opt/ansible/collections:/usr/share/ansible/collections"
ENV ANSIBLE_ROLES_PATH="/work/ansible/roles:/opt/ansible/roles:/etc/ansible/roles"

ENV AWS_PAGER=""

RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" -o /tmp/awscliv2.zip \
 && unzip -q /tmp/awscliv2.zip -d /tmp \
 && /tmp/aws/install \
 && rm -rf /tmp/aws /tmp/awscliv2.zip \
 && aws --version

ENV KUBECONFIG="~/.kube/config"
RUN curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
 && chmod +x /usr/local/bin/kubectl \
 && kubectl version --client

RUN curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" -o /tmp/helm.tgz \
 && tar -xzf /tmp/helm.tgz -C /tmp \
 && mv /tmp/linux-amd64/helm /usr/local/bin/helm \
 && chmod +x /usr/local/bin/helm \
 && rm -rf /tmp/helm.tgz /tmp/linux-amd64 \
 && helm version --short

RUN curl -fsSL "https://get.pulumi.com/releases/sdk/pulumi-v${PULUMI_VERSION}-linux-x64.tar.gz" -o /tmp/pulumi.tgz \
 && tar -xzf /tmp/pulumi.tgz -C /opt \
 && ln -s /opt/pulumi/pulumi /usr/local/bin/pulumi \
 && ln -s /opt/pulumi/pulumi-language-python /usr/local/bin/pulumi-language-python \
 && rm -f /tmp/pulumi.tgz \
 && pulumi version

COPY infra/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN set -eux; \
  python3 --version; \
  ansible --version; \
  aws --version; \
  kubectl version --client; \
  helm version --short; \
  pulumi version

WORKDIR /work
CMD ["bash"]