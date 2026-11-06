---
id: installation
title: Installation and models
description: Prepare the runtime, engines and optional models.
section: Guide
order: 5
parent: overview
revision: 622cbe034ad452ba
---

## Start the application {#start}

Open `CyTools_AIChat.exe` on Windows. If the private runtime is missing, follow the installation steps in [Features and installation](doc:guide-readme). Launchers and engine requirements differ by application; do not assume that a copied source folder is a portable installation.

## Engines and models {#models}

Remote providers do not require a GPU. Local GGUF models use the selected llama.cpp CPU or CUDA engine. Dictation and speech synthesis have separate installation steps in Speech; a chat model does not install them.

Read the licence and source shown for each component before downloading. When access is restricted, open the official model page, obtain access with your account and authenticate locally. Do not paste credentials into generation settings.

## Storage {#storage}

Keep application data and model weights separate from the application files. Check the selected installation folder and available disk space before starting a large download. Changing a download-cache setting does not move existing models.
