# Team Setup Instructions

Welcome to the XStem project! This guide will help you get set up for collaborative development.

## For ALL Team Members

Everyone on the team must complete these steps after accessing the repository.

### 1. Run the Setup Script

This installs git hooks and configures the commit template:

```bash
cd ~/Amiga/xstem
./setup-hooks.sh
```

You should see output like:

```
Setting up git hooks and commit template for XStem...

✓ Installed prepare-commit-msg hook
✓ Installed pre-commit hook
✓ Configured commit template: /path/to/.gitmessage

==========================================
Setup complete!
==========================================

Git hooks installed:
  • prepare-commit-msg - Loads commit template
  • pre-commit - Validates code before commit
```

### 2. Verify Your Git Configuration

```bash
# Check that hooks are installed
ls -la .git/hooks/
# You should see: prepare-commit-msg and pre-commit

# Verify commit template is configured
git config --get commit.template
# Should show: /path/to/xstem/.gitmessage
```

### 3. Test the Commit Template

```bash
# Make a small change (or use --allow-empty)
git commit --allow-empty

# You should see the commit template in your editor:
# [TYPE] Brief summary (50 chars or less)
#
# More detailed explanation (wrap at 72 chars)
# ...
```

Press `Ctrl+C` or `:q!` to exit without committing.

### 4. Install VSCode Extensions (Recommended)

If you're using VSCode:

1. Open the repository in VSCode
2. You'll see a notification: "This workspace has extension recommendations"
3. Click "Install All" or "Show Recommendations"

Recommended extensions:
- Python language support
- GitLens (enhanced Git integration)
- Black formatter
- Flake8 linter

### 5. Read the Documentation

Please read these files before starting development:

1. **[README.md](README.md)** - Project overview and technical documentation
2. **[CONTRIBUTING.md](CONTRIBUTING.md)** - Full contribution guidelines (15 min read)
3. **[TEAM_QUICK_REFERENCE.md](TEAM_QUICK_REFERENCE.md)** - Quick command reference

## Team Communication Setup

### Daily Communication Protocol

**Required:** Set up a team communication channel (Slack, Discord, Teams, etc.)

Before starting work each day:
1. Post what you're working on
2. Mention which files/modules you'll be editing
3. Wait for acknowledgment from team

**Example:**
```
Patrick: "Morning! Working on navigation/path_planner.py today - adding recovery logic"
Alice: "👍 I'll focus on vision/detector.py then"
```

### SSH Collaboration Rules

Since we all share SSH access to the same machine:

1. **Always announce what you're working on**
2. **Avoid editing the same file simultaneously**
3. **Pull frequently** (every 1-2 hours): `git pull --rebase`
4. **Commit frequently** (every 30 min)
5. **Communicate if conflicts occur**

