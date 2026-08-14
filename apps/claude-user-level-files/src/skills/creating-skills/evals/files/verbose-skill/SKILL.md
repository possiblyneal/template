---
name: verbose-skill
description: Generates weekly status reports from git history, Jira tickets, and Slack summaries. Use when a user wants to write a status report, weekly update, standup summary, or project progress report.
---

# Weekly Status Report Generator

This skill helps you generate weekly status reports by pulling together information from multiple sources including git commit history, Jira tickets, and Slack message summaries. The goal is to produce a clear, concise report that can be shared with stakeholders.

## Background and Context

Weekly status reports are a common communication tool in software engineering teams. They help keep stakeholders informed about progress, blockers, and upcoming work. Different teams have different formats, but most reports cover what was accomplished, what is in progress, what is blocked, and what is planned next week.

The challenge with generating these reports automatically is that the raw data (commits, tickets, Slack messages) is often verbose and technical, while the report needs to be readable by non-technical stakeholders. This skill bridges that gap by extracting the key information and presenting it in a human-friendly format.

## Data Sources

### Git History

Git commit history is one of the primary data sources for status reports. Commits represent actual work done and are a reliable record of activity.

To pull git history for a given time period, use:

```bash
git log --since="last monday" --until="today" --oneline --author="$(git config user.email)"
```

This will give you a list of commits since last Monday. You can adjust the time window as needed.

If the user hasn't specified a time window, default to the last 7 days:

```bash
git log --since="7 days ago" --oneline
```

To get more detail on a specific commit, you can use:

```bash
git show <commit-hash> --stat
```

This shows which files were changed in that commit, which can help you understand the scope of the work.

For a summary of all changes across multiple commits:

```bash
git diff HEAD~20 HEAD --stat
```

This shows all files changed in the last 20 commits. Adjust the number as needed.

Sometimes it's useful to see the commit messages grouped by day:

```bash
git log --since="7 days ago" --format="%ad %s" --date=short | sort
```

This gives you a chronological view of what was worked on each day.

### Jira Tickets

If the user has a Jira instance, you can pull ticket information to supplement the git history. Jira tickets provide context about why work was done and what the business impact is.

To query Jira, you'll need the Jira API. The base URL is usually something like `https://<company>.atlassian.net/rest/api/3/`. You'll need an API token, which the user should provide or have stored in their environment.

Common API calls:

**Get issues assigned to current user updated this week:**
```
GET /rest/api/3/search?jql=assignee=currentUser() AND updated>="-7d"
```

**Get issues in a specific sprint:**
```
GET /rest/api/3/search?jql=sprint in openSprints() AND assignee=currentUser()
```

**Get a specific issue:**
```
GET /rest/api/3/issue/{issueKey}
```

When reading Jira data, focus on:
- Issue summary (title)
- Status (To Do, In Progress, Done, etc.)
- Story points if available
- Any comments added this week

Jira tickets often have a lot of irrelevant fields — ignore anything that isn't directly relevant to status reporting.

### Slack Summaries

Slack is often where blockers and decisions get discussed. If the user can provide a Slack export or paste relevant messages, you can extract key information.

Look for:
- Messages where the user mentioned blockers ("blocked by", "waiting on", "can't proceed until")
- Decisions made ("decided to", "going with", "approved")
- Action items assigned to the user

If the user provides a Slack export, it will be in JSON format. The relevant fields are `text`, `ts` (timestamp), and `user`.

### Combining Sources

When you have data from multiple sources, reconcile them:
1. Start with Jira tickets as the structured backbone
2. Enrich each ticket with related git commits (match by ticket number in commit message)
3. Add context from Slack where relevant
4. Fill gaps: if there are commits with no matching ticket, add them as unlabeled work items

## Report Format

The standard report format is:

```
## Weekly Status: [Date Range]

### ✅ Completed
- [Item 1]
- [Item 2]

### 🔄 In Progress
- [Item 1] — [% complete or current state]
- [Item 2] — [% complete or current state]

### 🚧 Blocked
- [Item 1] — blocked by [blocker]

### 📅 Next Week
- [Planned item 1]
- [Planned item 2]

### 📊 Metrics (optional)
- Commits: N
- Tickets closed: N
- PRs merged: N
```

