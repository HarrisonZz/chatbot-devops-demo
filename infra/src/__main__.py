from stacks import edge, registry, eks, network, eks_addons, storage
import pulumi

ROUTER = {
  "edge": edge.deploy,
  "registry": registry.deploy,
  "network": network.deploy,
  "eks": eks.deploy,
  "addons": eks_addons.deploy,
  "storage": storage.deploy
}

ALLOWED_ENVS = {"dev", "test", "prod"}

def parse_stack(stack_name: str) -> tuple[str, str]:
    # net-dev -> ("net", "dev")
    parts = stack_name.split("-", 1)
    if len(parts) != 2:
        raise Exception(f"Stack name must be <component>-<env>, got: {stack_name}")
    component, env = parts
    if env not in ALLOWED_ENVS:
        raise Exception(f"env must be one of {sorted(ALLOWED_ENVS)}, got: {env}")
    return component, env

component, env = parse_stack(pulumi.get_stack())

if component not in ROUTER:
    raise Exception(f"Unknown component '{component}'. Allowed: {list(ROUTER.keys())}")

ROUTER[component](env=env)