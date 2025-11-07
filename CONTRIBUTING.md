# Contributing to PrizmAI

Thank you for your interest in contributing to the PrizmAI project! We value all contributions, whether it's fixing bugs, improving documentation, or suggesting new features. This document outlines the process for contributing to make it as smooth as possible.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Contribution Process](#contribution-process)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Feature Requests](#feature-requests)
- [Community](#community)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone. We expect all contributors to:

- Be respectful and considerate in communication
- Accept constructive criticism graciously
- Focus on what's best for the community
- Show empathy towards other community members

## Getting Started

1. **Fork the repository** to your GitHub account
2. **Clone your fork** to your local machine
3. **Set up the development environment** (see below)
4. **Create a new branch** for your contribution
5. Make your changes and commit them with clear messages
6. Push your branch to your forked repository
7. Create a pull request to the main repository

## Development Environment

### Prerequisites

- Python 3.9 or higher
- pip (Python package installer)
- Git

### Setup

```bash
# Clone your forked repository
git clone https://github.com/your-username/Digital_Kanban_Board.git
cd Digital_Kanban_Board

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create a superuser (for admin access)
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`.

## Contribution Process

1. **Check existing issues** to see if your contribution is already being worked on or has been discussed
2. **Create or claim an issue** before starting work on significant changes
3. **Pull the latest changes** from the main branch before starting work
4. **Create a feature branch** with a descriptive name (e.g., `feature/add-task-filtering`)
5. **Make focused changes** that address the specific issue
6. **Write tests** for your changes (if applicable)
7. **Update documentation** as needed
8. **Submit a pull request** with a clear description of the changes

## Pull Request Guidelines

When submitting a pull request:

1. **Reference the related issue** in the PR description (e.g., "Fixes #123")
2. **Provide a clear description** of what the changes do and why they're needed
3. **Include screenshots** for UI changes
4. **Ensure all tests pass** and add new tests as appropriate
5. **Keep the scope focused** - if you find other issues, create separate PRs
6. **Be responsive** to feedback and be willing to make changes if requested

## Coding Standards

We follow standard conventions for Python, Django, HTML, CSS, and JavaScript:

- **Python**: Follow PEP 8 style guide
- **Django**: Follow Django's best practices
- **HTML/CSS**: Use consistent indentation and descriptive class names
- **JavaScript**: Use ES6+ features and avoid global variables

### Style Guides

- Use meaningful variable and function names
- Include docstrings for functions and classes
- Write comments for complex code sections
- Keep functions small and focused
- Maintain consistent whitespace and indentation

## Testing

We value tests that ensure the application works correctly:

- **Unit tests**: Test individual functions and methods
- **Integration tests**: Test how components work together
- **UI tests**: Test user interfaces (if applicable)

To run tests:

```bash
python manage.py test
```

## Documentation

Good documentation is essential for a successful project:

- Update README.md when adding significant features
- Document models, views, and other components with docstrings
- Add comments to explain complex logic
- Update user guides when changing user-facing features

## Issue Reporting

When reporting issues:

1. Use a clear and descriptive title
2. Provide steps to reproduce the issue
3. Describe the expected behavior and what actually happened
4. Include environment details (OS, browser, etc.)
5. Add screenshots or error messages if available

## Feature Requests

For feature requests:

1. Clearly describe the feature and the problem it solves
2. Explain how it benefits the project and users
3. Suggest an implementation approach if possible
4. Be open to discussion and refinement

## Community

Join our community discussions:

- GitHub Discussions for feature ideas and general questions
- Discord for real-time chat and collaboration
- Monthly video meetings (check the community calendar)

---

Thank you for contributing to PrizmAI! Your efforts help make this project better for everyone.