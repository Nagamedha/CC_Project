import os

print("Current working directory:", os.getcwd())
import yaml
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_iam as iam,
    aws_efs as efs,  # ✅ Import EFS
    aws_ec2 as ec2,  # ✅ Required for Security Groups
    aws_opensearchserverless as aoss,
    Duration, Size
)
from aws_cdk.aws_lambda_event_sources import SqsEventSource
from constructs import Construct


class ProcessingLambdasStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, lambda_role: iam.Role, repository,
                 image_tag: str,
                 sqs_queues: dict, efs_file_system: efs.FileSystem, efs_access_point: efs.AccessPoint,
                 lambda_security_group: ec2.SecurityGroup,
                 # aoss_collections: dict,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ✅ Load configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'infra_config',
                                   'lambda_config.yaml')
        with open(config_path, 'r') as config_file:
            config = yaml.safe_load(config_file)

        project_name = self.node.try_get_context('project_name') or config['project_name']
        environment = self.node.try_get_context('environment') or config['default_environment']

        # ✅ No need to create a new security group, just use the existing one
        self.lambda_security_group = lambda_security_group
        # ✅ Store AOSS collections for Lambda usage
        # self.aoss_collections = aoss_collections
        # ✅ Ensure EFS is created before using it in Lambda
        self.node.add_dependency(efs_file_system)
        # Create Lambda functions dynamically
        for key, lambda_config in config["lambda_functions"].items():
            handler = lambda_config.get("handler")
            if not handler:
                raise ValueError(f"No handler defined for Lambda '{key}' in config")

            handler_cmd = [handler]

            # ✅ Create the Docker-based Lambda function with EFS
            lambda_function = lambda_.DockerImageFunction(
                self,
                f"{key.capitalize()}ProcessingLambda",
                function_name=f"{project_name}-{lambda_config['function_name_suffix']}-{environment}",
                code=lambda_.DockerImageCode.from_ecr(
                    repository=repository,
                    tag_or_digest=image_tag,
                    cmd=handler_cmd
                ),
                timeout=Duration.seconds(lambda_config.get("timeout", 240)),
                memory_size=lambda_config.get("memory", 1024),
                ephemeral_storage_size=Size.mebibytes(lambda_config.get("ephemeral_storage", 4096)),
                # ✅ 4GB Ephemeral Storage
                role=lambda_role,
                log_retention=logs.RetentionDays.ONE_WEEK,
                environment=lambda_config["env_vars"],
                vpc=vpc,  # ✅ Ensure Lambda is inside the VPC
                security_groups=[lambda_security_group],  # ✅ Attach Lambda's EFS Security Group
                filesystem=lambda_.FileSystem.from_efs_access_point(
                    efs_access_point,
                    "/mnt/efs"  # ✅ Mount EFS inside the Lambda
                )
            )

            # ✅ Ensure Lambda waits for EFS
            lambda_function.node.add_dependency(efs_file_system)
            lambda_function.node.add_dependency(efs_access_point)

            # If the user sets a provisioned concurrency > 0, add an alias with that concurrency
            prov_concurrency = lambda_config.get("provisioned_concurrency", 0)
            if prov_concurrency > 0:
                # Creates an alias named "live" with a specified concurrency
                lambda_alias = lambda_function.add_alias(
                    "live",
                    provisioned_concurrent_executions=prov_concurrency
                )

            # Configure SQS event source (if applicable)
            queue_key = key
            if queue_key in sqs_queues:
                queue = sqs_queues[queue_key]
                queue.grant_consume_messages(lambda_function)
                lambda_function.add_event_source(SqsEventSource(
                    queue,
                    batch_size=5,
                    max_batching_window=Duration.seconds(30)
                ))
            else:
                raise ValueError(f"SQS queue '{key}' not found in provided queues dict.")