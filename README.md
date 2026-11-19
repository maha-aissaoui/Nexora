# Nexora

### Intelligent Incident Detection and Controlled Workflow Automation

Nexora is an automated incident management and workflow orchestration system designed to monitor Ubuntu services, detect failures, recommend appropriate interventions, execute approved actions, and verify service recovery.

The project combines monitoring, REST APIs, workflow automation, and NoSQL data storage to provide a controlled and traceable approach to incident management.

---

## Project Overview

In a traditional environment, when an application or system service fails, an administrator must manually detect the problem, investigate its cause, choose an appropriate action, execute it, and verify whether the service has recovered.

Nexora aims to automate this process through a centralized platform.

The system:

1. Monitors the status of Ubuntu demonstration services.
2. Detects incidents automatically.
3. Reports incidents to a central backend.
4. Stores incident information and execution history in MongoDB.
5. Recommends compatible workflows based on incident characteristics and historical results.
6. Executes predefined actions after the required authorization.
7. Verifies the result and updates the incident status.

## Main Objectives

- Automate incident detection and reporting.
- Centralize incident management.
- Create configurable and reusable workflows.
- Provide recommendations based on historical execution data.
- Execute only predefined and authorized system actions.
- Verify service recovery before resolving an incident.
- Maintain a complete history of incidents and workflow executions.

---

## Architecture

Nexora follows a distributed architecture composed of a Windows host machine and an Ubuntu virtual machine.

```text
                    WINDOWS HOST
              ┌──────────────────────┐
              │    React Frontend    │
              │                      │
              │  Monitoring          │
              │  Incidents           │
              │  Workflows            │
              │  Executions           │
              └──────────┬───────────┘
                         │ HTTP / JSON
                         ▼
              ┌──────────────────────┐
              │   FastAPI Backend    │
              │                      │
              │  Incidents API       │
              │  Workflows API       │
              │  Suggestion Engine   │
              │  Execution Engine    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │       MongoDB        │
              │                      │
              │  incidents           │
              │  workflows           │
              │  executions          │
              └──────────────────────┘

                         ▲
                         │ HTTP / JSON
                         │ Authenticated
                         ▼

                    UBUNTU VM
              ┌──────────────────────┐
              │    FastAPI Agent     │
              │                      │
              │  Monitoring          │
              │  Incident Reporter   │
              │  Secure Actions      │
              │  Job Management      │
              └──────────┬───────────┘
                         │
              ┌──────────┴───────────┐
              ▼                      ▼
        ┌────────────┐         ┌────────────┐
        │ RH Service │         │Compta Service│
        │ Port 8101  │         │ Port 8102   │
        └────────────┘         └────────────┘
```

### Main Components

| Component | Responsibility |
|---|---|
| React Frontend | User interface and system monitoring |
| FastAPI Backend | Central APIs and workflow orchestration |
| FastAPI Agent | Monitoring and controlled Ubuntu actions |
| MongoDB | Persistent storage of incidents, workflows and executions |
| Suggestion Engine | Recommends compatible workflows using historical data |
| Workflow Engine | Executes workflow steps and tracks their results |

### Communication

- The React frontend communicates with the central Backend.
- The Ubuntu Agent communicates with the Backend through authenticated HTTP requests.
- The Backend interacts with MongoDB.
- The Backend calls the Agent when a workflow requires an action on Ubuntu.

---

## Technology Stack

| Area | Technologies |
|---|---|
| Frontend | React |
| Backend | Python, FastAPI |
| Agent | Python, FastAPI |
| Database | MongoDB |
| API Communication | REST, HTTP, JSON |
| Virtualization | Oracle VirtualBox |
| Operating System | Ubuntu Server |
| Service Management | systemd |
| Version Control | Git, GitHub |

---

## Core Features

### 1. Service Monitoring

The Agent periodically checks the status of the demonstration services.

It monitors:

- systemd service status.
- Application health endpoints.
- Application availability.
- Scheduled job execution status.

### 2. Incident Detection

Nexora identifies four incident types:

| Incident Type | Description |
|---|---|
| `SERVICE_STOPPED` | A systemd service is stopped or failed |
| `HEALTH_CHECK_FAILED` | The application health check returns an error |
| `APP_UNREACHABLE` | The application cannot be reached |
| `JOB_FAILED` | A scheduled job fails |

