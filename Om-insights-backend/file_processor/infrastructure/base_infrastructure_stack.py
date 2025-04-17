import json
import os
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_iam as iam,
    aws_s3_notifications as s3n,
    aws_efs as efs,
    aws_dynamodb as dynamodb,
    Duration,
    RemovalPolicy,
    aws_opensearchserverless as aoss,
    CfnOutput
)
from constructs import Construct
import yaml

class BaseInfrastructureStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --------------------------------------------------------------------------------
        # 1) LOAD CONFIG
        # --------------------------------------------------------------------------------
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'infra_config',
            'infra_config.yaml'
        )
        with open(config_path, "r") as config_file:
            self.config = yaml.safe_load(config_file)
        self.tables = {}  # Store created tables for reference

        # Always allow context override via cdk.json or CLI
        self.project_name = self.node.try_get_context('project_name') or self.config["project_name"]
        self.env_name = self.node.try_get_context('environment') or self.config["environment"]
        # --------------------------------------------------------------------------------
        # 2) CREATE VPC
        # --------------------------------------------------------------------------------
        self.vpc = self._create_vpc()
        # --------------------------------------------
        # 2.1) CREATE EFS (Elastic File System) ✅
        # --------------------------------------------
        # ✅ Modify constructor to store Lambda Security Group
        self.efs_file_system, self.efs_access_point, self.lambda_security_group = self._create_efs()
        # --------------------------------------------------------------------------------
        # 3) CREATE S3 BUCKET
        # --------------------------------------------------------------------------------
        self.file_bucket = self._create_s3_bucket()

        # --------------------------------------------------------------------------------
        # 4) CREATE SQS QUEUES (REGION + SUBSCRIPTION TIERS)
        # --------------------------------------------------------------------------------
        self.sqs_queues = self._create_region_subscription_queues()

        # --------------------------------------------------------------------------------
        # 5) CREATE WORKER SQS QUEUES DYNAMICALLY FROM CONFIG
        # --------------------------------------------------------------------------------
        self.worker_queues = self._create_worker_queues()

        # --------------------------------------------------------------------------------
        # 6) CREATE LAMBDA ROLE
        # --------------------------------------------------------------------------------
        self.lambda_role = self._create_lambda_execution_role()

        # --------------------------------------------------------------------------------
        # 7) CREATE / REUSE DYNAMODB TABLE
        # --------------------------------------------------------------------------------
        self.file_metadata_table = self._create_or_reuse_dynamodb_table()

        # --------------------------------------------------------------------------------
        # 8) CREATE AOSS COLLECTION (OpenSearch Serverless Index)
        # --------------------------------------------------------------------------------
        # Create required encryption policy before AOSS collections
        # self.aoss_encryption_policy = self._create_aoss_encryption_policy()
        # # Now create the collections, these are serverless costs every hr of ocu only enable it for production.
        # self.aoss_collections = self._create_aoss_collection()

        # Fetch table names dynamically from config.yaml
        self.table_names = self.config.get("tables", [])
        if not self.table_names:
            raise ValueError("No table names found in the configuration. Please define 'tables' in config.yaml.")
        # Create tables dynamically
        for table_name in self.table_names:
            table = self._create_processing_lambdas_dynamodb_table(table_name)
            self.tables[table_name] = table
            # Output the table name for use in other stacks
            CfnOutput(self, f"{table_name.capitalize()}TableName", value=table.table_name)
        # --------------------------------------------------------------------------------
        # 8) OUTPUTS
        # --------------------------------------------------------------------------------
        CfnOutput(self, "BucketName", value=self.file_bucket.bucket_name)
        CfnOutput(self, "LambdaRoleArn", value=self.lambda_role.role_arn)
        CfnOutput(self, "FileMetadataTableName", value=self.file_metadata_table.table_name)

    # ------------------------------------------------------------------------------------
    # HELPER METHODS FOR RESOURCE CREATION
    # ------------------------------------------------------------------------------------
    def _create_vpc(self) -> ec2.Vpc:
        """Create a cost-effective VPC with private subnets and VPC Endpoints (no NAT Gateway)."""
        nat_gateway_enabled = self.node.try_get_context("nat_gateway_enabled") == "true"
        vpc = ec2.Vpc(
            self,
            "OmInsightsVpc",
            max_azs=2,
            nat_gateways=1 if nat_gateway_enabled else 0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="PrivateSubnet",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,  # ✅ Private subnet for Lambdas & EFS
                    cidr_mask=24
                ),
            ]
        )

        # ✅ Gateway Endpoints (Free, optimized for high-speed access)
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3
        )
        vpc.add_gateway_endpoint(
            "DynamoDBEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
        )

        # # ✅ Interface Endpoints (Use service names as strings)
        # interface_endpoints = {
        #     "LambdaEndpoint": "lambda",
        #     "EcrApiEndpoint": "ecr.api",
        #     "EcrDkrEndpoint": "ecr.dkr",
        #     "SqsEndpoint": "sqs",
        #     "SsmEndpoint": "ssm",
        #     "CloudWatchLogsEndpoint": "logs",
        #     "SecretsManagerEndpoint": "secretsmanager",
        #     "KMSEndpoint": "kms"
        # }
        #
        # for endpoint_name, service_name in interface_endpoints.items():
        #     vpc.add_interface_endpoint(endpoint_name, service=ec2.InterfaceVpcEndpointAwsService(service_name))

        return vpc

    def _create_s3_bucket(self) -> s3.IBucket:
        """Create or import an S3 bucket for file uploads."""
        bucket_name = self.config["bucket_name"]
        try:
            # Attempt to import existing
            return s3.Bucket.from_bucket_name(
                self,
                "ExistingFileBucket",
                bucket_name
            )
        except Exception:
            # Otherwise create a new one
            return s3.Bucket(
                self,
                "FileUploadBucket",
                bucket_name=bucket_name,
                removal_policy=RemovalPolicy.RETAIN,
                auto_delete_objects=False,
                versioned=True
            )

    def _create_region_subscription_queues(self) -> dict:
        """
        Create SQS queue + DLQ for each (region + subscription_tier).
        Return a dict { queue_name: sqs.Queue }.
        """
        queue_dict = {}

        regions = self.config["regions"]
        subscription_tiers = self.config["subscription_tiers"]

        for region in regions:
            for tier in subscription_tiers:
                queue_name = f"{region}-{tier}-file-processing-queue"
                dlq_name = f"{queue_name}-DLQ"

                # Create DLQ
                dlq = sqs.Queue(
                    self,
                    dlq_name,
                    queue_name=dlq_name,
                    retention_period=Duration.days(7),
                    removal_policy=RemovalPolicy.RETAIN
                )

                # Main queue with DLQ
                sqs_queue = sqs.Queue(
                    self,
                    queue_name,
                    queue_name=queue_name,
                    retention_period=Duration.days(4),
                    visibility_timeout=Duration.seconds(75),
                    dead_letter_queue=sqs.DeadLetterQueue(
                        max_receive_count=2,
                        queue=dlq
                    )
                )

                queue_dict[queue_name] = sqs_queue

                # Attach S3 event notification (prefix = region/tier)
                self.file_bucket.add_event_notification(
                    s3.EventType.OBJECT_CREATED,
                    s3n.SqsDestination(sqs_queue),
                    s3.NotificationKeyFilter(prefix=f"{region}/{tier}/")
                )

        return queue_dict

    def _create_worker_queues(self) -> dict:
        """
        Create Worker SQS queues from config["queues"].
        - ✅ Automatically assigns a DLQ for EVERY queue created.
        """
        worker_queues = {}

        for queue_name, queue_id in self.config["queues"].items():
            # Lower-case or handle naming as you wish
            normalized_name = queue_name.lower()

            # Build the final queue name with project/env
            final_queue_name = f"{self.project_name}-{queue_id.lower()}-{self.env_name}"

            # ✅ Create a DLQ for every queue
            dlq_name = f"{final_queue_name}-dlq"
            dlq = sqs.Queue(
                self,
                f"{queue_id}DLQ",
                queue_name=dlq_name,
                retention_period=Duration.days(14),  # ✅ Store messages for 14 days
                removal_policy=RemovalPolicy.RETAIN
            )

            # ✅ Main queue with DLQ
            queue = sqs.Queue(
                self,
                f"{queue_id}Queue",
                queue_name=final_queue_name,
                visibility_timeout=Duration.seconds(300),
                dead_letter_queue=sqs.DeadLetterQueue(
                    max_receive_count=2,  # ✅ Move to DLQ after 5 failures
                    queue=dlq
                )
            )

            worker_queues[normalized_name] = queue

            # Output queue and DLQ names
            CfnOutput(self, f"{queue_id}QueueName", value=queue.queue_name)
            CfnOutput(self, f"{queue_id}DLQName", value=dlq.queue_name)

        return worker_queues

    def _create_lambda_execution_role(self) -> iam.Role:
        """Create a Lambda execution role with various managed policies."""
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSLambda_FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSBatchFullAccess"),
            ]
        )

        # ✅ Add Lambda Invoke permissions (in case other AWS services need to trigger Lambda)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account}:function:*",
                ],
                effect=iam.Effect.ALLOW
            )
        )

        # ✅ Add EFS permissions to Lambda Role
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite", "elasticfilesystem:ClientRootAccess"],
                resources=[self.efs_file_system.file_system_arn],
                effect=iam.Effect.ALLOW
            )
        )

        # Add Full iam:PassRole permission
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[lambda_role.role_arn],
                effect=iam.Effect.ALLOW
            )
        )
        # ✅ Allow full AOSS access for managing collections, indexes, templates, reindexing, search, etc.
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "aoss:APIAccessAll",  # Full OpenSearch Serverless API access
                    "aoss:BatchGetCollection",  # Read collection metadata
                    "aoss:BatchGetIndex",  # Read index info
                    "aoss:CreateIndex",  # Create new index
                    "aoss:UpdateIndex",  # Update index settings
                    "aoss:DeleteIndex",  # Delete index
                    "aoss:IngestDocuments",  # Add/update documents
                    "aoss:Search",  # Perform search queries
                ],
                resources=["*"],  # You can later restrict this to specific collection ARNs
                effect=iam.Effect.ALLOW
            )
        )

        return lambda_role

    def _create_or_reuse_dynamodb_table(self) -> dynamodb.ITable:
        """
        Reuse if table with config["table_name"] exists,
        otherwise create a new table with recommended GSI & LSI.
        """
        table_name = self.config["table_name"]
        try:
            existing_table = dynamodb.Table.from_table_name(
                self,
                "ExistingFileMetadataTable",
                table_name
            )
            CfnOutput(self, "DynamoDBTableStatus", value=f"Reusing existing table: {table_name}")
            return existing_table
        except Exception:
            # Create new table
            read_capacity = self.config["dynamodb_read_capacity"]
            write_capacity = self.config["dynamodb_write_capacity"]
            min_cap = self.config["dynamodb_min_scaling"]
            max_cap = self.config["dynamodb_max_scaling"]

            new_table = dynamodb.Table(
                self,
                "FileProcessingMetadata",
                table_name=table_name,
                partition_key=dynamodb.Attribute(name="business_id", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="file_id", type=dynamodb.AttributeType.STRING),
                billing_mode=dynamodb.BillingMode.PROVISIONED,
                read_capacity=read_capacity,
                write_capacity=write_capacity,
                removal_policy=RemovalPolicy.RETAIN,
                time_to_live_attribute="ttl",
            )

            # Enable Auto-Scaling
            read_scaling = new_table.auto_scale_read_capacity(
                min_capacity=min_cap,
                max_capacity=max_cap
            )
            read_scaling.scale_on_utilization(target_utilization_percent=70)

            write_scaling = new_table.auto_scale_write_capacity(
                min_capacity=min_cap,
                max_capacity=max_cap
            )
            write_scaling.scale_on_utilization(target_utilization_percent=70)

            # GSI for region-based queries
            new_table.add_global_secondary_index(
                index_name="RegionTierIndex",
                partition_key=dynamodb.Attribute(name="region_tier", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="upload_timestamp", type=dynamodb.AttributeType.NUMBER),
                projection_type=dynamodb.ProjectionType.ALL,
            )

            # LSI for file type queries
            new_table.add_local_secondary_index(
                index_name="FileTypeIndex",
                sort_key=dynamodb.Attribute(name="file_type", type=dynamodb.AttributeType.STRING),
                projection_type=dynamodb.ProjectionType.ALL,
            )

            CfnOutput(self, "DynamoDBTableStatus", value=f"Created new table: {table_name}")

            # Grant lambda_util read/write
            new_table.grant_read_write_data(self.lambda_role)

            return new_table
    # --------------------------------------------
    # ✅ CREATE EFS FILE SYSTEM & ACCESS POINT
    # --------------------------------------------
    def _create_efs(self):
        """Creates an EFS File System and an Access Point for Lambda."""

        # ✅ Create EFS File System
        file_system = efs.FileSystem(
            self,
            "OmInsightsEFS",
            vpc=self.vpc,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_7_DAYS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ✅ Create an EFS Access Point for Lambda
        access_point = file_system.add_access_point(
            "OmInsightsEFSAccessPoint",
            path="/models",
            create_acl=efs.Acl(owner_uid="1001", owner_gid="1001", permissions="755"),
            posix_user=efs.PosixUser(uid="1001", gid="1001"),
        )

        # ✅ Create a Security Group for Lambda to access EFS (Move it here)
        lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaEfsSecurityGroup",
            vpc=self.vpc,
            description="Security group for Lambda functions accessing EFS",
            allow_all_outbound=True
        )

        # ✅ Allow Lambda Security Group to access EFS
        file_system.connections.allow_default_port_from(lambda_security_group)

        # ✅ Allow Lambda to access OpenSearch via HTTPS (port 443)
        lambda_security_group.add_ingress_rule(
            peer=lambda_security_group,
            connection=ec2.Port.tcp(443),
            description="Allow Lambda to communicate with OpenSearch over HTTPS"
        )

        # ✅ Output everything
        CfnOutput(self, "EFSFileSystemId", value=file_system.file_system_id)
        CfnOutput(self, "EFSAccessPointId", value=access_point.access_point_id)
        CfnOutput(self, "LambdaSecurityGroupId", value=lambda_security_group.security_group_id)

        return file_system, access_point, lambda_security_group

    def _create_aoss_encryption_policy(self) -> aoss.CfnSecurityPolicy:
        """
        Create an OpenSearch Serverless Encryption Security Policy required before creating a collection.
        """
        encryption_policy = aoss.CfnSecurityPolicy(
            self,
            "AOSSEncryptionPolicy",
            name=f"{self.project_name[:10]}-{self.env_name}-enc-policy",
            type="encryption",
            policy=json.dumps({
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": ["collection/*"]
                    }
                ],
                "AWSOwnedKey": True
            })
        )

        CfnOutput(self, "AOSSEncryptionPolicyName", value=encryption_policy.name)
        return encryption_policy

    def _create_aoss_collection(self) -> dict:
        """
        Create OpenSearch Serverless (AOSS) Collections per region from config.
        Also attach access policy for Lambda execution role.
        Returns a dict of created collections for future reference.
        """
        aoss_collections = {}
        aoss_collection_names = []

        # Read region list from config
        aoss_regions = self.config.get("aoss_region", [])
        if not aoss_regions:
            raise ValueError("No AOSS regions defined in config.yaml under 'aoss_region'")

        for region in aoss_regions:
            collection_name = f"{self.project_name}-{self.env_name}-{region}"
            logical_id = f"AOSSCollection{region.capitalize()}"

            collection = aoss.CfnCollection(
                self,
                logical_id,
                name=collection_name,
                type="SEARCH",
                description=f"AOSS collection for {region} region (MVP tier)"
            )
            # ✅ Make collection wait for encryption policy to be created
            collection.add_dependency(self.aoss_encryption_policy)
            # Track collection
            aoss_collections[region] = collection
            aoss_collection_names.append(collection_name)

            # Output
            CfnOutput(self, f"{region.capitalize()}AOSSCollectionName", value=collection.name)

        # Create a single access policy for all collections
        # Build AOSS resource names (not ARNs)
        aoss_resource_names = [f"collection/{name}" for name in aoss_collection_names]

        aoss_access_policy = aoss.CfnAccessPolicy(
            self,
            "LambdaAOSSAccessPolicy",
            name=f"{self.project_name}-{self.env_name}-aoss-access",
            type="data",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",  # ✅ REQUIRED
                            "Resource": aoss_resource_names,  # ✅ Short resource names like "collection/..."
                            "Permission": ["aoss:*"]  # ✅ Use supported values or aoss:* for full access
                        }
                    ],
                    "Principal": [self.lambda_role.role_arn]
                }
            ])
        )

        CfnOutput(self, "AOSSAccessPolicyName", value=aoss_access_policy.name)

        return aoss_collections

    def _create_processing_lambdas_dynamodb_table(self, table_name: str) -> dynamodb.ITable:
        """
        Dynamically create or reuse a DynamoDB table based on the provided table name from config.yaml.
        """
        full_table_name = f"om-insights-{table_name}-table"

        try:
            # Check if the table exists
            existing_table = dynamodb.Table.from_table_name(
                self, f"Existing{table_name.capitalize()}Table", full_table_name
            )
            CfnOutput(self, f"{table_name.capitalize()}TableStatus", value=f"Reusing existing table: {full_table_name}")
            return existing_table

        except Exception:
            # Define read/write capacities and scaling from config
            read_capacity = self.config.get("dynamodb_read_capacity", 5)
            write_capacity = self.config.get("dynamodb_write_capacity", 5)
            min_cap = self.config.get("dynamodb_min_scaling", 5)
            max_cap = self.config.get("dynamodb_max_scaling", 100)

            # Create new table
            new_table = dynamodb.Table(
                self,
                f"{table_name.capitalize()}Table",
                table_name=full_table_name,
                partition_key=dynamodb.Attribute(name="business_id", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="timestamp", type=dynamodb.AttributeType.STRING),
                billing_mode=dynamodb.BillingMode.PROVISIONED,
                read_capacity=read_capacity,
                write_capacity=write_capacity,
                removal_policy=RemovalPolicy.RETAIN,
                time_to_live_attribute="ttl",
            )

            # Enable Auto-Scaling
            read_scaling = new_table.auto_scale_read_capacity(min_capacity=min_cap, max_capacity=max_cap)
            read_scaling.scale_on_utilization(target_utilization_percent=70)

            write_scaling = new_table.auto_scale_write_capacity(min_capacity=min_cap, max_capacity=max_cap)
            write_scaling.scale_on_utilization(target_utilization_percent=70)

            # Add GSI (Global Secondary Index) for region-based queries
            new_table.add_global_secondary_index(
                index_name="RegionTierIndex",
                partition_key=dynamodb.Attribute(name="region_tier", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="upload_timestamp", type=dynamodb.AttributeType.NUMBER),
                projection_type=dynamodb.ProjectionType.ALL,
            )

            # Add LSI (Local Secondary Index) for file type queries
            new_table.add_local_secondary_index(
                index_name="FileTypeIndex",
                sort_key=dynamodb.Attribute(name="file_type", type=dynamodb.AttributeType.STRING),
                projection_type=dynamodb.ProjectionType.ALL,
            )

            CfnOutput(self, f"{table_name.capitalize()}TableStatus", value=f"Created new table: {full_table_name}")

            # Grant read/write permissions to Lambda function
            new_table.grant_read_write_data(self.lambda_role)

            return new_table