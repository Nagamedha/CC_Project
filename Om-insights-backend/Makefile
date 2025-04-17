# ========================================
# 🚀 OmInsights: Makefile (CI/CD + Infra)
# ========================================

.PHONY: install install-skopeo run test clean lint format all \
        docker-start docker-login ensure-docker docker-build docker-push \
        verify-ecr-image verify-deployment rollback-deployment \
        deploy-infra deploy-file-processing deploy-file-processing-update \
        cdk-synth cdk-diff cdk-destroy infra-all \
        logs monitor print-vars print-ecr-image-uri run-opensearch-dashboard run-opensearch-local

# Python & Package Management
PYTHON := python
PIP := pip

# Project Metadata
PROJECT_NAME := om-insights
VERSION := 0.1.0
ENV ?= dev
ENVIRONMENTS := dev staging prod

# AWS & Docker Settings
AWS_PROFILE ?= default  # ✅ Set the default AWS profile (change if needed)
AWS := aws --profile $(AWS_PROFILE)  # ✅ Ensure all AWS CLI commands use this profile
# AWS Account & Region
AWS_ACCOUNT_ID := $(shell $(AWS) sts get-caller-identity --query Account --output text)
AWS_REGION ?= us-east-1
# Docker & CDK
DOCKER := $(shell which docker 2>/dev/null || echo "docker")
CDK := cdk

# Function & ECR Naming
# Generate a hash of `requirements.txt` to track changes
DOCKERFILE_HASH := $(shell sha256sum Dockerfile | awk '{print $$1}' | cut -c1-8)
REQS_HASH := $(shell sha256sum requirements.txt | awk '{print $$1}' | cut -c1-8)
LAMBDA_FUNCTION_NAME := $(shell echo $(notdir $(CURDIR)) | tr '[:upper:]' '[:lower:]')
ECR_REPO_NAME := $(PROJECT_NAME)-$(LAMBDA_FUNCTION_NAME)
LAMBDA_IMAGE_NAME := $(LAMBDA_FUNCTION_NAME)
IMAGE_TAG := $(ENV)-latest-$(DOCKERFILE_HASH)-$(REQS_HASH)
NAT_GATEWAY_ENABLED ?= false
# AWS CDK Context Parameters
CDK_CONTEXT := --context project_name=$(PROJECT_NAME) \
               --context environment=$(ENV) \
               --context ecr_repo_name=$(ECR_REPO_NAME) \
               --context lambda_image_name=$(LAMBDA_IMAGE_NAME) \
               --context image_tag=$(IMAGE_TAG) \
               --context aws_account=$(AWS_ACCOUNT_ID) \
               --context aws_region=$(AWS_REGION)

# Ensure AWS credentials are set before proceeding
check-aws:
	@echo "🔍 Verifying AWS Credentials..."
	@if ! $(AWS) sts get-caller-identity > /dev/null 2>&1; then \
	  echo "❌ AWS Credentials not found. Please configure AWS CLI (aws configure)"; exit 1; \
	fi
	@echo "✅ AWS Credentials Verified!"

# ===============================
# 🛠️ Install Dependencies
# ===============================

install:
	$(PIP) install -r requirements.txt

install-skopeo:
	@echo "Installing skopeo..."
	@if ! command -v skopeo >/dev/null 2>&1; then \
		if [[ "$$(uname)" == "Darwin" ]]; then \
			brew install skopeo; \
		elif [[ -f /etc/debian_version ]]; then \
			sudo apt update && sudo apt install -y skopeo; \
		elif [[ -f /etc/redhat-release ]]; then \
			sudo yum install -y skopeo; \
		else \
			echo "❌ Unsupported OS. Please install skopeo manually."; \
			exit 1; \
		fi \
	else \
		echo "✅ Skopeo is already installed."; \
	fi

# ===============================
# 🐳 Docker Utilities
# ===============================

docker-start:
	@echo "Starting Docker..."
	@if [ "$$(uname)" = "Darwin" ]; then open -a Docker && sleep 10; fi

