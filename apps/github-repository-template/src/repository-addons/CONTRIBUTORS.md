# Contributors

Everyone who has helped build this project, in the [All Contributors](https://allcontributors.org) format.

The point of this file is the work git cannot see. The commit graph already credits code, and GitHub renders it for free — what it structurally cannot show is the person who reported the bug that found the root cause, wrote the explanation that became the docs, translated the interface, reviewed without authoring, or triaged for a year. Those are contributions and this is where they are recorded.

<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->

[![All Contributors](https://img.shields.io/badge/all_contributors-0-orange.svg?style=flat-square)](#contributors)

<!-- ALL-CONTRIBUTORS-BADGE:END -->

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## Adding someone

Comment on any issue or pull request:

```text
@allcontributors please add @username for code, doc
```

The bot opens a pull request updating the table and the badge count. Use one comment per person. It parses loosely, so a sentence around the request is fine, but the `@` on both the bot and the username is what it keys on.

Adding someone by hand instead means editing the table and `.all-contributorsrc` to match; they are two halves of one record, and the CLI regenerates the table from that file rather than reading the Markdown.

## What this depends on

**The marker comments above are load-bearing.** The bot finds its insertion point by string match on `ALL-CONTRIBUTORS-LIST:START` and `ALL-CONTRIBUTORS-LIST:END`. Delete, reword, or reformat them and the bot has nowhere to write — it fails to find the section rather than guessing, so the symptom is a pull request that never appears.

**`.all-contributorsrc` travels with this file and is not optional.** It ships alongside, already carrying `"files": ["CONTRIBUTORS.md"]` — the default is `["README.md"]`, so without that key the table lands in the README and this file stays empty forever. The two are one record: the table here is generated from the `contributors` array there, never parsed back out of the Markdown.

**Replace `REPO-OWNER` and `REPO-NAME` in it before first use.** Both are required and the CLI throws rather than guessing, so the failure is at least loud. They build the profile and commit links, so wrong values produce a table of dead links instead of an error.

**The bot must be installed on the repository** from <https://github.com/apps/allcontributors>. The comment syntax does nothing on a repository where it is not installed, and nothing reports that — the comment simply sits there.

## Contribution types

The key passed after `for`. Multiple types are comma-separated.

| Key | | Meaning | Key | | Meaning |
| --- | --- | --- | --- | --- | --- |
| `a11y` | ♿️ | Accessibility | `platform` | 📦 | Packaging/porting to new platform |
| `audio` | 🔊 | Audio | `plugin` | 🔌 | Plugin/utility libraries |
| `blog` | 📝 | Blogposts | `projectManagement` | 📆 | Project Management |
| `bug` | 🐛 | Bug reports | `promotion` | 📣 | Promotion |
| `business` | 💼 | Business development | `question` | 💬 | Answering Questions |
| `code` | 💻 | Code | `research` | 🔬 | Research |
| `content` | 🖋 | Content | `review` | 👀 | Reviewed Pull Requests |
| `data` | 🔣 | Data | `security` | 🛡️ | Security |
| `design` | 🎨 | Design | `talk` | 📢 | Talks |
| `doc` | 📖 | Documentation | `test` | ⚠️ | Tests |
| `eventOrganizing` | 📋 | Event Organizing | `tool` | 🔧 | Tools |
| `example` | 💡 | Examples | `translation` | 🌍 | Translation |
| `financial` | 💵 | Financial | `tutorial` | ✅ | Tutorials |
| `fundingFinding` | 🔍 | Funding Finding | `userTesting` | 📓 | User Testing |
| `ideas` | 🤔 | Ideas, Planning, & Feedback | `video` | 📹 | Videos |
| `infra` | 🚇 | Infrastructure (Hosting, Build-Tools, etc) | | | |
| `maintenance` | 🚧 | Maintenance | | | |
| `mentoring` | 🧑‍🏫 | Mentoring | | | |

An unrecognized key is an error, not a silent skip: the CLI raises `Unknown contribution type` and writes nothing. Extra types can be defined in `.all-contributorsrc` under `types`, which merges over these defaults.
