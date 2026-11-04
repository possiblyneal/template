# Language ranking

If you could keep only N languages for all projects, keep the first N rows. Each row covers ground none of the rows above it does. Languages present everywhere anyway (Bash, SQL, HTML/CSS) are not ranked.

| # | Language | Why it's the next pick |
|---|---|---|
| 1 | TypeScript | The only language that targets the browser natively (as JavaScript) and also handles servers, CLIs and agent tooling. It reaches ML through APIs (ComfyUI, LLM endpoints). |
| 2 | Python | Its ML, inference, data and science libraries can't be replaced, the largest gap TypeScript leaves. |
| 3 | Go | Single static binaries, cheap long-running services, fast compiles, and a small language AI writes reliably. Takes over backends and CLIs from TypeScript. |
| 4 | Rust | For when Go measurably falls short: no garbage collector, predictable latency, WASM, systems code. |
| 5 | Swift | Native iOS and macOS apps. |
| 6 | Kotlin | Native Android apps, plus the JVM ecosystem. |
| 7 | C | Microcontrollers (ESP32, Arduino), kernel and driver work, and the shared interface every other language can call into. |
| 8 | C++ | CUDA kernels, llama.cpp, game engines, and existing high-performance code bases. |
| 9 | Lua | Scripting embedded in other programs: Neovim, game mods, nginx/OpenResty, Redis. |
| 10 | Elixir | Highly concurrent services that recover from failure on their own (chat, realtime, many connections). |
| 11 | C# | Unity games, Windows desktop apps, and .NET shops. |
| 12 | R | Statistics and bioinformatics; many medical and research methods are published only as R packages. |
| 13 | Nix | Declarative, exactly rebuildable machine and environment configuration (NixOS). |
| 14 | Zig | A modern C replacement, and a drop-in C/C++ cross-compiler, also used as the cross-linker for cgo and Rust builds. |
| 15 | PHP | Extending self-hosted software: WordPress, Nextcloud apps, MediaWiki. |
| 16 | Verilog / SystemVerilog | Hardware design: FPGAs and custom chips. |
| 17 | Assembly | Bootloaders, reverse engineering, security CTFs, and reading compiler output. |
| 18 | Dart | Flutter: one UI codebase for iOS, Android, desktop and web, instead of two native apps. |
| 19 | Ruby | Extending existing tools: Homebrew formulas, Rails apps, Metasploit modules. |
| 20 | Solidity | Smart contracts on Ethereum and other EVM chains. |

Rows 1–6 are the six languages this template supports. From row 7 on, each language is worth adding only when that specific kind of project comes up.
