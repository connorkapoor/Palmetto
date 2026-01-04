# Contributing to Palmetto

Thank you for your interest in contributing to Palmetto! This document provides guidelines for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Code Guidelines](#code-guidelines)
- [Pull Request Process](#pull-request-process)
- [Adding New Feature Recognizers](#adding-new-feature-recognizers)

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally: `git clone https://github.com/your-username/palmetto.git`
3. Add the upstream repository: `git remote add upstream https://github.com/original-owner/palmetto.git`
4. Create a new branch for your feature: `git checkout -b feature/my-new-feature`

## Development Setup

Please follow the setup instructions in [README.md](README.md) to get your development environment running. Key steps:

1. **Build C++ Engine**: Requires OpenCASCADE 7.8+ and CMake 3.20+
2. **Backend Setup**: Python 3.10+ with FastAPI
3. **Frontend Setup**: Node.js 18+ with React/Vite

See [CLAUDE.md](CLAUDE.md) for detailed development workflow and architecture documentation.

## How to Contribute

We welcome contributions in several areas:

### Bug Reports
- Use GitHub Issues to report bugs
- Include steps to reproduce, expected behavior, and actual behavior
- Attach sample STEP files if applicable
- Include system information (OS, OpenCASCADE version, etc.)

### Feature Requests
- Use GitHub Issues with the "enhancement" label
- Describe the feature and its use case
- Discuss implementation approach if you have ideas

### Code Contributions
- Bug fixes
- New feature recognizers (holes, pockets, bosses, ribs, etc.)
- Performance improvements
- Documentation improvements
- Test coverage

## Code Guidelines

### C++ Engine (core/)

**Style:**
- Follow existing code style (or use `clang-format` if available)
- Use meaningful variable names
- Add comments for complex algorithms
- Use OpenCASCADE best practices

**Architecture:**
- All recognizers must operate on the AAG (Attributed Adjacency Graph)
- Keep recognizers independent and modular
- Export results to JSON via `json_exporter.cpp`
- Add CLI flags in `main.cpp` for new recognizers

**Testing:**
- Test with sample models in `examples/test-models/`
- Verify AAG export includes new attributes
- Check for memory leaks with Valgrind (if available)

### Python Backend (backend/)

**Style:**
- Use Black for formatting: `black .`
- Use Ruff for linting: `ruff check .`
- Follow PEP 8 conventions
- Add type hints where appropriate

**Code Quality:**
```bash
cd backend
black .           # Format code
ruff check .      # Lint
mypy app          # Type check (optional)
pytest            # Run tests (when available)
```

### Frontend (frontend/)

**Style:**
- Use Prettier for formatting: `npm run format`
- Use ESLint for linting: `npm run lint`
- Follow React best practices
- Use TypeScript types consistently

**Code Quality:**
```bash
cd frontend
npm run lint      # ESLint
npm run format    # Prettier
npm run build     # Verify production build works
```

## Pull Request Process

1. **Update your fork** with the latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Make your changes** in your feature branch

3. **Test thoroughly**:
   - Build C++ engine successfully
   - Verify backend starts without errors
   - Test frontend in development mode
   - Try production builds if applicable

4. **Commit with clear messages**:
   ```bash
   git add .
   git commit -m "Add cylindrical boss recognizer with diameter detection"
   ```
   Follow conventional commit format when possible:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `refactor:` for code refactoring
   - `test:` for adding tests

5. **Push to your fork**:
   ```bash
   git push origin feature/my-new-feature
   ```

6. **Create Pull Request** on GitHub:
   - Provide a clear title and description
   - Reference any related issues
   - Explain what was changed and why
   - Include screenshots for UI changes
   - Mention if breaking changes are introduced

7. **Respond to feedback**:
   - Address reviewer comments
   - Make requested changes
   - Update PR with additional commits

## Adding New Feature Recognizers

New recognizers are highly valuable contributions! Here's the workflow:

### 1. C++ Recognizer Implementation

Create `core/apps/palmetto_engine/my_feature_recognizer.{h,cpp}`:

```cpp
// my_feature_recognizer.h
#pragma once
#include "aag.h"
#include <vector>

struct MyFeature {
    std::vector<int> face_ids;
    double characteristic_dimension;
    // Add other geometric parameters
};

class MyFeatureRecognizer {
public:
    MyFeatureRecognizer(const AAG& aag);
    std::vector<MyFeature> recognize();
private:
    const AAG& aag_;
    // Helper methods
};
```

### 2. Add to Build System

Update `core/CMakeLists.txt`:
```cmake
set(PALMETTO_ENGINE_SOURCES
    # ... existing files ...
    apps/palmetto_engine/my_feature_recognizer.cpp
)
```

### 3. Register in Engine

Update `core/apps/palmetto_engine/engine.cpp`:
- Add recognition method
- Call in appropriate workflow
- Store results

### 4. Export to JSON

Update `core/apps/palmetto_engine/json_exporter.cpp`:
- Export feature objects to `features` array
- Add boolean attribute `is_my_feature_face` to faces
- Include geometric parameters

### 5. Add CLI Flag

Update `core/apps/palmetto_engine/main.cpp`:
```cpp
if (cxxopts["enable-my-feature"].as<bool>()) {
    engine.recognize_my_features();
}
```

### 6. Backend Integration

Update `backend/app/core/cpp_engine.py`:
- Add parameter for enabling your recognizer
- Pass CLI flag to engine

### 7. Frontend Display

Update `frontend/src/components/ResultsPanel.tsx`:
- Add section for your feature type
- Display feature list with parameters
- Enable click-to-highlight

### 8. Natural Language Support

Update `backend/app/query/query_parser.py`:
- Add example queries for your feature
- Add fallback detection for common terms

### 9. Documentation

- Add recognizer to README.md feature list
- Document in CLAUDE.md for future developers
- Include sample STEP file demonstrating the feature

## Code Review

All submissions require review. We use GitHub pull requests for this purpose. Be patient and responsive to feedback.

## Community

- Be respectful and constructive
- Help others in issues and discussions
- Share interesting use cases or examples

## Questions?

- Open a GitHub Discussion for general questions
- Use GitHub Issues for bug reports and feature requests
- Check [CLAUDE.md](CLAUDE.md) for development details

Thank you for contributing to Palmetto!