docker-login:
	@echo "Logging into Docker..."
	$(DOCKER) login

ensure-docker: docker-start docker-login install-skopeo
	@echo "Docker & Skopeo are ready."

docker-build: ensure-docker
	@echo "Building Docker image..."
	$(DOCKER) build --platform linux/amd64 -t $(LAMBDA_IMAGE_NAME):$(IMAGE_TAG) .

create-ecr-repo:
	@echo "Checking if ECR repository exists..."
	@if ! $(AWS) ecr describe-repositories --repository-names $(ECR_REPO_NAME) --region $(AWS_REGION) > /dev/null 2>&1; then \
		echo "Creating ECR repository: $(ECR_REPO_NAME)"; \
		$(AWS) ecr create-repository --repository-name $(ECR_REPO_NAME) --region $(AWS_REGION); \
	fi

ECR_TOKEN := $(shell $(AWS) ecr get-login-password --region $(AWS_REGION))

docker-push: create-ecr-repo docker-build
	@echo "🔄 Logging into AWS ECR using profile $(AWS_PROFILE)..."
	$(AWS) ecr get-login-password --region $(AWS_REGION) | $(DOCKER) login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	@echo "🔄 Tagging and pushing Docker image to ECR..."
	$(DOCKER) tag $(LAMBDA_IMAGE_NAME):$(IMAGE_TAG) $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)
	$(DOCKER) push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)
	@echo "🔄 Re-authenticating before `skopeo copy`..."
	$(AWS) ecr get-login-password --region $(AWS_REGION) | $(DOCKER) login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	@echo "🔄 Converting OCI image format to Docker v2 Schema 2 for AWS Lambda compatibility..."
	skopeo copy --override-arch=amd64 --override-os=linux --format v2s2 \
		--src-creds AWS:$(ECR_TOKEN) \
		--dest-creds AWS:$(ECR_TOKEN) \
		docker://$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG) \
		docker://$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)

	@echo "✅ Image successfully converted to Docker v2 Schema 2 format."
	@echo "🗑️ Cleaning up old images in ECR, preserving any with '$(ENV)-latest-'..."
	@$(AWS) ecr list-images --repository-name $(ECR_REPO_NAME) --region $(AWS_REGION) --query 'imageIds[*]' --output json \
		| jq -c '.[]' \
		| grep -v '$(ENV)-latest-' \
		| jq -s '.' > delete_images.json

	@if [ -s delete_images.json ]; then \
		$(AWS) ecr batch-delete-image --repository-name $(ECR_REPO_NAME) --region $(AWS_REGION) --image-ids file://delete_images.json; \
		rm delete_images.json; \
		echo "✅ Old images deleted (those not matching $(ENV)-latest-)."; \
	else \
		echo "✅ No images found outside the pattern $(ENV)-latest-, so nothing to delete."; \
	fi

verify-ecr-image:
	@echo "🔍 Verifying image format in ECR..."
	skopeo inspect --raw docker://$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG) | jq .

# ===============================
# 🚀 Deployment & CI/CD
# ===============================

deploy-infra:
	@echo "Deploying Infrastructure..."
	cd file_processor/infrastructure && $(CDK) deploy --app "python app.py" \
	    $(CDK_CONTEXT) --context nat_gateway_enabled=$(NAT_GATEWAY_ENABLED) \
	    --require-approval never \
	    OmInsightsBaseInfraStack
	@echo "✅ Infrastructure Deployment Complete!"

deploy-file-processing: docker-push verify-ecr-image check-aws
	@echo "Deploying File Processing Lambda..."
	cd file_processor/infrastructure && $(CDK) deploy --app "python app.py" \
	    $(CDK_CONTEXT) --require-approval never \
	    OmInsightsFileProcessingStack
	@echo "✅ File Processing Deployment Complete!"