Each item in the completed and in-progress sections should be written at the right level of abstraction — specific enough to be meaningful but not so technical that non-engineers can't understand it.

**Good:** "Implemented retry logic for payment processor timeouts (reduces checkout failures during outages)"
**Bad:** "Fixed bug in payment_processor.py line 847 where exception handler wasn't catching TimeoutError"

The "Metrics" section is optional — only include it if the user asks for it or if it adds meaningful context.

## Writing Guidelines

### Tone and Voice

Status reports should be written in first person, past tense for completed items ("I implemented...", "I fixed...") and present/future for in-progress and planned items ("I'm working on...", "I plan to...").

Keep the language direct and factual. Avoid hedging language like "I tried to" or "I attempted to" — either it's done or it's in progress.

Don't be too brief — one-line summaries without context are less useful than a brief explanation of why the work matters. But also don't over-explain — a sentence or two per item is usually enough.

### Level of Detail

Match the level of detail to the audience:
- For engineering managers: include technical context
- For product managers: focus on user-facing impact
- For executives: high-level outcomes only

If you're not sure who the audience is, default to "engineering manager" level — technical enough to be credible, accessible enough to be readable.

### Handling Blockers

Blockers should be specific and actionable. Don't just say "blocked" — explain what you're waiting on, who owns the blocker, and what the impact is if it's not resolved.

**Good:** "Blocked on design approval for new checkout flow — waiting on @sarah. This will delay the Q2 launch if not resolved by Thursday."
**Bad:** "Blocked on design."

If a blocker has been resolved since you first noted it, mention that it was resolved and what the outcome was.

### Confidentiality

Be mindful of what goes into a status report. Avoid:
- Naming colleagues negatively (e.g., "blocked because [Name] hasn't done their job")
- Sharing sensitive financial or customer data
- Discussing internal conflicts or personnel issues

If the user's data contains sensitive information, flag it before including it in the report.

## Customization

### Custom Templates

If the user has a custom template, use it instead of the default format. Ask the user to paste or link their template before generating the report.

When using a custom template, map the user's data to the template's sections as best you can. If there are sections in the template that don't have corresponding data, leave them blank rather than inventing content.

### Recurring Reports

If the user runs this skill weekly, they may want to maintain a history of reports. Suggest saving reports to a `status-reports/` directory with filenames like `2026-W22.md`.

You can also offer to diff two consecutive reports to highlight what changed week over week — useful for spotting trends or showing progress over longer timeframes.

### Team Reports

If the user wants to generate a team report rather than an individual one, you'll need data from multiple team members. Ask the user how they want to aggregate the data:
- Merge all commits/tickets into a single report organized by feature area
- Generate individual reports and combine them into a team summary
- Generate only the team summary, omitting individual details

## Error Handling

### No Git History Found

If `git log` returns nothing, the user may be in the wrong directory, the time window may be too narrow, or the author filter may not match their email.

Ask: "I didn't find any commits in the last 7 days. Are you in the right repository? Your configured git email is [email]. Do you want me to try a broader time window?"

### No Jira Access

If Jira API calls fail, fall back to git history and Slack only. Tell the user: "I wasn't able to connect to Jira. I'll generate the report from git history only — you can add ticket context manually."

### Ambiguous Commits

Some commit messages are unhelpful ("fix", "wip", "misc"). When you encounter these:
1. Look at the files changed in that commit
2. Try to infer what the change was about
3. If still unclear, include a placeholder like "[unclear - review commit abc1234]"

Don't invent a description for a commit you can't understand.

### Empty Weeks

If there's genuinely no activity to report (vacation, sick leave, etc.), generate a minimal report:

```
## Weekly Status: [Date Range]

No activity this week — [reason if known].

### 📅 Next Week
- [Planned items]
```

## Examples

### Example 1: Engineer with git + Jira data

Input:
- 8 commits across 3 branches
- 2 Jira tickets closed, 1 in progress
- 1 blocker noted in Slack

