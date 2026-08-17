<!-- ADOPT: this file is a SCAFFOLD, not prose to leave as-is. It ships the shape
     of a strong README and the widest reasonable palette of Markdown elements,
     with every project-specific value marked [REPLACE: ...] so an unfinished
     copy renders loudly rather than passing for done. Work top to bottom: fill
     or delete each [REPLACE: ...] and each <!-- ADOPT: ... --> region, keep only
     the sections that are true of this project, and make the table of contents
     match the headings you keep. src/addon-adoption.json lists the same regions
     for someone building from the template with the manifest in hand. -->

<div align="center">

<!-- ADOPT: the logo and hero below are relative image paths. GitHub renders
     them from the repository, so until docs/assets/logo.svg and
     docs/assets/hero.png exist they show as broken-image icons -- a loud
     failure by design. Add the images (the external step in the manifest), or
     delete these blocks and lead with the heading alone. A logo that already
     carries the name makes the H1 redundant; keep one, not both. -->

<img src="docs/assets/logo.svg" alt="[REPLACE: project name] logo" width="120" />

# [REPLACE: project name]

_[REPLACE: one-line tagline]_

<!-- ADOPT: badges. Keep ONLY badges backed by something real. A build badge for
     a workflow that does not exist, or a hardcoded version, renders green-and-
     official while being false -- the one failure mode a README must not have.
     Delete any row you cannot back. shields.io documents the full catalogue. -->

[![Build](https://img.shields.io/github/actions/workflow/status/[REPLACE: owner]/[REPLACE: repo]/ci.yml?branch=main)](https://github.com/[REPLACE: owner]/[REPLACE: repo]/actions)
[![License](https://img.shields.io/github/license/[REPLACE: owner]/[REPLACE: repo])](LICENSE)
[![Release](https://img.shields.io/github/v/release/[REPLACE: owner]/[REPLACE: repo])](https://github.com/[REPLACE: owner]/[REPLACE: repo]/releases)

[About](#about) &bull; [Features](#features) &bull; [Install](#install) &bull; [Usage](#usage) &bull; [Contributing](#contributing) &bull; [License](#license)

<br />

<!-- ADOPT: the hero shot. The strongest READMEs open with one image that shows
     the thing running in context -- the app window on a desktop, a terminal
     mid-session, a rendered output. Replace it or delete the block. -->

[![[REPLACE: project name] in action](docs/assets/hero.png)](https://github.com/[REPLACE: owner]/[REPLACE: repo])

</div>

---

## About

<!-- ADOPT: the whole of this section is placeholder. Say what the project does,
     who it is for, and why it exists -- in the reader's terms, not the build's.
     A reader decides in about thirty seconds whether to keep going. -->

**[REPLACE: project name]** is [REPLACE: one-line tagline]. [REPLACE: two or
three sentences on the problem it solves, who it is for, and what makes it worth
a look.]

> [!NOTE]
> [REPLACE: one line on what makes this different from the obvious alternative.]

## Table of contents

<!-- ADOPT: keep this list in step with the headings you actually keep. GitHub
     auto-anchors headings (lowercase, spaces to hyphens); a link here to a
     section you deleted is a dead anchor. -->

- [About](#about)
- [Features](#features)
- [Install](#install)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features

<!-- ADOPT: replace these with the project's real features. Give each one that
     earns it a screenshot; a feature list a reader can see beats one they have
     to imagine. Delete the subsections you do not need. -->

### :sparkles: [REPLACE: headline feature]

[REPLACE: a sentence on what it does and why it matters.]

[![[REPLACE: feature] screenshot](docs/assets/feature-1.png)](docs/assets/feature-1.png)

### :zap: [REPLACE: second feature]

[REPLACE: a sentence.]

At a glance:

| Capability | [REPLACE: project name] | [REPLACE: alternative] |
| --- | :---: | :---: |
| [REPLACE: capability] | :white_check_mark: | :x: |
| [REPLACE: capability] | :white_check_mark: | :white_check_mark: |
| [REPLACE: capability] | :white_check_mark: | :x: |

## Install

<!-- ADOPT: these commands are stack-specific and do not exist until this
     project's first language manifest does -- until then there is nothing real
     to run here. Replace them with the project's actual install steps when they
     exist; leave a truthful "coming with the first release" line until then. -->

```bash
# [REPLACE: the real install command]
brew install [REPLACE: repo]
```

<details>
<summary>Build from source</summary>

```bash
git clone https://github.com/[REPLACE: owner]/[REPLACE: repo].git
cd [REPLACE: repo]
# [REPLACE: the real build command]
```

</details>

## Usage

<!-- ADOPT: replace with a real, runnable example -- the smallest thing that
     shows the project doing its job. -->

```bash
# [REPLACE: a minimal example that actually runs]
[REPLACE: repo] --help
```

> [!IMPORTANT]
> [REPLACE: the one prerequisite or gotcha a first-time user must know.]

Keyboard-driven? Press <kbd>Ctrl</kbd> + <kbd>K</kbd> for the command palette.

## Roadmap

<!-- ADOPT: a task list is a promise readers will hold you to. Keep only items
     you mean to ship, or delete the section. -->

- [x] [REPLACE: something already done]
- [ ] [REPLACE: planned]
- [ ] [REPLACE: planned]

## Contributing

<!-- ADOPT: keep the links below only for the companion files this repository
     actually has. CONTRIBUTING.md and CODE_OF_CONDUCT.md are separate addons; a
     link to one that was not adopted points at nothing. -->

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), and by
taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

<!-- ADOPT: keep this only if SECURITY.md was adopted; otherwise name the private
     channel you actually watch, or delete the section. -->

Found a vulnerability? Do not open a public issue -- see [SECURITY.md](SECURITY.md).

## License

<!-- ADOPT: keep this only if a LICENSE file is present; match the SPDX id to it. -->

Released under the [GPL-3.0-or-later](LICENSE) license.

## Acknowledgements

<!-- ADOPT: credit the tools, people, and prior work this stands on. Delete the
     placeholders. -->

- [[REPLACE: a dependency or inspiration]](https://example.com)
- [[REPLACE: another]](https://example.com)

Built with care by [REPLACE: owner].[^1]

[^1]: [REPLACE: a footnote -- a thanks, a caveat, or a link worth a detour.]
