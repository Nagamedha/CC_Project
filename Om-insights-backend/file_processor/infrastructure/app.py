#!/usr/bin/env python3
import os
import sys

from aws_cdk import App, Environment

# Add the parent directory to the path to import the base infrastructure stack
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

# Import the stacks
from base_infrastructure_stack import BaseInfrastructureStack
from file_processor.infrastructure.file_processing_routing_stack import FileProcessingStack
from file_processor.infrastructure.processing_lambdas_stack import ProcessingLambdasStack

app = App()

# ✅ Load AWS Environment Variables
env = Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
)

# ✅ Get the image tag from context or use a default value
image_tag = app.node.try_get_context('image_tag') or 'latest'

# **Step 1: Deploy Base Infrastructure Stack (VPC, SQS, EFS, IAM, DynamoDB)**
base_stack = BaseInfrastructureStack(app, "OmInsightsBaseInfraStack", env=env)

# **Step 2: Deploy File Processing Stack (S3 Triggers, Event Routing)**
file_processing_stack = FileProcessingStack(
    app,
    "OmInsightsFileProcessingStack",
    vpc=base_stack.vpc,
    lambda_role=base_stack.lambda_role,
    sqs_queues=base_stack.sqs_queues,  # ✅ Pass SQS queues
    file_bucket=base_stack.file_bucket,
    worker_sqs_queues=base_stack.worker_queues,
    file_metadata_table=base_stack.file_metadata_table,
    efs_file_system=base_stack.efs_file_system,  # ✅ Pass EFS File System
    efs_access_point=base_stack.efs_access_point,  # ✅ Pass EFS Access Point for Lambda
    lambda_security_group=base_stack.lambda_security_group,  # ✅ Pass Pre-Created Security Group
    env=env
)

# **Step 3: Deploy Processing Lambdas Stack (Ensures SQS & EFS are Available)**
processing_lambdas_stack = ProcessingLambdasStack(
    app,
    "OmInsightsProcessingLambdasStack",
    vpc=base_stack.vpc,
    lambda_role=base_stack.lambda_role,
    repository=file_processing_stack.repository,
    image_tag=image_tag,
    sqs_queues=base_stack.worker_queues,
    efs_file_system=base_stack.efs_file_system,  # ✅ Pass EFS File System
    efs_access_point=base_stack.efs_access_point,  # ✅ Pass EFS Access Point for Lambda
    lambda_security_group=base_stack.lambda_security_group,  # ✅ Pass Pre-Created Security Group
    # aoss_collections=base_stack.aoss_collections,  # ✅ Pass AOSS collections to Lambdas
    env=env
)

# ✅ Ensure ProcessingLambdasStack waits for BaseInfraStack (but avoid cyclic dependencies)
processing_lambdas_stack.node.add_dependency(file_processing_stack)  # ✅ Ensure File Processing is deployed first
file_processing_stack.node.add_dependency(base_stack)  # ✅ Ensure BaseInfra is deployed first

# ✅ Generate CloudFormation Template
app.synth()