# XStem Team Collaboration Overview

## Quick Start (5 minutes)

```bash
# 1. Run setup script
./setup-hooks.sh

# 2. Read quick reference
cat TEAM_QUICK_REFERENCE.md

# 3. Start working
git checkout -b feature/my-feature
```

## Team Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    DAILY WORKFLOW                           │
└─────────────────────────────────────────────────────────────┘

Morning:
  ┌──────────────┐
  │ Team Chat:   │ "Working on navigation/path_planner.py"
  │ Announce     │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Pull Latest  │ git pull origin main
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Create/      │ git checkout -b feature/my-feature
  │ Switch Branch│
  └──────┬───────┘

During Work:
         │
         ▼
  ┌──────────────┐
  │ Code Changes │ Edit files, test locally
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Commit       │ git commit (every 30 min)
  │ Frequently   │ ├─ Pre-commit hook runs
  └──────┬───────┘ └─ Validates code quality
         │
         ▼
  ┌──────────────┐
  │ Pull         │ git pull --rebase (every 1-2 hours)
  │ Regularly    │
  └──────┬───────┘

End of Day:
         │
         ▼
  ┌──────────────┐
  │ Run Tests    │ ./scripts/run-tests.sh unit
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Push Branch  │ git push -u origin feature/my-feature
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Create PR    │ Fill PR template, request review
  └──────────────┘
```

## File Organization

```
xstem/
│
├─── 📚 Documentation (Start Here!)
│    ├── SETUP_INSTRUCTIONS.md      ← Read FIRST
│    ├── CONTRIBUTING.md            ← Full guidelines
│    ├── TEAM_QUICK_REFERENCE.md    ← Bookmark this!
│    └── README.md                  ← Technical docs
│
├─── 🔧 Configuration
│    ├── .vscode/
│    │   ├── settings.json          ← Shared editor settings
│    │   └── extensions.json        ← Recommended extensions
│    │
│    ├── .git-hooks/
│    │   ├── pre-commit             ← Code validation
│    │   └── prepare-commit-msg     ← Commit template loader
│    │
│    ├── .github/
│    │   └── pull_request_template.md
│    │
│    ├── .gitmessage                ← Commit message format
│    ├── .gitignore                 ← Files to ignore
│    ├── .flake8                    ← Python linting rules
│    └── .coveragerc                ← Test coverage config
│
├─── 🛠️ Scripts
│    ├── setup-hooks.sh             ← Run this first!
│    └── scripts/
│        └── run-tests.sh           ← Test runner
│
└─── 💻 Source Code
     ├── main.py
     ├── config/
     ├── core/
     ├── navigation/
     ├── vision/
     ├── control/
     ├── hardware/
     ├── utils/
     └── tests/
```

## Git Hooks in Action

```
You: git commit
│
├─ 🪝 PRE-COMMIT HOOK RUNS
│   │
│   ├─ ✓ Check for merge conflict markers
│   ├─ ✓ Check for debugging code (pdb, breakpoint)
│   ├─ ✓ Check for print statements (warning)
│   ├─ ✓ Run flake8 on Python files
│   ├─ ✓ Check for large files
│   └─ ✓ Check for potential secrets
│
├─ If all checks pass:
│   │
│   └─ 🪝 PREPARE-COMMIT-MSG HOOK RUNS
│       │
│       └─ Loads commit template into editor
│
└─ You fill out the template:
    │
    ├─ [TYPE] Brief summary (50 chars)
    ├─ 
    ├─ Detailed explanation (wrap at 72 chars)
    └─ 
       Closes #123
```

## Branch Strategy

```
main (protected)
 │
 ├─── feature/visual-servoing
 │    └─ Merge via PR after review
 │
 ├─── fix/can-timeout
 │    └─ Merge via PR after review
 │
 ├─── dev/patrick/experiment-detection
 │    └─ Personal work, may not merge
 │
 └─── refactor/vision-cleanup
      └─ Merge via PR after review
```

## Pull Request Flow

```
1. Create Branch
   ┌──────────────────────────────────┐
   │ git checkout -b feature/my-feat  │
   └──────────────────────────────────┘
                 │
                 ▼
2. Make Changes & Commit
   ┌──────────────────────────────────┐
   │ git commit (multiple times)      │
   │ ├─ Pre-commit hook validates     │
   │ └─ Commit template guides you    │
   └──────────────────────────────────┘
                 │
                 ▼
3. Push to Remote
   ┌──────────────────────────────────┐
   │ git push -u origin feature/...   │
   └──────────────────────────────────┘
                 │
                 ▼
4. Create PR on GitHub
   ┌──────────────────────────────────┐
   │ Fill PR template                 │
   │ ├─ Summary                       │
   │ ├─ Type of change                │
   │ ├─ Testing performed             │
   │ └─ Checklist                     │
   └──────────────────────────────────┘
                 │
                 ▼
