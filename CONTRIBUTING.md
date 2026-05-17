# Contributing to NEXUS Agent

Thank you for your interest in contributing to NEXUS Agent!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch: `git checkout -b feature/my-feature`
4. Make your changes
5. Run tests: `pytest tests/ -v`
6. Submit a pull request

## Development Setup

```bash
# Backend
cd NexusAgent
pip install -e ".[dev]"

# Frontend
npm install

# Run in development
nexus serve --dev
npm run dev
```

## Code Style

### Python
- Follow PEP 8
- Use type hints everywhere
- Use Pydantic for data models
- Async/await for all I/O operations
- Thread-safe singletons with locks

### TypeScript
- Strict TypeScript (`strict: true`)
- No `any` types (except navigator.deviceMemory)
- All logging through `createLogger()`
- Zustand for state management

## Testing

- **Minimum coverage**: 80%
- **TDD required**: Write tests first, then implement
- **Test types**: Unit, integration, E2E

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=nexus --cov-report=html

# Run specific module
pytest tests/plugins/ -v
```

## Commit Messages

Use Conventional Commits:

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

## Pull Request Process

1. Update documentation if needed
2. Add tests for new features
3. Ensure all tests pass
4. Request review from maintainers

## Security

- Never commit secrets (API keys, passwords)
- Use environment variables for configuration
- Report security issues privately

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