# Deploy Processing Lambdas Stack (Sales, Inventory, General)
deploy-processing-lambdas: docker-push verify-ecr-image check-aws
	@echo "🚀 Deploying Processing Lambdas Stack..."
	cd file_processor/infrastructure && $(CDK) deploy --app "python app.py" \
	    $(CDK_CONTEXT) --require-approval never \
	    OmInsightsProcessingLambdasStack
	@echo "✅ Processing Lambdas Deployment Complete!"

deploy-file-processing-routing-lambda-update: docker-push verify-ecr-image check-aws
	@echo "🚀 Updating AWS Lambda function with converted Docker image..."
	$(AWS) lambda update-function-code \
	  --function-name $(PROJECT_NAME)-routing-$(ENV) \
	  --image-uri $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)

	@echo "✅ AWS Lambda Function Updated Successfully!"

deploy-file-processing-sales-lambda-update: docker-push verify-ecr-image check-aws
	@echo "🚀 Updating AWS Lambda function with converted Docker image..."
	$(AWS) lambda update-function-code \
	  --function-name $(PROJECT_NAME)-sales-processing-$(ENV) \
	  --image-uri $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)

	@echo "✅ AWS Lambda Function Updated Successfully!"

deploy-file-processing-inventory-lambda-update: docker-push verify-ecr-image check-aws
	@echo "🚀 Updating AWS Lambda function with converted Docker image..."
	$(AWS) lambda update-function-code \
	  --function-name $(PROJECT_NAME)-inventory-processing-$(ENV) \
	  --image-uri $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)

	@echo "✅ AWS Lambda Function Updated Successfully!"

deploy-file-processing-marketing-lambda-update: docker-push verify-ecr-image check-aws
	@echo "🚀 Updating AWS Lambda function with converted Docker image..."
	$(AWS) lambda update-function-code \
	  --function-name $(PROJECT_NAME)-marketing-processing-$(ENV) \
	  --image-uri $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)

	@echo "✅ AWS Lambda Function Updated Successfully!"


verify-deployment:
	@echo "Verifying deployment status..."
	$(AWS) lambda get-function-configuration --function-name $(PROJECT_NAME)-file-processing-$(ENV)

rollback-deployment:
	@echo "Rolling back to previous File Processing Lambda version..."
	$(AWS) lambda update-function-code \
	  --function-name $(PROJECT_NAME)-file-processing-$(ENV) \
	  --image-uri $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):previous
	@echo "✅ Rolled back successfully!"

# ===============================
# 📊 Monitoring & Logging
# ===============================

logs:
	@echo "Fetching latest AWS Lambda logs..."
	$(AWS) logs tail /aws/lambda/$(PROJECT_NAME)-file-processing-$(ENV) --follow

monitor:
	@echo "Monitoring File Processing Lambda function..."
	$(AWS) lambda get-function --function-name $(PROJECT_NAME)-file-processing-$(ENV)

# ===============================
# 🔍 Debugging & Info Commands
# ===============================

print-vars:
	@echo "LAMBDA_FUNCTION_NAME: $(LAMBDA_FUNCTION_NAME)"
	@echo "ECR_REPO_NAME: $(ECR_REPO_NAME)"
	@echo "LAMBDA_IMAGE_NAME: $(LAMBDA_IMAGE_NAME)"
	@echo "IMAGE_TAG: $(IMAGE_TAG)"

print-ecr-image-uri:
	@echo "Full ECR Image URI: $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)"

run-opensearch-dashboard:
	@echo "Starting SSH tunnel for OpenSearch Dashboards on localhost:5601..."
	ssh -i ~/Downloads/omec2.pem -N -L 5601:vpc-ominights-uh4xluwsmhjtpcziv7uwt472fa.us-east-1.es.amazonaws.com:443 ec2-user@54.198.176.61

run-opensearch-local:
	@echo "Starting SSH tunnel for OpenSearch API on localhost:9201..."
	ssh -i ~/Downloads/omec2.pem -N -L 9201:vpc-ominights-uh4xluwsmhjtpcziv7uwt472fa.us-east-1.es.amazonaws.com:443 ec2-user@54.198.176.61