Output:
```
## Weekly Status: May 26 – May 30, 2026

### ✅ Completed
- Implemented retry logic for payment processor timeouts — reduces checkout failures during brief payment service outages (PAY-4421)
- Fixed incorrect tax calculation for international orders with multiple line items (ORD-8823)

### 🔄 In Progress
- Migrating order history endpoint to new pagination API — ~60% complete, finishing next week (ORD-8901)

### 🚧 Blocked
- New checkout UI — waiting on design sign-off from @sarah. Expected by Thursday; delays Q2 launch if missed.

### 📅 Next Week
- Complete pagination migration
- Start integration testing for checkout UI once design is approved
```

### Example 2: Engineer with git only, no Jira

Input:
- 5 commits, no Jira integration

Output:
```
## Weekly Status: May 26 – May 30, 2026

### ✅ Completed
- Added dark mode support to dashboard components
- Resolved memory leak in background sync worker
- Updated onboarding flow to skip steps already completed by user

### 🔄 In Progress
- Refactoring authentication module to support SSO — early stages

### 📅 Next Week
- Continue SSO refactor
- Address review comments on dark mode PR
```

## Advanced Usage

### Integrating with Calendar

If the user wants to include meeting notes or action items from their calendar, ask them to paste the relevant entries. You can then extract action items assigned to them and include them as additional context.

### Automated Weekly Runs

This skill can be run as a scheduled task. To set up weekly automation:
1. Create a script that runs this skill with `claude --print`
2. Schedule it with cron: `0 9 * * 5` (9am every Friday)
3. Pipe output to a file or email

### Integration with PR Reviews

If the user spent significant time reviewing PRs this week, mention it. Reviewing code is real work and often goes uncredited in status reports.

To find PRs reviewed on GitHub:
```
GET /search/issues?q=type:pr+reviewed-by:USERNAME+updated:>LAST_MONDAY
```

## Troubleshooting

### Report is Too Long

If the generated report is longer than ~1 page, it's probably too detailed. Ask the user: "This report is quite long. Should I summarize more aggressively, or is this level of detail appropriate for your audience?"

### Report is Too Vague

If the user says the report is too vague, ask them to share the raw data again and flag which items need more context.

### Wrong Time Period

If the report covers the wrong dates, ask the user to specify the exact start and end dates: "I defaulted to last 7 days. What date range would you like the report to cover?"

### Duplicate Items

If the same work item appears in both git commits and Jira tickets, deduplicate it in the final report. Show it once with the ticket number if available.

## API Reference

### Git Commands Reference

Here is a comprehensive reference for all git commands you might need when generating status reports.

**Basic log commands:**
```bash
# Show commits in the last N days
git log --since="N days ago" --oneline

# Show commits by a specific author
git log --author="Name or Email" --oneline

# Show commits between two dates
git log --after="2026-05-01" --before="2026-05-31" --oneline

# Show commits with file statistics
git log --stat --since="7 days ago"

# Show commits in a specific branch
git log main..feature-branch --oneline

# Show merge commits only
git log --merges --since="7 days ago"

# Show commits that touched a specific file
git log --follow -- path/to/file.py

# Show commits formatted as a changelog
git log --format="%h %ad %s" --date=short --since="7 days ago"
```

**Diff commands:**
```bash
# Show what changed in the last N commits
git diff HEAD~N HEAD --stat

# Show full diff for a specific commit
git show <hash>

# Show only file names changed
git diff --name-only HEAD~7 HEAD

# Show word-level diff (good for docs)
git diff --word-diff HEAD~3 HEAD -- README.md
```

**Branch commands:**
```bash
# Show branches with last commit date
git branch -v

# Show remote branches
git branch -r

# Show merged branches
git branch --merged main
```

### Jira API Reference

Full reference for Jira API endpoints used in this skill.

**Authentication:**
Use HTTP Basic Auth with your Atlassian account email and an API token. Generate tokens at https://id.atlassian.com/manage-profile/security/api-tokens.

```
Authorization: Basic base64(email:api_token)
```

**JQL (Jira Query Language) reference:**

