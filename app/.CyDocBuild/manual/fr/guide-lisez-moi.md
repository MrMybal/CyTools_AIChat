---
id: guide-lisez-moi
title: Guide d’utilisation
description: Utilisez l’application étape par étape.
section: Guide
order: 10
parent: overview
sourceRevision: 3245ec27555941ea
---

## CyTools_AIChat {#cytools-aichat}

Un moteur de discussion : plusieurs conversations ouvertes en onglets, gardées sur le disque, avec les modèles auxquels vous avez déjà accès — Codex, Claude Code, Antigravity, un point d'accès OpenAI-compatible, Ollama — et avec des modèles GGUF locaux auxquels vous pouvez appliquer des LoRA.

## Démarrer {#demarrer}

Double-cliquez **`CyTools_AIChat.exe`**. Rien d'autre à configurer : pas de terminal, pas de JSON à éditer.

La fenêtre a quatre onglets, plus ceux fournis par le socle CyTools (journal, bibliothèque de modèles, opérations avancées, options) :

- **Discussion** — la liste de vos conversations à gauche, un onglet par conversation ouverte à droite. Choisissez un fournisseur, éventuellement un modèle, écrivez, envoyez.
- **Fournisseurs** — ce qui a été trouvé sur la machine, et où saisir une clé API ou une URL.
- **Modèles** — le moteur llama.cpp, les modèles et les LoRA téléchargeables, et ce qui est chargé en mémoire en ce moment.
- **Mises à jour** — application, moteur et poids, trois flux séparés.

L'interface est en anglais par défaut. **Options → Language → Français** la bascule sans redémarrer, et le choix est conservé. Le thème (cinq au choix) et la densité (compacte ou confortable) se règlent au même endroit.

## Choisir un fournisseur {#choisir-un-fournisseur}

Deux familles, et la différence compte :

