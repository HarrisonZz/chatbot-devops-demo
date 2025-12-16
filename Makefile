up-edge-dev:
	pulumi --cwd ./infra -s edge-dev up

up-registry-dev:
	pulumi --cwd ./infra -s registry-dev up

up-eks-dev:
	pulumi -s eks-dev config set eks:netRef HarrisonZz-org/ai-chatbot-infra/network-dev
	pulumi --cwd ./infra -s eks-dev up

up-network-dev:
	pulumi --cwd ./infra -s network-dev up

preview-all-dev:
	pulumi --cwd ./infra -s edge-dev preview
	pulumi --cwd ./infra -s registry-dev preview
	pulumi --cwd ./infra -s network-dev preview
	pulumi -s eks-dev config set eks:netRef HarrisonZz-org/ai-chatbot-infra/network-dev
	pulumi --cwd ./infra -s eks-dev preview

destroy-edge-dev:
	pulumi --cwd ./infra -s eks-dev destroy

destroy-edge-dev:
	pulumi --cwd ./infra -s registry-dev destroy
	
destroy-edge-dev:	
	pulumi --cwd ./infra -s edge-dev destroy