5. Request Review
   ┌──────────────────────────────────┐
   │ Tag team members                 │
   └──────────────────────────────────┘
                 │
                 ▼
6. Address Feedback
   ┌──────────────────────────────────┐
   │ Make changes                     │
   │ git push (updates PR)            │
   └──────────────────────────────────┘
                 │
                 ▼
7. Get Approval & Merge
   ┌──────────────────────────────────┐
   │ Squash and merge                 │
   │ Delete branch                    │
   └──────────────────────────────────┘
```

## SSH Collaboration Rules

```
┌─────────────────────────────────────────┐
│ BEFORE STARTING WORK                    │
├─────────────────────────────────────────┤
│ 1. Check team chat                      │
│ 2. Announce: "Working on file.py"       │
│ 3. Wait for acknowledgment              │
│ 4. Start coding                         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ CONFLICT PREVENTION                     │
├─────────────────────────────────────────┤
│ ✓ Announce your work area               │
│ ✓ Avoid same file simultaneously        │
│ ✓ Pull frequently (every 1-2 hours)     │
│ ✓ Commit frequently (every 30 min)      │
│ ✓ Communicate if conflicts occur        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ IF CONFLICT HAPPENS                     │
├─────────────────────────────────────────┤
│ 1. STOP - Don't force anything          │
│ 2. Post in team chat immediately        │
│ 3. Discuss resolution approach          │
│ 4. Resolve together if needed           │
│ 5. Test thoroughly after resolution     │
└─────────────────────────────────────────┘
```

## Testing Workflow

```
┌──────────────────────────────────────────────┐
│ BEFORE COMMITTING                            │
├──────────────────────────────────────────────┤
│ ./scripts/run-tests.sh unit                  │
│ └─ Fast, runs in seconds                     │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│ BEFORE CREATING PR                           │
├──────────────────────────────────────────────┤
│ ./scripts/run-tests.sh all                   │
│ ├─ Unit tests                                │
│ ├─ Integration tests                         │
│ └─ (Optional) Hardware tests                 │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│ BEFORE MERGING TO MAIN                       │
├──────────────────────────────────────────────┤
│ ./scripts/run-tests.sh coverage              │
│ └─ Generates HTML coverage report            │
└──────────────────────────────────────────────┘
```

## Commit Message Format

```
Template (auto-loads in editor):
┌─────────────────────────────────────────┐
│ [TYPE] Brief summary (50 chars max)     │
│                                         │
│ Detailed explanation (wrap at 72):      │
│ - Why this change is needed             │
│ - What problem it solves                │
│ - Any side effects                      │
│                                         │
│ Closes #123                             │
└─────────────────────────────────────────┘

Types:
  [FEAT]     - New feature
  [FIX]      - Bug fix
  [REFACTOR] - Code restructuring
  [DOCS]     - Documentation
  [TEST]     - Tests
  [CHORE]    - Build/tooling
  [PERF]     - Performance
  [STYLE]    - Formatting

Example:
┌─────────────────────────────────────────┐
│ [FEAT] Add visual servoing alignment    │
│                                         │
│ Implements closed-loop control using    │
│ downward camera for fine positioning.   │
│ Falls back to open-loop if detection    │
│ confidence is low.                      │
│                                         │
│ Closes #42                              │
└─────────────────────────────────────────┘
```

## Key Files Reference

| File | Purpose | When to Use |
|------|---------|-------------|
| `SETUP_INSTRUCTIONS.md` | Step-by-step setup | First time only |
| `CONTRIBUTING.md` | Full guidelines | Reference when needed |
| `TEAM_QUICK_REFERENCE.md` | Quick commands | Daily use, bookmark! |
| `README.md` | Technical docs | Understanding system |
| `setup-hooks.sh` | Install git hooks | First time + updates |
| `scripts/run-tests.sh` | Run tests | Before commit/PR |

## Getting Help

```
┌─────────────────────────────────────────┐
│ Question Type    → Where to Ask         │
├─────────────────────────────────────────┤
│ Quick question   → Team chat            │
│ Git issue        → TEAM_QUICK_REFERENCE │
│ Workflow         → CONTRIBUTING.md      │
│ Technical        → README.md            │
│ Bug/Feature      → GitHub Issues        │
│ Complex issue    → Schedule team sync   │
└─────────────────────────────────────────┘
```

## Success Checklist

New team member setup:
- [ ] Ran `./setup-hooks.sh`
- [ ] Verified git hooks installed
- [ ] Tested commit template works
- [ ] Installed VSCode extensions
- [ ] Read SETUP_INSTRUCTIONS.md
- [ ] Read CONTRIBUTING.md
- [ ] Bookmarked TEAM_QUICK_REFERENCE.md
- [ ] Joined team communication channel
- [ ] Introduced yourself to team
- [ ] Created test branch to practice

Ready to contribute!

---

**Remember:** Communication is key! When in doubt, ask the team.
