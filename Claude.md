# CRITICAL

RESPECT THE WORKFLOW BELOW!!!
NEVER: leave uncommitted or unpushed changes - always maintain a consistent and backed-up repository state
ALWAYS: Consider if a web research for current best practices could be useful.
ALWAYS: Consider if a web research for existing framework components that cover the requirements

# WORKFLOW

## Git Branching

- Work on feature branches, NOT directly on main/master
- Create a new branch for each task: `git checkout -b feature/<descriptive-name>`
- Commit changes to the feature branch with conventional commit messages
- Only merge to main when the user approves the changes
- After merge approval: merge to main with `--no-ff`, push, and delete the feature branch
- Keep feature branches focused on a single task/feature

## Code Review Process

After completing a task do two subsequent reviews:

1. **First**: review your changes with a subagent that focuses on the big picture, how the new implementation is used and which implications arise
2. **Second**: review your changes with a subagent the default way

Address findings and ask back if anything unclear.
