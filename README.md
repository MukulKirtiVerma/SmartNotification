# Smart Notification System

A comprehensive agent-based notification system that adapts to user behavior and preferences to deliver personalized notifications across multiple channels.

## Features

- **User Behavior Analysis**: Tracks user interactions with notifications across all channels
- **Adaptive Notification Delivery**: Dynamically adjusts notification frequency based on engagement
- **Notification Type Analysis**: Categorizes and personalizes notifications by type (shipment, packing, delivery)
- **Multi-Channel Support**: Supports email, mobile push, SMS, and dashboard notifications
- **AI-Powered Decision Engine**: Learns from user behavior to optimize notification strategies

## Architecture

The system is built on a multi-agent architecture with four main layers:

1. **Data Collection Layer**
   - Dashboard Tracker Agent
   - Email Engagement Agent
   - Mobile App Events Agent
   - SMS Interaction Agent

2. **Analysis Layer**
   - Frequency Analysis Agent
   - Type Analysis Agent
   - Channel Analysis Agent

3. **AI Decision Engine**
   - User Profile Service
   - Recommendation System
   - A/B Testing Module

4. **Notification Management Layer**
   - Email Service
   - Push Notification Service
   - SMS Gateway
   - Dashboard Alert System

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL
- Redis
- MongoDB

### Installation

1. Clone the repository:
git clone [https://github.com/MukulKirtiVerma/smart-notification-system.git](https://github.com/MukulKirtiVerma/SmartNotification.git)
cd smart-notification-system

2. Set up a virtual environment:
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate

3. Install dependencies:
pip install -r requirements.txt

4. Configure the system:
- Update database connection details in `config/config.py`
- Adjust notification settings if needed
- Review agent configuration parameters

5. Set up the databases:
python scripts/setup_database.py

6. Generate dummy data (optional):
python scripts/generate_dummy_data.py

# Configuration Details

### Database Configuration

Edit `config/config.py` to update your database connection strings:


### PostgreSQL configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/notification_system")

### Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

### MongoDB configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/notification_system")



You can either modify these values directly or set environment variables.

# Agent Configuration
The agent check interval determines how frequently agents process data:

AGENT_CHECK_INTERVAL = 60  


# Notification settings
MAX_NOTIFICATIONS_PER_DAY = 10

NOTIFICATION_COOLDOWN_MINUTES = 30

# Running the Application

Start the application:
python app/main.py

The API will be available at: http://localhost:8000/api/v1/

You can view the API documentation at: http://localhost:8000/api/docs

# Docker Setup

You can also run the entire system using Docker:

Make sure Docker and Docker Compose are installed on your system
Build and start the containers:
docker-compose up -d

The application will be available at: http://localhost:8000/api/v1/

# API Endpoints
The system exposes several RESTful endpoints:
```
/api/v1/users/ - User management

/api/v1/notifications/ - Create and query notifications

/api/v1/engagements/ - Record notification engagements

/api/v1/preferences/ - Manage notification preferences

/api/v1/ab-tests/ - A/B test management

/api/v1/dashboard-alerts/ - Dashboard alert management

/api/v1/system/status - System status information
```
# Example: Creating a Notification

To create a notification using the API:
bashcurl -X POST "http://localhost:8000/api/v1/notifications/" \
```
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "type": "shipment",
    "channel": "email",
    "title": "Your order has shipped",
    "content": "Your order #12345 has shipped and will arrive soon."
  }'
 ```

# System Components

## Data Collection Layer
This layer captures user interaction data from various channels:

Dashboard Tracker Agent: Monitors user activity on dashboards
Email Engagement Agent: Tracks opens, clicks, and forwards for emails
Mobile App Events Agent: Monitors push notification interaction
SMS Interaction Agent: Records delivery confirmations and responses

## Analysis Layer
Processes the collected data to identify patterns and preferences:

Frequency Analysis Agent: Evaluates optimal notification timing and frequency
Type Analysis Agent: Determines user preferences for different notification categories
Channel Analysis Agent: Identifies which delivery channels yield highest engagement

## Decision Engine
Makes intelligent decisions about notification delivery:

User Profile Service: Maintains dynamic user profiles with preference scores
Recommendation System: Uses ML models to determine optimal notification strategy
A/B Testing Module: Continuously tests and refines notification strategies

## Notification Management Layer
Handles the actual delivery of notifications:

## Email Service: Manages email creation and delivery
Push Notification Service: Handles mobile app notifications
SMS Gateway: Controls SMS notification delivery
Dashboard Alert System: Manages in-app and dashboard notifications

# Troubleshooting
## Common Issues

### Database Connection Problems:

Ensure your database services are running
Verify connection strings in config.py
Check database user permissions


### Agent Not Processing:

Check system logs in the logs directory
Verify agent is registered correctly
Look for exceptions in agent processing


### API Connection Issues:

Confirm the application is running
Check the port is not in use
Verify firewall settings



# Logs
Application logs are stored in the logs directory. Check these files for detailed information about system operations and errors.



This project is licensed under the MIT License - see the LICENSE file for details.

# Acknowledgments
This project implements research from the field of adaptive notification systems and user behavior analysis.
