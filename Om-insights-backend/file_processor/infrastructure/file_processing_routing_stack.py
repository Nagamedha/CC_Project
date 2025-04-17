import os

import yaml
from aws_cdk import (
    Stack,
    aws_ecr as ecr,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_iam as iam,
    aws_efs as efs,  # ✅ Import EFS
    aws_ec2 as ec2,  # ✅ Required for Security Groups
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    Duration,
    CfnOutput
)
from constructs import Construct

# ✅ Construct the correct path to `config.yaml`
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'infra_config','routing_config.yaml')

# ✅ Load Configuration from YAML File
with open(config_path, "r") as config_file:
    CONFIG = yaml.safe_load(config_file)

class FileProcessingStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, lambda_role: iam.Role, sqs_queues: dict,
                 file_bucket: s3.Bucket, worker_sqs_queues:dict, file_metadata_table: dynamodb.Table,efs_file_system: efs.FileSystem, efs_access_point: efs.AccessPoint,
                 lambda_security_group: ec2.SecurityGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ✅ Load Config Values
        project_name = self.node.try_get_context('project_name') or CONFIG["project_name"]
        environment = self.node.try_get_context('environment')  or CONFIG["environment"]
        ecr_repo_name = self.node.try_get_context('ecr_repo_name') or CONFIG["ecr_repo"]["name"]
        image_tag = self.node.try_get_context('image_tag') or CONFIG["ecr_repo"]["image_tag"]
        lambda_memory = CONFIG["lambda"]["memory_size"]
        lambda_timeout = CONFIG["lambda"]["timeout_seconds"]

        if not ecr_repo_name or not image_tag:
            raise ValueError("ECR repository name and image tag must be provided in config.yaml.")
        # ✅ No need to create a new security group, just use the existing one
        self.lambda_security_group = lambda_security_group

        # ✅ Reference ECR Repository
        self.repository = ecr.Repository.from_repository_name(
            self, "OmInsightsBackendRepo", repository_name=ecr_repo_name
        )

        # ✅ Routing Lambda
        self.routing_lambda = lambda_.DockerImageFunction(
            self,
            "RoutingLambda",
            function_name=f"{project_name}-routing-{environment}",
            code=lambda_.DockerImageCode.from_ecr(repository=self.repository, tag_or_digest=image_tag),
            timeout=Duration.seconds(lambda_timeout),
            memory_size=lambda_memory,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            role=lambda_role,
            log_retention=logs.RetentionDays.ONE_WEEK,
            environment={
                "DYNAMODB_TABLE": file_metadata_table.table_name,
                "S3_BUCKET_NAME": file_bucket.bucket_name,
                **{f"{queue_name}_queue_url".upper(): queue.queue_url for queue_name, queue in
                   worker_sqs_queues.items()},  # Uppercase keys
                "LOG_LEVEL": "DEBUG"
            },
            security_groups=[lambda_security_group],  # ✅ Attach Lambda's EFS Security Group
            filesystem=lambda_.FileSystem.from_efs_access_point(
                efs_access_point,
                "/mnt/efs"  # ✅ Mount EFS inside the Lambda
            )
        )
        # ✅ Ensure Lambda waits for EFS
        self.routing_lambda.node.add_dependency(efs_file_system)
        self.routing_lambda.node.add_dependency(efs_access_point)

        # ✅ Grant Permissions
        file_metadata_table.grant_write_data(self.routing_lambda)
        file_bucket.grant_read_write(self.routing_lambda)

        for queue in worker_sqs_queues.values():
            queue.grant_send_messages(self.routing_lambda)

        for queue in sqs_queues.values():
            queue.grant_consume_messages(self.routing_lambda)

            # ✅ Attach SQS as an Event Source for Lambda
            lambda_.EventSourceMapping(
                self,
                f"{queue.node.id}-EventSource",
                target=self.routing_lambda,
                event_source_arn=queue.queue_arn,
                batch_size=5,
                max_batching_window=Duration.seconds(30)
            )

        # ✅ Outputs
        for queue_name, queue in worker_sqs_queues.items():
            CfnOutput(self, f"{queue_name.capitalize()}QueueUrl", value=queue.queue_url)
        CfnOutput(self, "LambdaFunctionName", value=self.routing_lambda.function_name)
        CfnOutput(self, "FileUploadBucketName", value=file_bucket.bucket_name)