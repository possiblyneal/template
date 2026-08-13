---
name: test-skill
description: Helps with log analysis tasks. Use when the user wants to look at logs.
---

# Log Analysis

This skill helps you analyze log files and find problems.

## How to analyze logs

When the user gives you a log file, read through it and look for errors. Pay attention to timestamps and try to understand the sequence of events.

Things to look for:
- ERROR or FATAL level messages
- Stack traces
- Repeated warnings
- Unusual gaps in timestamps

## Reporting

Tell the user what you found. Explain any errors in plain language. If there are a lot of errors, summarize the main themes rather than listing every single one.

Try to explain what might have caused the problem if you can figure it out from the log context.

## Format

Write a short summary at the top, then go into detail. Use bullet points for lists of errors.