See [CONTRIBUTING.md - SSH Collaboration Guidelines](CONTRIBUTING.md#ssh-collaboration-guidelines) for details.

## Branching Strategy

### Branch Naming

Use these prefixes:

- `feature/description` - New features
- `fix/description` - Bug fixes
- `refactor/description` - Code improvements
- `test/description` - Test additions
- `dev/yourname/description` - Personal experiments

**Examples:**
```bash
git checkout -b feature/visual-servoing
git checkout -b fix/can-timeout
git checkout -b dev/patrick/experiment-detection
```

### Working on a Feature

```bash
# 1. Create branch from main
git checkout main
git pull
git checkout -b feature/your-feature

# 2. Make changes and commit frequently
git add <files>
git commit  # Template loads automatically

# 3. Push to remote
git push -u origin feature/your-feature

# 4. Create Pull Request on GitHub
# 5. Request review from teammate
# 6. Merge after approval
```

## Pre-Commit Hook

The pre-commit hook automatically checks your code before each commit:

**Checks performed:**
- ✓ Merge conflict markers
- ✓ Debugging code (pdb, breakpoint)
- ✓ Python style (flake8)
- ✓ Large files (>1MB warning)
- ✓ Potential secrets/credentials
- ⚠ Print statements (warning only)
- ⚠ TODOs without issue numbers (warning only)

**If the hook fails:**
1. Read the error message
2. Fix the issues
3. Try committing again

**Example:**
```bash
git commit
# Running pre-commit checks...
# Checking for merge conflict markers... OK
# Checking for debugging code... OK
# Running flake8 on Python files... FAILED
#
# flake8 found style issues:
# main.py:42:80: E501 line too long (92 > 88 characters)
#
# Please fix the above issues before committing.
```

Fix the issue and try again:
```bash
# Fix the line length issue
black main.py  # Auto-format

# Commit again
git commit
# ✓ All pre-commit checks passed!
```

## Testing

### Running Tests

```bash
# Quick unit tests (run before every commit)
./scripts/run-tests.sh unit

# All tests
./scripts/run-tests.sh all

# With coverage report
./scripts/run-tests.sh coverage
```

### Before Pushing Code

**Checklist:**
- [ ] Unit tests pass: `./scripts/run-tests.sh unit`
- [ ] Code follows style: `flake8 .`
- [ ] No debugging code left (pdb, excessive prints)
- [ ] Commit messages follow format

## Pull Request Process

### Creating a PR

1. Push your branch:
   ```bash
   git push -u origin feature/your-branch
   ```

2. Go to GitHub and click "Compare & pull request"

3. Fill out the PR template (auto-loads)
   - Summary of changes
   - Type of change
   - Testing performed
   - All checklist items

4. Request review from at least one team member

5. Address feedback and re-request review

6. Merge after approval

### Reviewing a PR

When you're asked to review:

1. Pull the branch locally and test it
2. Review the code on GitHub
3. Leave comments or approve
4. Respond within 24 hours when possible

## Common Issues

### Issue: "Hook failed" when committing

**Solution:** Read the error message and fix the issues. Usually it's:
- Flake8 style violations → Run `black .` to auto-format
- Debugging code → Remove `pdb.set_trace()` or `breakpoint()`

### Issue: "Merge conflict" when pulling

**Solution:**
1. Don't panic - this is normal!
2. Open the file in VSCode
3. Choose which changes to keep
4. Mark as resolved: `git add <file>`
5. Complete the merge: `git commit`

See [TEAM_QUICK_REFERENCE.md - Resolving Conflicts](TEAM_QUICK_REFERENCE.md#resolving-conflicts)

### Issue: "I edited the same file as someone else"

**Solution:**
1. Post in team chat immediately
2. Discuss who should commit first
3. The second person will handle the merge conflict
4. Work together to resolve

## File Structure Overview

```
xstem/
├── CONTRIBUTING.md              # Full contribution guide
├── TEAM_QUICK_REFERENCE.md      # Quick command reference
├── SETUP_INSTRUCTIONS.md        # This file
├── README.md                    # Project documentation
│
├── .github/
│   └── pull_request_template.md # PR template (auto-loads)
│
├── .vscode/
│   ├── settings.json            # Shared VSCode settings
│   └── extensions.json          # Recommended extensions
│
├── .git-hooks/
│   ├── pre-commit               # Validates code before commit
│   └── prepare-commit-msg       # Loads commit template
│
├── scripts/
│   └── run-tests.sh             # Test runner
│
├── setup-hooks.sh               # Setup script (run this first!)
├── .gitmessage                  # Commit message template
├── .gitignore                   # Git ignore patterns
├── .flake8                      # Python linting config
└── .coveragerc                  # Test coverage config
```

## Getting Help

If you have questions:

1. **Check the docs first:**
   - [CONTRIBUTING.md](CONTRIBUTING.md) - Detailed guidelines
   - [TEAM_QUICK_REFERENCE.md](TEAM_QUICK_REFERENCE.md) - Quick commands
   - [README.md](README.md) - Technical documentation

2. **Ask in team chat**

3. **Create a GitHub issue** with the `question` label

4. **Schedule a team sync** if it's a complex question

## Next Steps

After completing this setup:

1. ✓ Read CONTRIBUTING.md (full guidelines)
2. ✓ Read TEAM_QUICK_REFERENCE.md (bookmark this!)
3. ✓ Join the team communication channel
4. ✓ Introduce yourself and ask for your first task
5. ✓ Create a test branch and practice the workflow

## Welcome to the Team!

Thanks for taking the time to set up properly. Following these guidelines will help us:
- Avoid merge conflicts
- Maintain code quality
- Collaborate effectively
- Ship features faster

Happy coding! 🚀

---

**Questions?** Ask in the team chat or create a GitHub issue.
**Found an error in this doc?** Submit a PR to fix it!
