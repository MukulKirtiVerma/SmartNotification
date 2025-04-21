import os
import sys


def create_project_structure():
    # Base directories
    directories = [
        "app",
        "app/agents",
        "app/agents/data_collection",
        "app/agents/analysis",
        "app/agents/decision_engine",
        "app/agents/notification",
        "app/api",
        "app/db",
        "app/utils",
        "config",
        "logs",
        "scripts",
        "tests"
    ]

    # Create directories
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")

    # Create __init__.py files
    init_files = [
        "__init__.py",
        "app/__init__.py",
        "app/agents/__init__.py",
        "app/agents/data_collection/__init__.py",
        "app/agents/analysis/__init__.py",
        "app/agents/decision_engine/__init__.py",
        "app/agents/notification/__init__.py",
        "app/api/__init__.py",
        "app/db/__init__.py",
        "app/utils/__init__.py",
        "config/__init__.py",
        "scripts/__init__.py",
        "tests/__init__.py"
    ]

    for init_file in init_files:
        with open(init_file, 'w') as f:
            f.write("# Empty init file to make the directory a package\n")
        print(f"Created file: {init_file}")

    # Create other files
    files = [
        # Main project files
        "README.md",
        "Dockerfile",
        "docker-compose.yml",
        "requirements.txt",

        # Config files
        "config/config.py",
        "config/constants.py",

        # Database files
        "app/db/database.py",
        "app/db/models.py",

        # Agents
        "app/agents/agent_registry.py",
        "app/agents/base_agent.py",

        # Data Collection Agents
        "app/agents/data_collection/dashboard_tracker.py",
        "app/agents/data_collection/email_engagement.py",
        "app/agents/data_collection/mobile_app_events.py",
        "app/agents/data_collection/sms_interaction.py",

        # Analysis Agents
        "app/agents/analysis/frequency_analysis.py",
        "app/agents/analysis/type_analysis.py",
        "app/agents/analysis/channel_analysis.py",

        # Decision Engine
        "app/agents/decision_engine/user_profile.py",
        "app/agents/decision_engine/recommendation.py",
        "app/agents/decision_engine/ab_testing.py",

        # Notification Services
        "app/agents/notification/email_service.py",
        "app/agents/notification/push_notification.py",
        "app/agents/notification/sms_gateway.py",
        "app/agents/notification/dashboard_alert.py",

        # API
        "app/api/routes.py",
        "app/api/schemas.py",

        # Utils
        "app/utils/logger.py",
        "app/utils/helpers.py",

        # Main application
        "app/main.py",

        # Scripts
        "scripts/setup_database.py",
        "scripts/generate_dummy_data.py",

        # Tests
        "tests/conftest.py",
        "tests/test_data_collection.py",
        "tests/test_analysis.py",
        "tests/test_decision_engine.py",
        "tests/test_notification.py"
    ]

    for file_path in files:
        with open(file_path, 'w') as f:
            f.write(f"# {file_path}\n# Add the code for this file here\n")
        print(f"Created file: {file_path}")

    print("\nProject structure created successfully!")
    print("Next steps: Add the code to each file from the provided implementation.")


if __name__ == "__main__":
    print("Creating Smart Notification System project structure...")
    create_project_structure()