The monitoring system prioritizes `SERVICE_STOPPED` over health-check and availability errors to avoid generating contradictory incidents for the same observation.

### 3. Incident Management

The central Backend receives and stores incidents in MongoDB.

Each incident includes information such as:

- Incident ID
- Incident type
- Affected service
- Host ID
- Current status
- Creation timestamp
- Last observation timestamp
- Observations and history

The system also prevents duplicate open incidents for repeated observations of the same failure.

### 4. Workflow Management

Workflows represent predefined procedures that can be used to investigate or resolve incidents.

Each workflow contains:

- An identifier and version.
- An enabled status.
- A trigger condition.
- An execution mode.
- A sequence of predefined steps.

### 5. Suggestion Engine

The Suggestion Engine identifies workflows compatible with an incident.

It uses MongoDB historical execution data to provide useful information about previous workflow results and success rates.

Recommendations are limited to enabled and compatible workflows.

### 6. Controlled Execution

The Workflow Engine coordinates workflow execution.

Depending on the workflow configuration, execution may require:

- Manual selection.
- Explicit user approval.
- An authorized automatic mode.

Only predefined actions are allowed. Arbitrary Linux command execution is not supported.

### 7. Verification and History

After an intervention, Nexora checks whether the affected service has recovered.

An incident is marked `RESOLVED` only after successful verification.

Workflow executions and their results are stored in MongoDB.

---

## Demonstration Services

Nexora uses two simple Ubuntu applications as monitoring targets.

| Service | Description | Port |
|---|---|---|
| RH Service | Demonstration Human Resources application | 8101 |
| Compta Service | Demonstration Accounting application | 8102 |

These are test applications, not real business systems.

A scheduled accounting report job is also used to demonstrate job failure and retry scenarios.

---

## Predefined Workflows

The project includes five predefined workflows:

| Workflow | Purpose |
|---|---|
| Recovery RH | Restart the RH service and verify recovery |
| Diagnostic Compta | Investigate a Compta health-check failure |
| Retry Compta Job | Retry a failed accounting report job after approval |
| Restart RH with Approval | Require approval before restarting RH |
| Investigation Compta | Investigate an inaccessible Compta application |

The system must prevent competing RH workflows from executing simultaneously.

A diagnostic workflow must not report a successful repair if the incident remains unresolved.

---

## Repository Structure

```text
Nexora/
│
├── backend/
│   ├── main.py
│   ├── incidents/
│   ├── workflows/
│   ├── executions/
│   ├── suggestions/
│   └── shared/
│
├── agent/
│   ├── main.py
│   ├── monitoring.py
│   ├── reporter.py
│   ├── actions.py
│   └── jobs.py
│
├── demo_apps/
│   ├── rh/
│   │   └── app.py
│   │
│   └── compta/
│       ├── app.py
│       └── daily_report.py
│
├── deploy/
│   └── systemd/
│
├── frontend/
│   └── src/
│       └── pages/
│           ├── Monitoring.jsx
│           ├── Incidents.jsx
│           ├── Workflows.jsx
│           └── Executions.jsx
│
├── docs/
│   └── contracts/
│
├── scripts/
│
├── .gitignore
└── README.md
```

---

## Team Organization

The project is developed by two team members working on complementary modules.

Both members learn and use the same core technologies while developing different responsibilities.

### Person 1 — Monitoring and Incident Management

**Main responsibility:** Detect failures and manage incidents.

Tasks:

- Prepare an Ubuntu virtual machine.
- Develop the monitoring module.
- Implement incident detection.
- Develop the incident reporter.
- Create the central Incidents API.
- Manage the MongoDB incidents collection.
- Develop the Monitoring and Incidents React pages.
- Test incident detection, reporting and deduplication.

### Person 2 — Workflow Management and Automation

**Main responsibility:** Recommend and execute controlled interventions.

Tasks:

- Prepare an Ubuntu virtual machine identical to Person 1's environment.
- Develop secure Agent actions.
- Implement predefined job execution.
- Create the Workflows API.
- Develop the Workflow Engine.
- Implement the Suggestion Engine.
- Manage MongoDB workflows and executions collections.
- Develop the Workflows and Executions React pages.
- Test workflow execution and verification.

