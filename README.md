# Serverless Document & Data Processing using AWS Lambda

A scalable, event-driven architecture that automates metadata extraction from structured documents (e.g., CSV) using AWS services like S3, SQS, Lambda (Dockerized), and DynamoDB. The system processes uploaded files in real-time and stores extracted metadata in a NoSQL database — with zero manual effort.

🎥 **Live Demo**: [Watch on YouTube](https://youtu.be/OkruHlKifrg?feature=shared)  
📦 **GitHub Repo**: https://github.com/Nagamedha/CC_Project  

---

## 🚀 Project Highlights

- **Fully automated pipeline**: File upload → Trigger → Metadata extraction → Storage
- **Serverless-first design**: Uses AWS Lambda, S3, SQS, DynamoDB
- **Modular infrastructure**: Supports routing and processing Lambdas per data type (e.g., sales, inventory)
- **Fault-tolerant**: DLQ handling for failed events
- **Cloud-native scalability**: Built using VPC, subnets, ECR, CloudFormation stacks
- **Real-time storage**: Output saved in DynamoDB and visualized using DynamoDB Workbench

---

## 📁 Folder Structure

```
Om-insights-backend/
├── src/                         # Main Lambda entry point
├── file_processor/             # Metadata extraction logic
├── infrastructure/             # CDK infrastructure (VPC, S3, Lambda, SQS)
├── tests/                      # Unit and integration tests
├── Dockerfile                  # Docker config for Lambda
├── requirements.txt            # Python dependencies
└── README.md                   # You're here!
```

---

## 💪 Tech Stack

| Layer         | Tool/Service Used                             |
|---------------|-----------------------------------------------|
| File Storage  | Amazon S3                                      |
| Message Queue | Amazon SQS + Dead Letter Queue                |
| Compute       | AWS Lambda (Docker container via ECR)         |
| Storage       | Amazon DynamoDB                               |
| Monitoring    | Amazon CloudWatch                             |
| Dev Tools     | Python, PyCharm Community, GitHub             |
| Visualization | DynamoDB Workbench                            |
| Deployment    | AWS CDK (CloudFormation stacks)               |

---

## 🧪 How to Use This Project (Step-by-Step)

This section is for anyone who wants to **download, set up, and run the project locally or deploy it to AWS**.

### ✅ **Step 1: Clone the Repository**

```bash
git clone https://github.com/Nagamedha/CC_Project.git
cd CC_Project/Om-insights-backend
```

### ✅ **Step 2: Set Up Python Environment (For Lambda logic)**

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### ✅ **Step 3: Install Required Tools**

You’ll need the following tools:

| Tool           | Purpose                        | Install Command / Link                          |
|----------------|--------------------------------|-------------------------------------------------|
| **AWS CLI**    | Access & deploy to AWS         | [Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| **Docker**     | Build Lambda images             | [Download Docker](https://www.docker.com/get-started) |
| **Node.js**    | For AWS CDK                    | [Download Node.js](https://nodejs.org/)         |
| **AWS CDK**    | Deploy infrastructure           | `npm install -g aws-cdk`                         |
| **AWS Account**| Create & configure AWS profile | Run `aws configure` to set keys                 |

### ✅ **Step 4: Authenticate Docker with ECR (Optional for Deployment)**

```bash
aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-ecr-repo-uri>
```

Replace `<your-region>` and `<your-ecr-repo-uri>` with actual values.

### ✅ **Step 5: Build Docker Images for Lambdas**

From the project root:

```bash
docker build -t routing-lambda ./file_processor/
docker tag routing-lambda:latest <your-ecr-repo-uri>:latest
docker push <your-ecr-repo-uri>:latest
```

### ✅ **Step 6: Deploy Infrastructure with AWS CDK**

Navigate to the infrastructure directory:

```bash
cd infrastructure/
npm install
cdk bootstrap
cdk deploy --all
```

This command deploys:
- VPC & subnets
- S3 bucket
- SQS queues + DLQs
- Lambda functions (Routing + Processing)
- DynamoDB tables (e.g., `sales_table`)

### ✅ **Step 7: Run the Flow**

1. **Upload a CSV file to S3** (via AWS Console)
2. **S3 triggers an event**, message added to SQS
3. **Lambda is triggered**, Docker image is used to process
4. **Metadata is extracted and saved to DynamoDB**
5. **View the result** in DynamoDB Workbench or via:

```bash
aws dynamodb scan --table-name sales_table --region <your-region>
```

### ✅ **Optional: Test Locally with Docker Lambda**

```bash
docker run -v "$PWD":/var/task routing-lambda:latest
```

### 🧠 Quick Tips for Customization

- Add a new file type: create a new Processor Lambda under `file_processor/` and register it in the router.
- Add a new DynamoDB table: update the CDK stack in `infrastructure/processing_stack.py`.
- Want an API? Add **API Gateway** in CDK and connect to routing Lambda.

---

## 📊 Results

- **100% automation** from upload to storage
- **~90% manual effort reduced**
- **Processed in seconds**, not hours
- **Supports multiple file types and projects**
- Easily **scalable across teams or use cases**

---

## 💪 Future Scope

- Support for **PDF, Excel, and XML**
- **AI-based validation** and smart column mapping
- **Frontend for upload**, status tracking, and querying
- **Email or SNS notifications** post-processing
- Enterprise-scale support with usage-based logging

---

**_Thank you for exploring our project!_**
