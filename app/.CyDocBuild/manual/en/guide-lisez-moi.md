---
id: guide-lisez-moi
title: User guide
description: Use the application step by step.
section: Guide
order: 10
parent: overview
revision: 3245ec27555941ea
---

## CyTools_AIChat {#cytools-aichat}

A discussion engine: multiple open conversations in tabs, saved on disk, with access to models you already have — Codex, Claude Code, Antigravity, an OpenAI-compatible point of access, Ollama — and local GGUF models to which you can apply LoRA.

## Start {#demarrer}

Double-click `CyTools_AIChat.exe`. No other configuration is needed: no terminal, no JSON to edit.

The window has four tabs, plus those provided by the CyTools base (journal, model library, advanced operations, options):

- Discussion — the list of your conversations on the left, one tab per open conversation on the right. Choose a provider, optionally a model, write, send.
- Providers — what was found on the machine, and where to enter a API key or a URL.
- Models — the llama.cpp engine, downloadable models and LoRA, and what is currently loaded in memory.
- Updates — application, engine, and weights, three separate streams.

The interface is in English by default. Options → Language → Français switches it without restarting, and the choice is remembered. You can choose from five themes and set the density (compact or comfortable) in the same place.

## Choose a provider {#choisir-un-fournisseur}

Two families, and the difference matters:

- Session providers (Codex, Claude Code, Antigravity, OpenCode). They keep their own history; the tool resumes their session on each turn. They use the account you are already logged into in their own program: no key to enter here. The New session provider button starts from zero with them without erasing your transcription.
- Stateless providers (OpenAI-compatible access point, Claude API, Ollama, local model). The tool sends the entire conversation on each turn: what is recorded is the context. The History limit setting allows you to send only the last N messages.

A API key entered in Providers is sealed with DPAPI for your Windows account. It never appears in a job parameter, in a saved configuration, in an event, or in the log. You can also choose not to save it and export the environment variable that the tab indicates.

## Use a local model {#utiliser-un-modele-local}

1. Models → Llama.cpp engine → Install. Use CUDA if you have a NVIDIA card, otherwise use CPU.
2. In the list below, check the license and then Download a model.
3. In the discussion, choose the Local model (llama.cpp) provider and this model.

A reasoning model (hybrids Qwen3, GPT-OSS) thinks before responding, and this thinking consumes the token budget. The catalog therefore sets Reasoning effort per model; you can change it per conversation. The thinking is displayed separately and is never recorded as a response. If a model exhausts its thinking budget, an error message is displayed and suggests increasing Maximum tokens or setting the effort to 'none'.

The model remains loaded between messages so that the next turn starts immediately. Models → Unload the model frees memory.

For a LoRA: download another one from the same list, or add a `.gguf` already present on the machine via the Models / Calcul tab. It then appears in the system prompt and conversation settings with an intensity slider. Changing the intensity acts immediately; changing the list of loaded adapters restarts the local server.

## Dictate and listen {#dicter-et-ecouter}

The Voice tab installs two environments (approximately 1.6 Go and 7.5 Go, created under `runtime/engines`), then the models, after acceptance of their license:

- Dictation : Dictate, in the input area, records the microphone and the words write while you speak, with about a half-second delay; the current sentence can still be corrected until the next pause. The message is sent only when you press Send. The first dictation of a session takes a few seconds to start, the time to load the model. Parakeet TDT 0.6B v3 includes French (and 24 other languages); Phonon-2, much lighter, is made for English. Dictation runs on the processor: about 1 second for 20 seconds of speech.
- Read aloud: choose Read aloud on a response, or enable Read responses to hear them as they arrive. Playback begins as soon as the first sentence is ready (about 1.5 seconds once the voice is loaded), while the rest is synthesized. Stop silences playback immediately. Markdown code and formatting are not spoken. XTTS-v2 speaks French and provides 58 studio voices; F5-TTS has French and English versions and always uses a reference voice sample.
- Voice : record or import an excerpt of 6 to 12 seconds ; the words pronounced are recognized by dictation. The language is guessed from the text, or set in the settings.

XTTS-v2 and F5-TTS are only authorized for non-commercial use, including the audio they produce.

## Your conversations {#vos-conversations}

The text of messages is selected with the mouse and copied with Ctrl+C; Copy copies an entire message.

They are in `data/conversations/`, a JSON readable by conversation. Closing a tab does not delete anything. To remove a conversation, hover over it and click on the trash; to remove several, click on the check next to CONVERSATIONS, check them then Delete. They are moved to `data/conversations/deleted/`: nothing is erased and nothing is sent elsewhere. An update of the application never touches `data/`.

The Copy conversation and Export to Markdown buttons are below the input area; exports go to `data/exports/`.

## When something goes wrong {#quand-quelque-chose-ne-va-pas}

- "Choose a provider before sending. " — no provider is selected for this tab.
- A provider is in red in Providers — expand its line: the message says if the executable is missing, the connection to the account, the key, or the server.
- `Journal de l'application` keeps the start, errors, and diagnostics; the text is selectable and copyable. Tokens are masked.
- The local server log is in `data/logs/llama-server.log`.

## Update, revert {#mettre-a-jour-revenir-en-arriere}

Since the sources: retrieve the new version, then launch `runtime\python\Scripts\python.exe -m pip install -r app\requirements.txt` — it is this command that updates SDK. Since the Updates tab: the archive is verified before being activated, and Restore previous version resets the application and the license files to before. In both directions, `data/` is never touched.
