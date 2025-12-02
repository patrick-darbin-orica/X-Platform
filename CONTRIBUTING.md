# Contributing to XStem Navigation System

Thank you for contributing to the XStem project! This guide will help you collaborate effectively with the team.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Branching Strategy](#branching-strategy)
4. [SSH Collaboration Guidelines](#ssh-collaboration-guidelines)
5. [Code Standards](#code-standards)
6. [Testing Requirements](#testing-requirements)
7. [Commit Message Format](#commit-message-format)
8. [Pull Request Process](#pull-request-process)
9. [Issue Tracking](#issue-tracking)
10. [Code Review Guidelines](#code-review-guidelines)

## Getting Started

### Initial Setup

1. Clone the repository (if not already done):
   ```bash
   cd ~/Amiga/xstem
   ```

2. Run the setup script to install git hooks and commit template:
   ```bash
   ./setup-hooks.sh
   ```

3. Verify your git configuration:
   ```bash
   git config --list | grep -E '(user.name|user.email|commit.template)'
   ```

4. Install recommended VSCode extensions (if using VSCode):
   - Open the repository in VSCode
   - When prompted, install recommended extensions
   - Or manually: `Ctrl+Shift+P` → "Extensions: Show Recommended Extensions"

### Dependencies

Ensure you have all required dependencies installed:
```bash
pip install farm-ng-amiga farm-ng-core opencv-python numpy pandas pyyaml pydantic pytest
```

## Development Workflow

### Daily Workflow

**Morning:**
1. Check team chat for ongoing work
2. Pull latest changes: `git pull origin main`
3. Announce what you're working on
4. Create or switch to your feature branch

**During Development:**
1. Make focused, incremental commits
2. Commit every 30 minutes to avoid losing work
3. Pull frequently: `git pull --rebase origin main` (every 1-2 hours)
4. Run tests before pushing

**End of Day:**
1. Commit all work (even WIP)
2. Push to remote: `git push`
3. Update any related issue status
4. Post progress summary in team chat

### Standard Development Process

1. **Pull latest changes:**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes:**
   - Write code following our standards (see below)
   - Add/update tests
   - Update documentation if needed

4. **Commit frequently:**
   ```bash
   git add <files>
   git commit  # Template will auto-populate
   ```

5. **Push to remote:**
   ```bash
   git push -u origin feature/your-feature-name
   ```

6. **Create a Pull Request:**
   - Go to GitHub
   - Create PR from your branch to `main`
   - Fill out the PR template
   - Request review from at least one team member

7. **Address review feedback:**
   - Make requested changes
   - Push updates to the same branch
   - Respond to comments

8. **Merge:**
   - Once approved, merge via GitHub
   - Delete the feature branch
   - Pull latest main locally

## Branching Strategy

### Branch Naming Convention

Use descriptive branch names with the following prefixes:

- `feature/description` - New features or enhancements
  - Example: `feature/visual-servoing`
  - Example: `feature/add-recovery-logic`

- `fix/description` - Bug fixes
  - Example: `fix/can-communication-timeout`
  - Example: `fix/filter-convergence-issue`

- `refactor/description` - Code refactoring (no behavior change)
  - Example: `refactor/vision-system-cleanup`

- `test/description` - Adding or updating tests
  - Example: `test/navigation-unit-tests`

- `docs/description` - Documentation updates
  - Example: `docs/update-installation-guide`

- `dev/name/description` - Personal development branches (for SSH sharing)
  - Example: `dev/patrick/experiment-hole-detection`
  - Example: `dev/alice/debug-canbus`

### Branch Guidelines

- **Keep branches short-lived:** Merge within 2-3 days when possible
- **One feature per branch:** Don't combine unrelated changes
- **Rebase before merging:** Keep history clean with `git pull --rebase`
- **Delete after merge:** Clean up merged branches promptly

## SSH Collaboration Guidelines

Since we share SSH access to the development machine, follow these rules to avoid conflicts:

### Communication is Critical

**Before starting work:**
1. Post in team chat: "Working on [module/file] for [feature]"
2. Check if anyone else is working on the same area
3. Wait for acknowledgment before proceeding

**Example chat messages:**
```
"Working on navigation/path_planner.py to add recovery logic"
"Editing vision/detector.py for the next 1-2 hours"
"Done with control/stemming_module.py, pushed to dev/alice/stemming-improvements"
```

### Conflict Prevention Strategies

1. **Claim Your Work Area**
   - Announce which files/modules you'll be editing
   - Avoid editing the same file as another team member simultaneously

2. **Use Personal Dev Branches for WIP**
   ```bash
   # For experimental or long-running work
   git checkout -b dev/yourname/feature-name
   ```

3. **Work in Modular Boundaries**
   - Navigation team → `navigation/`, `utils/track_builder.py`
   - Vision team → `vision/`, camera integration
   - Control team → `control/`, `hardware/`
   - Coordinate when work crosses boundaries

4. **Frequent Pulls**
   ```bash
   # Pull every hour, or before making significant changes
   git pull --rebase origin main
   ```

5. **Atomic Commits**
   - Commit small, complete changes frequently (every 30 min)
   - Easier to merge and resolve conflicts
   - Better rollback capability

6. **Lock Files Informally**
   - If doing major refactoring, claim the file explicitly
   - Others should wait or coordinate directly

### If Conflicts Occur

1. **Stop and communicate immediately**
   - Don't try to resolve alone if unsure
   - Hop on a quick call if needed

2. **Identify the conflict:**
   ```bash
   git status  # See conflicting files
   git diff    # See what changed
   ```

3. **Discuss resolution approach:**
   - Who has the more recent/correct changes?
   - Can we merge both sets of changes?
   - Should one person revert and reapply?

4. **Resolve the conflict:**
   - Use VSCode's merge editor (recommended)
   - Or manually edit conflict markers
   - Or use: `git mergetool`

5. **Test thoroughly:**
   ```bash
   # Run tests after resolving
   ./scripts/run-tests.sh unit
   python main.py --config config/navigation_config.yaml  # Smoke test
   ```

6. **Commit the resolution:**
   ```bash
   git add <resolved-files>
   git commit  # Git will auto-generate merge commit message
   ```

### Remote Work Best Practices

- **Use screen/tmux:** Keep sessions alive if SSH disconnects
- **Background processes:** Be careful with long-running processes that block files
- **Permissions:** Don't change file permissions without team discussion
- **Shared resources:** Coordinate hardware access (CAN bus, cameras)

## Code Standards

### Python Style Guide

We follow PEP 8 with these specific guidelines:

1. **Use flake8 for linting:**
   - Configuration in `.flake8`
   - Pre-commit hook will check automatically
   - Fix all warnings before committing

2. **Line length:**
   - Maximum 88 characters (Black formatter default)
   - Docstrings wrap at 72 characters

3. **Type hints:**
   ```python
   def plan_segment(self, start: Pose3F64, end: Pose3F64) -> Track:
       """Plan a track segment between two poses."""
       ...
   ```

4. **Docstrings:**
   - All public functions, classes, and modules
   - Use Google or NumPy style
   ```python
   def execute_track(self, track: Track) -> bool:
       """Execute a navigation track.

       Args:
           track: Track object containing waypoints and metadata

       Returns:
           True if track completed successfully, False otherwise
       """
   ```

5. **Naming conventions:**
   - `snake_case` for functions and variables
   - `PascalCase` for classes
   - `UPPER_CASE` for constants
   - Descriptive names: `hole_position` not `hp`

6. **Imports:**
   ```python
   # Standard library
   import asyncio
   import logging
   from pathlib import Path

   # Third-party
   import numpy as np
   from farm_ng.core import Event

   # Local
   from navigation.path_planner import PathPlanner
   from vision.vision_system import VisionSystem
   ```

7. **Keep functions focused:**
   - Under 50 lines when possible
   - Single responsibility
   - Extract complex logic into helper functions

### Hardware-Specific Guidelines

1. **Always handle hardware failures gracefully:**
   ```python
   try:
       await self.services.canbus.send_message(msg)
   except Exception as e:
       logger.error(f"CAN bus communication failed: {e}")
       return False
   ```

2. **Add timeouts to all async operations:**
   ```python
   try:
       result = await asyncio.wait_for(detection_task, timeout=5.0)
   except asyncio.TimeoutError:
       logger.warning("Detection timed out")
       return None
   ```

3. **Log state changes:**
   ```python
   logger.info(f"State transition: {old_state} → {new_state}")
   ```

## Testing Requirements

### Test Categories

We have three test categories:

1. **Unit Tests** (`tests/unit/`)
   - Fast, no hardware required
   - Mock external dependencies
   - Test individual functions/classes

2. **Integration Tests** (`tests/integration/`)
   - Test multiple modules together
   - May use simulated hardware
   - Slower than unit tests

3. **Hardware Tests** (`tests/hardware/`)
   - Require actual Amiga robot
   - Test real CAN bus, cameras, etc.
   - Run manually before deployment

### Running Tests

```bash
# Run unit tests (fast, always run before commit)
./scripts/run-tests.sh unit

# Run integration tests
./scripts/run-tests.sh integration

# Run all tests
./scripts/run-tests.sh all

# Run specific test file
python -m pytest tests/unit/test_path_planner.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Writing Tests

```python
# tests/unit/test_path_planner.py
import pytest
from navigation.path_planner import PathPlanner

def test_waypoint_loading():
    """Test loading waypoints from CSV."""
    planner = PathPlanner(...)
    assert planner.waypoint_count > 0

@pytest.mark.asyncio
async def test_segment_planning():
    """Test planning a track segment."""
    planner = PathPlanner(...)
    track = await planner.plan_segment(start, end)
    assert track is not None
```

### Testing Requirements for PRs

- [ ] All existing tests pass
- [ ] New code has unit tests (aim for >80% coverage)
- [ ] Integration tests for new features
- [ ] Tested on actual hardware (when applicable)
- [ ] No test skips without documented reason

## Commit Message Format

We use a structured commit format defined in `.gitmessage`. The git hook will automatically load this template.

### Commit Structure

```
[TYPE] Brief summary (50 chars or less)

More detailed explanation (wrap at 72 chars):
- Why this change is needed
- What problem it solves
- Any side effects or implications

Footer (optional): Link to issues, breaking changes, etc.
Closes #123
Breaking change: ...
```

### Commit Types

- `[FEAT]` - New feature or functionality
- `[FIX]` - Bug fix
- `[REFACTOR]` - Code restructuring without changing behavior
- `[DOCS]` - Documentation changes only
- `[TEST]` - Adding or updating tests
- `[STYLE]` - Formatting, whitespace, etc. (no code change)
- `[PERF]` - Performance improvements
- `[CHORE]` - Build, dependencies, tooling, etc.
- `[OVERHAUL]` - Major system rewrite or restructuring

### Examples

```
[FEAT] Add visual servoing for fine alignment

Implements closed-loop visual servoing using downward camera to
correct final positioning errors. Falls back to open-loop if
detection confidence is low.

Closes #42
```

```
[FIX] Resolve CAN bus timeout during tool deployment

The stemming module was not properly handling CAN communication
timeouts. Added retry logic and better error handling.

Fixes #67
```

```
[REFACTOR] Extract coordinate transforms into utility module

Moved ENU→NWU and pose transformation functions from path_planner
into navigation/coordinate_transforms.py for better reusability.
No behavior changes.
```

### Commit Best Practices

- **Atomic commits:** One logical change per commit
- **Complete commits:** Code compiles and tests pass
- **Descriptive commits:** Someone should understand the change from the message alone
- **Link issues:** Reference issue numbers when applicable

## Pull Request Process

### Creating a PR

1. **Push your branch:**
   ```bash
   git push -u origin feature/your-feature
   ```

2. **Create PR on GitHub:**
   - Click "Compare & pull request"
   - Fill out the PR template completely
   - Assign yourself
   - Add relevant labels
   - Request review from at least one team member

3. **PR Template Checklist:**
   - Summary of changes
   - Type of change (feature/fix/refactor/etc.)
   - Testing performed
   - All checklist items completed
   - Related issues linked

### Review Process

1. **Reviewer responsibilities:**
   - Review within 24 hours
   - Check code quality, tests, documentation
   - Run code locally if possible
   - Provide constructive feedback
   - Approve or request changes

2. **Author responsibilities:**
   - Address all feedback
   - Push updates to the same branch
   - Respond to comments
   - Re-request review after changes

3. **Approval requirements:**
   - At least 1 approval required
   - All CI checks pass (if configured)
   - No unresolved conversations
   - Up to date with main branch

### Merging

1. **Before merging:**
   ```bash
   # Update your branch with latest main
   git checkout main
   git pull
   git checkout feature/your-feature
   git rebase main
   git push --force-with-lease
   ```

2. **Merge strategy:**
   - Use "Squash and merge" for feature branches (cleaner history)
   - Use "Rebase and merge" for hotfixes
   - Use "Merge commit" for long-running branches

3. **After merging:**
   - Delete the feature branch on GitHub
   - Delete local branch: `git branch -d feature/your-feature`
   - Pull latest main: `git checkout main && git pull`

## Issue Tracking

### Creating Issues

Use GitHub Issues for all tasks, bugs, and discussions.

**Create issues for:**
- Bugs discovered during development or testing
- New features or enhancements
- Refactoring needs
- Documentation improvements
- Questions or discussions

### Issue Labels

We use the following labels to categorize issues:

**Type:**
- `bug` - Something isn't working
- `enhancement` - New feature or improvement
- `refactor` - Code quality improvement
- `documentation` - Documentation updates
- `question` - Discussion or clarification needed

**Component:**
- `navigation` - Navigation system (path planning, track execution)
- `vision` - Vision system (cameras, detection, alignment)
- `control` - Control system (tool manager, stemming module)
- `hardware` - Hardware integration (CAN bus, actuators, filters)
- `config` - Configuration or setup issues

**Priority:**
- `urgent` - Blocking issue, needs immediate attention
- `high` - Important, should be done soon
- `medium` - Normal priority
- `low` - Nice to have, not urgent

**Status:**
- `help-wanted` - Good for collaboration or discussion
- `wip` - Work in progress
- `blocked` - Cannot proceed without external input

### Issue Workflow

1. **Report the issue:**
   - Use a clear, descriptive title
   - Provide context and steps to reproduce (for bugs)
   - Add relevant labels
   - Assign to someone if known, otherwise leave unassigned

2. **During development:**
   - Self-assign when you start working on it
   - Reference the issue in commits: `Implements #123`
   - Update status with comments if it takes multiple days

3. **Closing issues:**
   - Close with PR: `Closes #123` in PR description
   - Or close manually with explanation if not via PR
   - Verify the fix before closing

### Issue Templates

When creating an issue, consider including:

**For bugs:**
```markdown
### Bug Description
Brief description of the bug

### Steps to Reproduce
1. Step one
2. Step two
3. See error

### Expected Behavior
What should happen

### Actual Behavior
What actually happens

### Environment
- Branch: main
- Hardware: Amiga robot / simulation
- Config: navigation_config.yaml

### Logs/Screenshots
Include relevant logs or screenshots
```

**For features:**
```markdown
### Feature Description
What feature should be added

### Motivation
Why this feature is needed

### Proposed Implementation
How it could be implemented (optional)

### Acceptance Criteria
- [ ] Requirement 1
- [ ] Requirement 2
```

## Code Review Guidelines

### For Reviewers

**What to check:**
1. **Correctness:** Does the code do what it claims?
2. **Tests:** Are there adequate tests?
3. **Style:** Does it follow our coding standards?
4. **Documentation:** Are docstrings and comments clear?
5. **Performance:** Any obvious performance issues?
6. **Safety:** Proper error handling for hardware operations?

**How to review:**
1. Read the PR description first
2. Look at the overall structure before details
3. Check tests and documentation
4. Review code logic
5. Run locally if making significant changes

**Providing feedback:**
- Be constructive and specific
- Explain *why* something should change
- Suggest alternatives
- Distinguish between "must fix" and "nice to have"
- Praise good solutions

**Example comments:**
```
✅ Good: "This function is quite long (75 lines). Consider extracting
the detection logic into a separate `_detect_and_filter()` helper
function for better readability."

❌ Bad: "This function is too long."
```

### For Authors

**Before requesting review:**
- [ ] Self-review your own code first
- [ ] All tests pass locally
- [ ] Documentation is updated
- [ ] No debugging code left in (pdb, print statements)
- [ ] Commit messages follow format
- [ ] PR description is complete

**Responding to feedback:**
- Don't take it personally - we're reviewing code, not you
- Ask for clarification if feedback is unclear
- Discuss disagreements professionally
- Mark conversations as resolved after addressing
- Thank reviewers for their time

## Questions?

If you have questions about contributing:
1. Check this guide first
2. Ask in team chat
3. Create a GitHub issue with the `question` label
4. Reach out to the team lead

Thank you for contributing to XStem!