- **Fournisseurs à session** (Codex, Claude Code, Antigravity, OpenCode). Ils gardent l'historique de leur côté ; l'outil reprend leur session à chaque tour. Ils utilisent le compte auquel vous êtes déjà connecté dans leur propre programme : aucune clé à saisir ici. Le bouton **Nouvelle session fournisseur** repart de zéro chez eux sans effacer votre transcription.
- **Fournisseurs sans état** (point d'accès OpenAI-compatible, Claude API, Ollama, modèle local). L'outil leur renvoie toute la conversation à chaque tour : ce qui est enregistré *est* le contexte. Le réglage **Limite d'historique** permet de n'envoyer que les N derniers messages.

Une clé API saisie dans **Fournisseurs** est scellée avec DPAPI pour votre compte Windows. Elle n'apparaît jamais dans un paramètre de job, dans une configuration enregistrée, dans un évènement ni dans le journal. Vous pouvez aussi ne rien enregistrer et exporter la variable d'environnement que l'onglet indique.

## Utiliser un modèle local {#utiliser-un-modele-local}

1. **Modèles → moteur llama.cpp → Installer.** Prenez CUDA si vous avez une carte NVIDIA, sinon CPU.
2. Dans la liste en dessous, cochez la licence puis **Télécharger** un modèle.
3. Dans la discussion, choisissez le fournisseur **Local model (llama.cpp)** et ce modèle.

Un modèle de raisonnement (les hybrides Qwen3, GPT-OSS) réfléchit avant de répondre, et cette réflexion consomme le budget de jetons. Le catalogue règle donc **Effort de raisonnement** par modèle ; vous pouvez le changer par conversation. La réflexion s'affiche à part et n'est jamais enregistrée comme réponse. Si un modèle épuise son budget à réfléchir, le message d'erreur le dit et propose d'augmenter *Jetons maximum* ou de mettre l'effort à « none ».

Le modèle reste chargé entre les messages pour que le tour suivant démarre tout de suite. **Modèles → Décharger le modèle** libère la mémoire.

Pour un **LoRA** : téléchargez-en un depuis la même liste, ou ajoutez un `.gguf` déjà présent sur la machine par l'onglet *Modèles / calcul*. Il apparaît ensuite dans *Invite système et réglages* de la conversation, avec un curseur d'intensité. Changer l'intensité agit immédiatement ; changer la liste des adaptateurs chargés redémarre le serveur local.

## Dicter et écouter {#dicter-et-ecouter}

L'onglet **Voix** installe deux environnements (environ 1,6 Go et 7,5 Go, créés sous `runtime/engines`), puis les modèles, après acceptation de leur licence :

- **Dictée** : *Dicter*, dans la zone de saisie, enregistre le micro et les mots s'écrivent pendant que vous parlez, avec environ une demi-seconde de retard ; la phrase en cours peut encore se corriger jusqu'à la pause suivante. Le message n'est envoyé que lorsque vous appuyez sur *Envoyer*. La première dictée d'une session met quelques secondes à démarrer, le temps de charger le modèle. Parakeet TDT 0.6B v3 comprend le français (et 24 autres langues) ; Phonon-2, beaucoup plus léger, est fait pour l'anglais. La dictée tourne sur le processeur : environ 1 seconde pour 20 secondes de parole.
- **Lecture** : *Lire à voix haute* sur une réponse, ou la case *Lire les réponses* pour les entendre au fil de l'eau. La lecture commence dès que la première phrase est prête (environ 1,5 s une fois la voix chargée) pendant que la suite se fabrique ; *Arrêter* coupe le son aussitôt. Le Markdown (code, liens, mise en forme) n'est pas lu. XTTS-v2 parle français et propose 58 voix de studio ; F5-TTS existe en version française et anglaise et imite toujours un extrait de voix.
- **Voix** : enregistrez ou importez un extrait de 6 à 12 secondes ; les mots prononcés sont retrouvés par la dictée. La langue est devinée d'après le texte, ou fixée dans les réglages.

XTTS-v2 et F5-TTS ne sont autorisés que pour un usage non commercial, y compris pour l'audio qu'ils produisent.

## Vos conversations {#vos-conversations}

Le texte des messages se sélectionne à la souris et se copie avec Ctrl+C ; *Copier* copie un message entier.

Elles sont dans `data/conversations/`, un fichier JSON lisible par conversation. Fermer un onglet ne supprime rien. Pour retirer une conversation, survolez-la et cliquez sur la corbeille ; pour en retirer plusieurs, cliquez sur la coche à côté de CONVERSATIONS, cochez-les puis **Supprimer**. Elles sont déplacées dans `data/conversations/deleted/` : rien n'est effacé et rien n'est envoyé ailleurs. Une mise à jour de l'application ne touche jamais `data/`.

Les boutons **Copier la conversation** et **Exporter en Markdown** sont sous la zone de saisie ; les exports arrivent dans `data/exports/`.

## Quand quelque chose ne va pas {#quand-quelque-chose-ne-va-pas}

- **« Choisissez un fournisseur avant d'envoyer. »** — aucun fournisseur n'est sélectionné pour cet onglet.
- **Un fournisseur est en rouge dans Fournisseurs** — dépliez sa ligne : le message dit s'il manque l'exécutable, la connexion au compte, la clé ou le serveur.
- **`Journal de l'application`** garde le démarrage, les erreurs et les diagnostics ; le texte est sélectionnable et copiable. Les jetons y sont masqués.
- Le journal du serveur local est dans `data/logs/llama-server.log`.

## Mettre à jour, revenir en arrière {#mettre-a-jour-revenir-en-arriere}

Depuis les sources : récupérez la nouvelle version, puis lancez `runtime\python\Scripts\python.exe -m pip install -r app\requirements.txt` — c'est cette commande qui met le SDK à niveau. Depuis l'onglet **Mises à jour** : l'archive est vérifiée avant d'être activée, et *Restaurer la version précédente* remet l'application et les fichiers de licence d'avant. Dans les deux sens, `data/` n'est jamais touché.