### Shared Responsibilities

Both members participate in:

- Defining API contracts and data schemas.
- Reviewing each other's code.
- Integrating their modules.
- Testing the complete system.
- Preparing the final demonstration.

---

## Development Environment

Each team member develops and tests a complete local copy of the system.

Each development environment contains:

- A Windows host machine.
- An Ubuntu Server VM using VirtualBox.
- A local MongoDB instance.
- A copy of the React frontend and FastAPI backend.

The Ubuntu VM uses two network adapters:

| Adapter | Purpose |
|---|---|
| NAT | Internet access for installing packages |
| Host-only | Private communication between Windows and Ubuntu |

The two development VMs do not form a cluster and do not synchronize with each other. GitHub is used to share the source code.

For the final demonstration, one Windows PC and its corresponding Ubuntu VM are selected.

---

## Getting Started

### Prerequisites

Install the following tools:

- Git
- Python 3
- Node.js and npm
- MongoDB
- Visual Studio Code
- Oracle VirtualBox
- Ubuntu Server

### Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd Nexora
```

### Backend Setup

```bash
cd backend

python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install the required dependencies:

```bash
pip install fastapi uvicorn pymongo httpx
```

Start the Backend:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API documentation:

```text
http://localhost:8000/docs
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Ubuntu Agent Setup

On the Ubuntu VM:

```bash
sudo apt update

sudo apt install -y python3 python3-venv python3-pip git curl openssh-server
```

Clone the repository and prepare the Agent environment:

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd Nexora/agent

python3 -m venv .venv
source .venv/bin/activate

pip install fastapi uvicorn httpx
```

The Agent is configured to communicate with the central Backend through the private Host-only network.

**Note:** These commands provide the initial development setup. Environment variables, MongoDB configuration, application dependencies and service configuration must be completed according to the implementation.

---

## Security Considerations

Security is an essential part of Nexora.

The project follows these principles:

- The Agent and Backend communicate using authentication tokens.
- Secrets are stored outside the Git repository.
- The Agent accepts only predefined services and jobs.
- Arbitrary shell commands are prohibited.
- The Agent runs using a dedicated non-root technical user.
- Privileges are limited to explicitly authorized actions.
- HTTP requests use timeouts and structured error handling.
- Each action and execution is logged.
- The laboratory APIs are restricted to the private Host-only network.

Never commit passwords, tokens, private keys or other secrets to GitHub.

---

## Testing and Validation

The final system must demonstrate the following scenarios:

1. Create a workflow before an incident occurs.
2. Stop the RH service and detect a `SERVICE_STOPPED` incident.
3. Select the Recovery RH workflow and verify service recovery.
4. Trigger a Compta health-check failure.
5. Execute the Diagnostic Compta workflow.
6. Simulate a failed accounting report job.
7. Reject a retry approval and verify that no job is launched.
8. Approve a retry and verify the result.
9. Require approval before restarting RH.
10. Verify that an unauthorized service cannot be restarted.
11. Test Backend unavailability and Agent retry behavior.
12. Verify that repeated monitoring cycles do not create duplicate open incidents.
13. Verify MongoDB execution history and workflow success statistics.
14. Test the complete integrated system.

---

## Project Scope and Limitations

Nexora focuses on controlled automation for Ubuntu demonstration services.

The following elements are explicitly outside the project scope:

- Kubernetes and cluster management.
- Real Human Resources or Accounting business applications.
- Arbitrary Linux command execution.
- Mandatory Machine Learning implementation.
- Synchronization between the two development VMs.

The Suggestion Engine relies on predefined compatibility rules and MongoDB historical execution data.

---

## Expected Result

At the end of the project, Nexora should provide a functional platform where a user can:

- Monitor Ubuntu demonstration services.
- Detect and visualize incidents.
- Consult incident details and history.
- Receive workflow recommendations.
- Approve or launch predefined interventions.
- Track workflow execution steps.
- Verify whether an incident has actually been resolved.

The final demonstration should show the complete process:

**Incident Detection → Backend Reporting → MongoDB Storage → Workflow Recommendation → Authorized Execution → Recovery Verification**

---

## Project Status

**Status:** In Development

**Project Type:** Academic Project — NoSQL and Web Services

**Repository:** Nexora

