````markdown
# Contributing to AI Workflow Framework

Thank you for your interest in contributing to the AI Workflow Framework (AWF).

AI Workflow Framework is an open-source, self-hosted framework for building,
executing, scheduling, and monitoring AI-powered workflows.

Contributions, bug reports, feature requests, documentation improvements,
and technical discussions are welcome.

## Code of Conduct

Please be respectful and constructive when interacting with other
contributors and maintainers.

## Before Contributing

Before starting significant work, please:

1. Check the existing issues.
2. Search for related feature requests or bug reports.
3. Open an issue for major changes before implementing them.
4. Explain the proposed change and its motivation.

Small documentation fixes and clearly scoped bug fixes can be submitted
directly as pull requests.

## Development Setup

The project is designed to run using Docker.

Please refer to the main `README.md` for the current installation,
configuration, and development instructions.

The project currently consists primarily of:

- React frontend
- React Flow workflow editor
- FastAPI backend
- PostgreSQL database
- Docker-based development environment
- Optional Ollama local LLM inference

## Project Structure

```text
ai-workflow-saas/
├── backend/
├── frontend/
├── screenshots/
├── README.md
├── CITATION.cff
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── docker-compose.yml
````

## Reporting Bugs

Please create a GitHub issue and include:

* A clear description of the problem.
* Steps to reproduce the problem.
* Expected behavior.
* Actual behavior.
* Relevant error messages or logs.
* Operating system.
* Docker version, where applicable.
* Browser and version, where applicable.
* Relevant screenshots, if useful.

Please remove API keys, passwords, tokens, personal information, and
other sensitive information before posting logs.

## Feature Requests

Feature requests are welcome.

Please describe:

* The problem the feature would solve.
* The proposed behavior.
* Why the feature would be useful.
* Any alternative approaches you considered.

For larger architectural changes, please open a discussion or issue before
starting implementation.

## Pull Requests

Before submitting a pull request:

1. Make sure your changes are focused on a specific issue or improvement.
2. Test the changes locally.
3. Update documentation when necessary.
4. Add or update tests when applicable.
5. Make sure no credentials or secrets are committed.
6. Keep unrelated changes out of the pull request.

Pull requests should explain:

* What was changed.
* Why it was changed.
* How it was tested.
* Any limitations or known issues.

## Testing

Contributors should test affected functionality before submitting a pull
request.

As the project evolves, automated backend, frontend, integration, and
workflow execution tests will be expanded.

## Security

Do not report security vulnerabilities through public GitHub issues.

If a security issue is discovered, please contact the project maintainer
privately before publicly disclosing the vulnerability.

Never commit:

* API keys
* Passwords
* OAuth secrets
* Access tokens
* Private keys
* Database credentials
* `.env` files containing secrets

## Documentation

Documentation improvements are welcome.

If a change modifies user-facing behavior, please update the relevant
documentation in the same pull request.

## License

By contributing to this project, you agree that your contributions will be
licensed under the Apache License 2.0.

See the `LICENSE` file for the complete license text.

## Questions

For general questions, feature discussions, and project improvements,
please use GitHub Issues or Discussions where available.

Thank you for contributing to AI Workflow Framework.

```
```
