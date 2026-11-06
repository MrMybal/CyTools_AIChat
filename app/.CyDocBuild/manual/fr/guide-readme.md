---
id: guide-readme
title: Fonctions et installation
description: Choisissez le parcours adapté et préparez l’application.
section: Guide
order: 20
parent: overview
sourceRevision: cff542b721c60bc1
---

Discutez avec des agents en ligne de commande, des fournisseurs HTTP ou un modèle GGUF local. Gardez plusieurs conversations en onglets et ajoutez la dictée ou la lecture des réponses lorsque les moteurs correspondants sont installés.

## Parcours principal {#workflow}

1. Ouvrez Providers et lancez la détection. Sélectionnez un fournisseur installé et connecté, ou configurez sa connexion API.
2. Pour un modèle local, installez le moteur CPU ou CUDA et des poids compatibles dans Models. Vérifiez le fournisseur et le modèle sélectionnés dans l’en-tête de la conversation.
3. Créez un onglet de conversation, saisissez un message et envoyez-le. Utilisez l’annulation pour arrêter une réponse ; exportez la conversation pour en conserver une copie séparée.

## Prérequis et installation {#requirements}

Les fournisseurs distants ne nécessitent pas de GPU. Les modèles GGUF locaux utilisent le moteur llama.cpp CPU ou CUDA choisi. La dictée et la synthèse vocale s’installent séparément dans Speech ; installer un modèle de discussion ne les installe pas.

Consultez [Installation et modèles](doc:installation) pour la préparation, le [Guide d’utilisation](doc:guide-lisez-moi) pour les commandes détaillées et [Automatisation et API](doc:operations) pour les contrats des opérations publiques.
