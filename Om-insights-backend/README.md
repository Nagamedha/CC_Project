# Om-insights-backend

## Project Overview

Om-insights-backend is a powerful, scalable backend service designed to provide data processing and insights capabilities. Built with a serverless architecture using AWS CDK, Lambda, and container technologies, it's optimized for flexibility and cost-effectiveness. The system processes various types of files (sales, inventory, etc.) through a routing mechanism that directs them to specialized processing lambdas. It also includes an advanced AI Context Retrieval & Fusion Engine for intelligent data analysis and insights generation.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Architecture Overview](#architecture-overview)
3. [Key Components](#key-components)
4. [Getting Started](#getting-started)
5. [Development Workflow](#development-workflow)
6. [Deployment](#deployment)
7. [Execution Flow](#execution-flow)
8. [Scaling Strategies](#scaling-strategies)
9. [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)
11. [License](#license)

## Project Structure

Additionally, the project includes a Context Engine module:

- `context_engine/`: AI Context Retrieval & Fusion Engine
  - `config/`: Static configs for retrieval and prompt generation
  - `core/`: Orchestrator that runs the full pipeline
  - `fusion/`: Combines retriever outputs into a coherent prompt
  - `retrievers/`: Plug-and-play retrievers for each data source
  - `router/`: Decides which retrievers to invoke
  - `models/`: Pydantic-based data models for all I/O
  - `utils/`: Text, date, and dict utilities used throughout
  - `di/`: Dependency injection & wiring logic
  - `src/`: AWS Lambda entrypoint (handler.py)
  - `infrastructure/`: CDK stack to deploy Lambda + IAM + (optional) API Gateway
  - `tests/`: Unit and integration tests per module

## Architecture Overview

Om-insights-backend uses a serverless event-driven architecture with the following key components:

1. **File Upload Trigger**: Files uploaded to S3 trigger the routing Lambda
2. **Routing Lambda**: Analyzes files and routes them to appropriate processing queues
3. **Processing Queues**: SQS queues for different file types (sales, inventory, etc.)
4. **Processing Lambdas**: Specialized container-based Lambda functions that process specific file types
5. **Shared File System**: EFS mount for handling large files and shared resources
6. **Metadata Storage**: DynamoDB for tracking file processing status and metadata
7. **Context Engine**: AI-powered retrieval and fusion layer for generating insights

![Architecture Diagram](architecture-diagram.png)

## Key Components

### Infrastructure Stacks

- **BaseInfrastructureStack**: Provisions core AWS resources (VPC, SQS, EFS, IAM, DynamoDB)
- **FileProcessingStack**: Sets up S3 triggers and event routing
- **ProcessingLambdasStack**: Deploys specialized processing Lambda functions
- **ContextEngineStack**: Deploys the AI Context Retrieval & Fusion Engine

### Lambda Functions

- **Routing Lambda**: Determines file type and routes to appropriate processing queue
- **Processing Lambdas**: Specialized functions for different file types:
  - Sales data processor
  - Inventory data processor
  - General-purpose data processor
- **Context Engine Lambda**: Handles AI-powered context retrieval and fusion

### Services

- **RoutingService**: Contains logic to analyze and route files
- **FileProcessorService**: Orchestrates the file processing workflow
- **Specialized Processing Services**: Business logic for specific file types
- **ContextEngineService**: Manages AI context retrieval and fusion

## Getting Started

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured with your credentials
- Python 3.9+
- Docker
- Node.js and npm (for AWS CDK)

### Environment Setup

**Clone the repository**

```bash
git clone https://github.com/your-username/om-insights-backend.git
cd om-insights-backend

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
npm install -g aws-cdk

aws configure

AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your-account-id
ENVIRONMENT=dev
```
## Execution Flow

1. **File Upload**: A file is uploaded to the designated S3 bucket
2. **S3 Event**: S3 generates an event that triggers the routing Lambda
3. **File Analysis**: The routing Lambda analyzes the file to determine its type
4. **Queue Selection**: Based on the file type, the routing Lambda sends a message to the appropriate SQS queue
5. **Processing Trigger**: The SQS message triggers the specialized processing Lambda
6. **File Processing**: The processing Lambda retrieves the file from S3 and processes it according to its business logic
7. **Results Storage**: Processing results are stored in DynamoDB and/or S3
8. **Notification**: Optional notifications are sent upon completion

Additionally, for the Context Engine:

1. **User Query Received**: (query, business_id, region)
2. **Router Invocation**: Decides which retrievers to use
3. **Data Retrieval**: Fetches relevant data from various sources
4. **Data Fusion**: Merges and deduplicates retrieved data
5. **Prompt Generation**: Prepares a context-rich prompt for LLMs
6. **Response**: Returns the result or passes it to an AI model

## Scaling Strategies

1. **Horizontal Scaling**: AWS Lambda automatically scales based on workload
2. **Database Scaling**: DynamoDB auto-scaling for handling variable throughput
3. **Queue-Based Load Leveling**: SQS queues buffer incoming requests during traffic spikes
4. **EFS for Large Files**: Elastic File System handles large files that exceed Lambda's /tmp storage
5. **Container Optimization**: Multi-stage Docker builds create efficient Lambda containers
6. **Concurrency Management**: Lambda concurrency settings prevent resource exhaustion

## Troubleshooting

### Common Issues

1. **Lambda Timeouts**
   - Check Lambda timeout settings in CDK stack
   - Consider breaking processing into smaller chunks

2. **Permission Errors**
   - Verify IAM roles have appropriate permissions
   - Check security group settings for VPC resources

3. **Container Image Issues**
   - Ensure Docker image is properly built and pushed to ECR
   - Verify Lambda function is updated with the correct image URI

### Logging and Monitoring

- **CloudWatch Logs** contain detailed Lambda execution logs
- **X-Ray tracing** provides insights into Lambda performance
- **CloudWatch Metrics** show Lambda invocation and error rates

For the Context Engine, additional logging and monitoring can be found in the `context_engine/` module logs.

## Contributing

We welcome contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.