```
# Issues assigned to current user
assignee = currentUser()

# Issues updated in last 7 days
updated >= "-7d"

# Issues in current sprint
sprint in openSprints()

# Issues in a specific project
project = "MYPROJECT"

# Issues by status
status = "In Progress"
status in ("In Progress", "In Review")

# Issues by type
issuetype = Story
issuetype in (Bug, Story, Task)

# Combining conditions
assignee = currentUser() AND updated >= "-7d" AND project = "PAY"

# Issues with specific label
labels = "backend"

# Issues resolved this week
resolution is not EMPTY AND resolutiondate >= "-7d"
```

**Response fields to extract:**
- `key` — ticket ID (e.g., PAY-4421)
- `fields.summary` — ticket title
- `fields.status.name` — current status
- `fields.story_points` or `fields.customfield_10016` — story points (field name varies by instance)
- `fields.updated` — last updated timestamp
- `fields.assignee.displayName` — assignee name
- `fields.comment.comments` — array of comments

**Pagination:**
Jira API paginates results. Use `startAt` and `maxResults` params. Default `maxResults` is 50.

```
GET /rest/api/3/search?jql=...&startAt=0&maxResults=50
GET /rest/api/3/search?jql=...&startAt=50&maxResults=50
```

### Slack Export Format

Slack exports (from workspace admin) produce a directory structure:

```
export/
├── channels.json
├── users.json
└── channel-name/
    ├── 2026-05-26.json
    ├── 2026-05-27.json
    └── ...
```

Each daily file is an array of message objects:

```json
[
  {
    "type": "message",
    "user": "U012AB3CD",
    "text": "blocked on the payments service being down",
    "ts": "1748300400.000100",
    "thread_ts": "1748300400.000100",
    "reply_count": 3
  }
]
```

Look up user IDs in `users.json` to get display names:
```json
{
  "id": "U012AB3CD",
  "name": "john.smith",
  "real_name": "John Smith"
}
```

Convert Unix timestamps with: `datetime.fromtimestamp(float(ts))`

## Configuration

### Environment Variables

| Variable | Description | Required |
|---|---|---|
| `JIRA_BASE_URL` | Your Jira instance URL, e.g. `https://company.atlassian.net` | For Jira |
| `JIRA_EMAIL` | Your Atlassian account email | For Jira |
| `JIRA_API_TOKEN` | API token from Atlassian | For Jira |
| `GITHUB_TOKEN` | Personal access token for PR queries | For GitHub |
| `SLACK_EXPORT_PATH` | Path to Slack export directory | For Slack |
| `REPORT_AUTHOR` | Override the author name in the report | No |
| `REPORT_OUTPUT_DIR` | Directory to save reports | No, defaults to `./status-reports/` |

### Config File

Alternatively, store config in `~/.status-report-config.json`:

```json
{
  "jira_base_url": "https://company.atlassian.net",
  "jira_email": "user@company.com",
  "jira_api_token": "your-token-here",
  "github_token": "ghp_...",
  "default_time_window_days": 7,
  "output_dir": "~/status-reports",
  "audience": "engineering_manager",
  "include_metrics": false
}
```

Config file values are overridden by environment variables.

## Frequently Asked Questions

**Q: What if I work across multiple repositories?**

A: Run `git log` in each repo separately and combine the results. If the repos are part of a monorepo, a single `git log` from the repo root covers everything.

**Q: Can I use this with GitLab instead of GitHub?**

A: Yes. GitLab has a similar API for PR (merge request) reviews. The endpoint is:
```
GET /projects/:id/merge_requests?state=merged&updated_after=<date>
```

**Q: What if my commit messages are terrible?**

A: Look at the files changed in each commit to infer what was done. If still unclear, mark it as a manual review item: "[review commit abc1234 - unclear message]". Going forward, consider using conventional commits.

**Q: Can I generate a report for a colleague?**

A: Yes. Pass their email to the `--author` flag in git log and their Jira username to the JQL query.

**Q: The report shows work I don't want to include (exploratory work, reverted commits, etc.)**

A: Tell the skill which commits or tickets to exclude. You can also set up a `.statusignore` file with commit hash prefixes or ticket numbers to skip.

**Q: How do I include work from before the standard 7-day window?**

A: Specify a custom start date: "Generate a status report for May 1 through May 30."
