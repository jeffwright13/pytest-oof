# Pytest-OOF (Objects of Fields) Project Architecture

## Project Overview
Pytest-OOF is a sophisticated pytest plugin designed to provide advanced test result tracking, analysis, and insights for software testing processes.

## Core Modules and Their Responsibilities

### 1. `plugin.py`
**Primary Responsibility**: Core pytest plugin implementation and test lifecycle management

**Key Functions**:
- Hooks into pytest's test execution lifecycle
- Captures and processes test results
- Manages test session metadata
- Handles test outcome tracking and rerun logic

**Key Features**:
- Tracks test outcomes across different stages (setup, call, teardown)
- Captures detailed test execution information from internal pytest objects (TestReport)

### 2. `db.py`
**Primary Responsibility**: Database operations and test result persistence

**Key Functions**:
- SQLite database management
- Test result storage and retrieval
- Advanced analytics generation
- Session and test result tracking

**Advanced Analytics Functions**:
- `get_rerun_patterns()`: Analyzes test rerun behaviors
- `get_flaky_tests()`: Identifies inconsistent test behaviors
- `get_stability_metrics()`: Generates test suite stability insights
- `get_recent_failures()`: Tracks recent test failures

### 3. `models.py`
**Primary Responsibility**: Data model definitions for test results and sessions

**Key Classes**:
- `TestResult`: Represents individual test execution details
- `SessionMetadata`: Captures test session metadata
- `TestSessionStats`: Aggregates test session statistics
- `Results`: Comprehensive container for test session information

### 4. `constants.py`
**Primary Responsibility**: Defines project-wide constants and configuration defaults

**Key Definitions**:
- Default database paths
- Configuration settings
- Constant values used across the project

### 5. `cli/test_mode.py` and `test_mode.py`
**Primary Responsibility**: Command-line interface and test mode implementations

**Features**:
- Provides CLI tools for test management
- Implements specific test execution modes
- Handles user interactions and configuration

### 6. `scripts/generate_historical_data.py`
**Primary Responsibility**: Generates synthetic test data for analysis and testing

**Key Features**:
- Creates realistic test result datasets
- Simulates complex test scenarios
- Helps in testing and validating the analytics functions

## Architecture Patterns

### 1. Pytest Plugin Architecture
- Uses pytest's hook system for deep integration
- Extends pytest's default behavior without modifying core functionality

### 2. Database-Driven Analytics
- SQLite as the primary data storage
- Complex query-based analytics
- Supports historical data tracking and analysis

### 3. Modular Design
- Separation of concerns between plugin, database, and models
- Extensible architecture allowing easy additions and modifications

## Data Flow

1. Test Execution
   ↓
2. Result Capture (plugin.py)
   ↓
3. Database Persistence (db.py)
   ↓
4. Analytics Generation

## Key Design Principles
- Minimal performance overhead
- Comprehensive test result tracking
- Advanced analytics capabilities
- Flexible configuration

## Technology Stack
- Python 3.11+
- pytest
- SQLite
- SQLAlchemy (minimal usage)

## Performance Considerations
- Lazy loading of analytics
- Efficient database queries
- Minimal runtime impact on test execution

## Future Expansion Points
- Machine learning-based test prediction
- Enhanced visualization tools
- More granular test insights
- Cloud/distributed testing support

## Contribution Guidelines
1. Maintain modular design
2. Keep performance overhead minimal
3. Comprehensive test coverage
4. Follow existing architectural patterns

## Project Guidelines and Critical Feedback

### Mocking and Testing Guidelines

#### Pytest-Mock Best Practices

1. **Library Preference**: Always use `pytest-mock` instead of `unittest.mock`

2. **Benefits of pytest-mock**:
   - Superior pytest integration
   - Automatic fixture cleanup
   - Consistent mocking patterns
   - Built-in spy functionality
   - Enhanced error messages and debugging

3. **Recommended Practices**:
   - Use the `mocker` fixture provided by pytest-mock
   - Prefer `mocker.patch` over direct patching
   - Utilize `mocker.spy` for verifying call counts and arguments
   - Leverage automatic teardown capabilities

### Critical Code Formatting Feedback

#### Style and Formatting Principles

1. **Formatting Approach**
   - NEVER modify source code functionality to address style issues
   - Use dedicated code formatters (ruff, black) for style corrections

2. **Potential Risks of Improper Formatting**
   - Changing code behavior during style modifications
   - Introducing unintended bugs and regressions
   - Undermining code review processes

3. **Recommended Workflow**
   - Separate functional changes from formatting changes
   - Use `ruff` and `black` to handle style consistently
   - Preserve original code behavior during all modifications

#### Example Bad Practice
```python
# BAD: Modifying functionality to fix style
def some_function():
    # Unnecessarily restructuring code to reduce line length
    result = very_long_function_name_with_many_arguments(
        arg1, arg2, arg3  # Changing logic just to fit style guide
    )
```

#### Correct Approach
```python
# GOOD: Use formatters, preserve logic
def some_function():
    result = very_long_function_name_with_many_arguments(arg1, arg2, arg3)
```

**Remember**: Code style should enhance readability without compromising functionality.

## Licensing
[Include your project's license information]

---

**Note**: This architecture is a living document. Always refer to the latest version of the codebase for the most up-to-date information.
