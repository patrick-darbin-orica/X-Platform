# XStem Team Quick Reference

Quick reference guide for daily development tasks.

## First-Time Setup

```bash
# 1. Navigate to repository
cd ~/Amiga/xstem

# 2. Run setup script (installs git hooks)
./setup-hooks.sh

# 3. Verify setup
git config --list | grep commit.template
```

## Daily Workflow Checklist

### Starting Your Day

```bash
# 1. Check team chat for ongoing work
# 2. Pull latest changes
git checkout main
git pull origin main

# 3. Create or switch to your branch
git checkout -b feature/your-feature-name
# or
git checkout feature/existing-branch

# 4. Announce in team chat what you're working on
```

### During Development

```bash
# Commit frequently (every 30 min)
git add <files>
git commit  # Template auto-loads

# Pull updates regularly (every 1-2 hours)
git pull --rebase origin main

# Run tests before pushing
./scripts/run-tests.sh unit
```

### End of Day

```bash
# 1. Commit all work (even WIP)
git add .
git commit -m "[WIP] Brief description of current state"

# 2. Push to remote
git push -u origin feature/your-branch

# 3. Update issue status on GitHub
# 4. Post progress update in team chat
```

## Common Git Commands

### Branch Management

```bash
# Create new branch
git checkout -b feature/description

# Switch branches
git checkout branch-name

# List all branches
git branch -a

# Delete local branch (after merge)
git branch -d feature/old-branch

# Update branch with latest main
git checkout main
git pull
git checkout feature/your-branch
git rebase main
```

### Committing

```bash
# Stage files
git add file1.py file2.py
git add .  # Stage all changes

# Commit with template
git commit  # Opens editor with template

# View commit history
git log --oneline -10
git log --graph --oneline

# Amend last commit (use carefully!)
git commit --amend
```

### Resolving Conflicts

```bash
# Check status
git status

# See conflicting files
git diff

# After resolving conflicts in editor
git add <resolved-files>
git commit  # Auto-generates merge commit

# Abort merge if needed
git merge --abort
git rebase --abort
```

### Undoing Changes

```bash
# Discard uncommitted changes
git checkout -- file.py
git restore file.py

# Unstage files
git reset HEAD file.py
git restore --staged file.py

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes) - DANGEROUS!
git reset --hard HEAD~1
```

## Testing

```bash
# Run unit tests (fast)
./scripts/run-tests.sh unit

# Run integration tests
./scripts/run-tests.sh integration

# Run all tests
./scripts/run-tests.sh all

# Run with coverage
./scripts/run-tests.sh coverage

# Run specific test
python -m pytest tests/unit/test_path_planner.py -v

# Run tests matching pattern
python -m pytest tests/ -k test_waypoint
```

## Code Quality

```bash
# Check code style
flake8 .
flake8 file.py

# Format code
black .
black file.py

# Run pre-commit checks manually
.git/hooks/pre-commit
```

## SSH Collaboration

### Before Starting Work

1. Post in team chat: `"Working on navigation/path_planner.py"`
2. Wait for acknowledgment
3. Start coding

### Communication Examples

```
✅ Good: "Editing vision/detector.py for next 2 hours - hole detection improvements"
✅ Good: "Done with control/stemming_module.py, pushed to dev/alice/stemming"
❌ Bad: Starting to edit without announcing
```

### If You Encounter a Conflict

1. STOP - Don't force anything
2. Post in team chat immediately
3. Check who's working on the same file
4. Discuss resolution approach
5. Resolve together if needed

## Pull Requests

### Creating a PR

```bash
# 1. Push your branch
git push -u origin feature/your-branch

# 2. Go to GitHub
# 3. Click "Compare & pull request"
# 4. Fill out template completely
# 5. Request review from teammate
```

### PR Checklist

- [ ] All tests pass
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] No debugging code left
- [ ] Commit messages follow format
- [ ] Branch up to date with main

### Reviewing a PR

```bash
# Fetch the PR branch
git fetch origin
git checkout feature/their-branch

# Test locally
./scripts/run-tests.sh unit
python main.py --config config/navigation_config.yaml

# Leave feedback on GitHub
```

## Issue Tracking

### Creating an Issue

1. Go to GitHub Issues
2. Click "New Issue"
3. Choose template (bug/feature)
4. Add labels: `bug`, `enhancement`, `navigation`, etc.
5. Assign if known, otherwise leave unassigned

### Linking Issues to Commits

```bash
# In commit message
[FEAT] Add new feature

Implements the feature described in issue #42

Closes #42

# Or in PR description
Closes #42
Fixes #67
Relates to #123
```

## Commit Message Format

### Structure

```
[TYPE] Brief summary (50 chars max)

Detailed explanation (wrap at 72 chars):
- Why this change is needed
- What problem it solves
- Any side effects

Closes #123
```

### Types

- `[FEAT]` - New feature
- `[FIX]` - Bug fix
- `[REFACTOR]` - Code restructuring
- `[DOCS]` - Documentation
- `[TEST]` - Tests
- `[CHORE]` - Build/tooling
- `[PERF]` - Performance
- `[STYLE]` - Formatting

### Examples

```
[FEAT] Add visual servoing for alignment

Implements closed-loop control using downward camera
to improve final positioning accuracy. Falls back to
open-loop if detection confidence is low.

Closes #42
```

```
[FIX] Resolve CAN timeout during deployment

Added retry logic and better error handling for CAN
communication. Timeout increased from 1s to 3s.

Fixes #67
```

## Troubleshooting

### Git Hook Errors

```bash
# If pre-commit hook fails
# Read the error message carefully
# Fix the issues (usually flake8 errors)
# Try commit again

# To bypass hook (emergency only!)
git commit --no-verify
```

### Merge Conflicts

```bash
# 1. Don't panic!
# 2. Check which files conflict
git status

# 3. Open file in VSCode
# - Click "Accept Current Change" or "Accept Incoming Change"
# - Or manually edit

# 4. After resolving
git add <resolved-file>
git commit
```

### Lost Work

```bash
# Find lost commits
git reflog

# Recover lost commit
git checkout <commit-hash>
git checkout -b recovery-branch

# Recover deleted branch
git reflog
git checkout -b recovered-branch <commit-hash>
```

## Useful VSCode Shortcuts

- `Ctrl+Shift+P` - Command palette
- `Ctrl+P` - Quick file open
- `Ctrl+Shift+F` - Search across files
- `Ctrl+`` - Toggle terminal
- `F5` - Run/debug
- `Ctrl+Shift+G` - Git panel
- `Ctrl+/` - Comment/uncomment

## Resources

- [CONTRIBUTING.md](CONTRIBUTING.md) - Full contribution guide
- [README.md](README.md) - Project documentation
- `.github/pull_request_template.md` - PR template
- [farm-ng Documentation](https://amiga.farm-ng.com/docs/)

## Getting Help

1. Check this quick reference
2. Check CONTRIBUTING.md
3. Ask in team chat
4. Create GitHub issue with `question` label

## Emergency Contacts

- Team Lead: [Name]
- Git Issues: [Name]
- Hardware Issues: [Name]
- Vision System: [Name]

---

**Last Updated:** 2025-12-02
**Maintainer:** Team Lead

Keep this guide updated as workflows evolve!
