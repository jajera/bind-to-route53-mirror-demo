.PHONY: test build package deploy destroy

test:
	pytest tests/ -v

build:
	./scripts/build_lambda.sh

package: build

deploy: build
	./scripts/deploy_stacks.sh

destroy:
	./scripts/destroy_stacks.sh
