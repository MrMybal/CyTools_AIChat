---
id: installation
title: Installation et modèles
description: Préparez le programme, les moteurs et les modèles facultatifs.
section: Guide
order: 5
parent: overview
sourceRevision: 622cbe034ad452ba
---

## Démarrer l’application {#start}

Ouvrez `CyTools_AIChat.exe` sous Windows. Si l’environnement privé manque, suivez [Fonctions et installation](doc:guide-readme). Les lanceurs et besoins des moteurs varient selon l’application ; un dossier de sources copié n’est pas nécessairement une installation portable.

## Moteurs et modèles {#models}

Les fournisseurs distants ne nécessitent pas de GPU. Les modèles GGUF locaux utilisent le moteur llama.cpp CPU ou CUDA choisi. La dictée et la synthèse vocale s’installent séparément dans Speech ; installer un modèle de discussion ne les installe pas.

Lisez la licence et la source affichées pour chaque composant avant téléchargement. Si l’accès est restreint, ouvrez la page officielle du modèle, obtenez l’accès avec votre compte et connectez-vous localement. Ne collez pas vos identifiants dans les réglages de génération.

## Stockage {#storage}

Séparez les données et les poids des modèles des fichiers de l’application. Vérifiez le dossier d’installation et l’espace disque avant un téléchargement volumineux. Modifier le cache de téléchargement ne déplace pas les modèles existants.
