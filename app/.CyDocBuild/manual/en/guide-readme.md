---
id: guide-readme
title: Features and installation
description: Choose the right workflow and prepare the application.
section: Guide
order: 20
parent: overview
revision: cff542b721c60bc1
---

Chat with connected agent CLIs, HTTP providers or a local GGUF model. Keep separate conversations in tabs and add dictation or spoken replies when their engines are installed.

## Main workflow {#workflow}

1. Open Providers and run detection. Select a provider that is installed and authenticated, or configure its API connection.
2. For a local model, install the CPU or CUDA engine and compatible weights from Models. Check the selected provider and model in the conversation header.
3. Create a conversation tab, enter a message and send it. Use cancellation to stop a reply; export the conversation when you need a separate copy.

## Requirements and installation {#requirements}

Remote providers do not require a GPU. Local GGUF models use the selected llama.cpp CPU or CUDA engine. Dictation and speech synthesis have separate installation steps in Speech; a chat model does not install them.

Read [Installation and models](doc:installation) for setup, the [User guide](doc:guide-lisez-moi) for detailed controls, and [Automation and API](doc:operations) for the public operation contracts.
