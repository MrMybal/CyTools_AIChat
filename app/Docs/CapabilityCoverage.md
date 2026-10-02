# Couverture des capacités — CyTools_AIChat 0.1.1

Ce document est la matrice exigée par `Docs/FullOperationAccess.md`. Il sépare trois états
qui ne doivent jamais être confondus : **implémenté et testé** sur cette machine,
**implémenté mais non validé**, et **non exposé** avec la raison.

Machine de test : Windows 10 Enterprise LTSC 2021 (19044), Python 3.11.5, NVIDIA RTX 3090
24 Go (pilote 610.47), llama.cpp b11114 CUDA 12.4, cytools-core 0.9.0, imgui-bundle 1.92.900,
Ollama avec `qwen3:0.6b`, codex-cli 0.155.0, claude-code 2.1.276, Antigravity `agy`.
Date des exécutions : 2026-09-23. Les preuves sont dans `data/reports/`.

**Passage à cytools-core 0.10.1 (MIT), application 0.1.1 — réexécuté le 2026-10-02** sur la
même machine : lanceur démarré depuis un autre dossier avec la configuration existante
(onglets Chat, Mises à jour, Options), CLI (`describe`, `diagnostics`), session MCP réelle avec
deux tours sur un modèle GGUF local, LoRA GGUF (chargement et poids modifié à chaud) sur CUDA,
point d'accès OpenAI-compatible, annulation d'une inférence en cours, mécanisme de mise à
jour sur maquettes (dont le refus d'une archive sans `LICENCES/` et le déploiement des
notices), construction et vérification de l'archive de release, suite pytest. **Non
réexécuté avec cette version du SDK** : Codex, Claude Code, Antigravity, Ollama et la fenêtre
en français ; leurs lignes « Testé » ci-dessous datent du 2026-09-23, sous cytools-core 0.9.0.

## 1. Fournisseurs

Un fournisseur est soit **sans état** — cet outil lui envoie la transcription entière à
chaque tour, et la conversation stockée *est* le contexte — soit **à session** : le
fournisseur garde l'historique, et l'outil reprend sa session par identifiant natif. La
colonne « Famille » porte cette différence, qui change ce que `history_limit` fait et ce
qu'une troncature de la transcription modifie réellement.

| Fournisseur | Transport | Famille | État | Preuve |
|---|---|---|---|---|
| Codex | `app-server` (protocole du SDK Codex, processus persistant) | session | **Testé** | Tour réel, streaming, reprise de session au tour suivant ; `data/reports/mcp-acceptance.json` |
| Codex | `cli-jsonl` (`codex exec --json`) | session | **Testé** | Tour réel via la CLI |
| Claude Code | `cli-jsonl` (`claude -p --output-format stream-json`) | session | **Testé** | Tour réel avec `--append-system-prompt` |
| Antigravity | `cli-jsonl` (`agy --output-format stream-json`) | session | **Testé** | Tour réel |
| OpenCode | `cli-jsonl` (`opencode run --format json`) | session | **Implémenté, non validé** | L'exécutable CLI est absent de cette machine ; seule l'application de bureau est installée |
| CodeBuddy, Command Code, Devin | — | session | **Non exposé** | Déclarés au catalogue de connecteurs, aucun adaptateur écrit ; `list_providers` les signale `NotImplemented` au lieu de les masquer |
| Point d'accès OpenAI-compatible | `chat-completions` (SSE) | sans état | **Testé** | Serveur llama.cpp démarré par le test, deux tours, streaming, endpoint injoignable → `NetworkError` ; `data/reports/http-provider.json` |
| OpenAI API | `chat-completions` | sans état | **Implémenté, non validé** | Même adaptateur que ci-dessus, URL et clé différentes ; aucune clé disponible pour un essai réel |
| OpenRouter | `chat-completions` | sans état | **Implémenté, non validé** | Idem |
| Claude API (Anthropic) | `messages` (SSE) | sans état | **Implémenté, non validé** | Constructeur de requête distinct (`system` hors de la liste de messages, `max_tokens` obligatoire) ; aucune clé disponible |
| Ollama | `native` (`/api/chat` NDJSON) | sans état | **Testé** | Tour réel sur `qwen3:0.6b`, avec le décompte de jetons rendu par Ollama |
| Ollama | `chat-completions` (surface OpenAI d'Ollama) | sans état | **Testé** | Tour réel sur le même modèle ; `list_provider_models` renvoie ce qui est réellement téléchargé |
| Modèle local llama.cpp | `local-server` | sans état | **Testé** | Modèle GGUF chargé sur CUDA, réponse produite, serveur maintenu résident entre les tours |

« Codex SDK » et « Claude SDK » : le transport `app-server` de Codex **est** le protocole que
pilote `@openai/codex-sdk`; il est implémenté et testé ici. Aucun transport `sdk` distinct n'est
branché pour Claude Code : son adaptateur `cli-jsonl` couvre déjà le même chemin, et déclarer
un transport « SDK » sans l'exécuter serait annoncer une capacité non vérifiée. Le paquet
`claude-agent-sdk` n'est donc pas une dépendance de ce Tool.

## 2. Modèles locaux, LoRA et périphériques

| Capacité native | Champ CyTools | Contrôle standalone | État | Preuve |
|---|---|---|---|---|
| Charger un GGUF | `model`, `model_profile` | Liste Modèle + bibliothèque | **Testé** | Réponse réelle sur CUDA |
| Adaptateur LoRA GGUF | `loras[{id,strength}]` | Cases + curseur d'intensité | **Testé** | `data/reports/local-lora.json` : échelle 0 reproduit la réponse de base, échelle 1 la modifie |
| Changer l'intensité sans recharger | `lora_scale` | Curseur dans Modèles | **Testé** | Même rapport : retour à 0 à chaud restaure la réponse de base |
| Refus d'un LoRA incompatible | — | — | **Implémenté, non validé** | Le contrôle d'en-tête GGUF refuse un fichier qui n'est pas un adaptateur ; le refus par le chargeur d'une famille incompatible n'a pas été provoqué |
| Choix CPU / CUDA | `engine` | Combo Moteur | **Testé (CUDA)** | Le moteur CPU est installé et vérifié, mais aucune génération n'a été exécutée dessus |
| Fenêtre de contexte | `context_tokens` | Curseur | **Testé** | Passe à `-c` du serveur ; un changement redémarre le serveur, et une demande supérieure à ce que le modèle déclare est ramenée à sa valeur |
| Effort de raisonnement | `reasoning_effort` | Combo | **Testé** | `none` sur les hybrides Qwen3, `low` sur GPT-OSS 20B ; sans cela Qwen3 8B dépensait tout son budget à réfléchir et ne répondait pas |
| Threads CPU | `threads` | — | **Implémenté, non validé** | Passe à `-t` ; non mesuré |
| Modèle résident entre les tours | `keep_loaded` | Case + onglet Modèles | **Testé** | `resident_status` montre le processus et sa durée de vie |
| Projecteur multimodal | — | — | **Non exposé** | Le serveur est lancé avec `--no-mmproj-auto` : aucune entrée image n'est déclarée dans ce Tool |

### Modèles locaux réellement exécutés

Chacun a été chargé puis interrogé sur le GPU, un par un, le précédent étant déchargé avant le
suivant (`data/reports/local-models.json`, 2026-09-23, RTX 3090). La question posée est une
vraie question en français avec un budget de 120 jetons, pas un test en trois mots : c'est
cette forme qui a révélé que les modèles de raisonnement dépensaient tout leur budget à
réfléchir sans jamais répondre.

| Modèle | Architecture | Taille | Périphérique | Chargement + réponse | Caractères de réflexion |
|---|---|---|---|---|---|
| Qwen3 8B (Q4_K_M) | `qwen3` | 4.7 Gio | CUDA | 13.1 s | 0 |
| Qwen2.5 1.5B Instruct (Q8_0) | `qwen2` | 1.8 Gio | CUDA | 1.7 s | 0 |
| Hermes 3 Llama 3.2 3B Q4_K_M | `llama` | 1.9 Gio | CUDA | 2.5 s | 0 |
| Dolphin 3.0 Llama 3.1 8B Q4_K_M | `llama` | 4.6 Gio | CUDA | 3.2 s | 0 |
| Self After Dark 8B Q4_K_M | `llama` | 4.6 Gio | CUDA | 6.6 s | 0 |
| Gemma 4 E4B HauhauCS Aggressive Q4_K_M | `gemma4` | 5.0 Gio | CUDA | 6.0 s | 0 |
| GPT-OSS 20B Heretic ARA v3 MXFP4 | `gpt-oss` | 11.3 Gio | CUDA | 7.2 s | 28 |

Restent déclarés au catalogue mais **non exécutés** faute d'être installés ici : Qwen3 4B,
Qwen3 14B, Llama 3.2 3B Instruct, Mistral 7B v0.3, Qwen 3.6 12B Hightop, Qwen 3.8 27B Cold
Fusion. Le 27B demande environ 21 Gio de VRAM : il tient sur une 3090 mais n'a pas été essayé.

Les poids déjà téléchargés par un autre CyTool s'importent avec
`app/scripts/import_models.py`, qui **copie** les fichiers — jamais de lien — et vérifie
chaque copie contre l'empreinte du catalogue avant de l'enregistrer. Deux Tools qui
partageraient un fichier ne seraient plus indépendants.

### Modèles de raisonnement

Un modèle hybride réfléchit avant de répondre, et cette réflexion consomme le budget de
jetons. Il n'existe pas un seul interrupteur pour l'arrêter, et cela a été mesuré plutôt que
supposé, modèle par modèle :

| Mécanisme | Qwen3, Gemma 4 | GPT-OSS |
|---|---|---|
| `chat_template_kwargs.enable_thinking = false` | **coupe la réflexion** | ignoré |
| `reasoning_effort` | ignoré | **respecté** (`low` : 28 caractères de réflexion au lieu de 350) |
| `reasoning_budget: 0` par requête | ignoré | ignoré |

`reasoning_effort: none` envoie donc les deux, ce qui donne « le moins de réflexion que ce
modèle autorise » quelle que soit la famille. Le catalogue enregistre la valeur par modèle :
`none` pour les hybrides Qwen3 et Gemma 4, `low` pour GPT-OSS. Le champ `reasoning_effort`
de l'opération `chat` permet de le changer par conversation. La réflexion est diffusée sur un
canal séparé et n'est jamais enregistrée comme réponse ; si elle épuise le budget, l'erreur
`ReasoningBudgetExhausted` le dit et indique quoi changer.

L'adaptateur publié utilisé pour le test est une LoRA d'« abliteration » pour Qwen2.5 1.5B.
Le test démontre le **chargement et la pondération**, pas la qualité de ce que produit cet
adaptateur : à l'intensité 1 sur une base Q8_0 sa sortie dégénère, ce qui est une propriété
de cet adaptateur et non un défaut de l'outil.

## 3. Paramètres d'inférence

| Paramètre | Local | OpenAI-compatible | Anthropic | Ollama | CLI d'agent |
|---|---|---|---|---|---|
| `temperature`, `top_p` | oui | oui | oui | oui | non exposé par ces CLI |
| `top_k` | oui | ignoré par le serveur | oui | oui | — |
| `max_tokens` | oui | oui | oui (obligatoire, défaut 4096) | `num_predict` | — |
| `repeat_penalty` | oui | — | — | oui | — |
| `seed` | oui (`-1` = laissé au moteur) | oui | — | oui | — |
| `context_tokens` | oui (au chargement) | — | — | `num_ctx` | — |
| `history_limit` | oui | oui | oui | oui | sans effet : le fournisseur garde l'historique |
| `settings` (objet libre) | fusionné dans la requête | idem | idem | idem | idem |

Un paramètre qu'un fournisseur n'expose pas n'est pas accepté puis ignoré en silence : il
n'est simplement pas envoyé, et ce tableau dit lesquels. `extra_body` permet d'ajouter un
champ propre à un point d'accès OpenAI-compatible sans modifier le Tool.

## 4. Opérations et parité

Les 32 opérations du manifeste sont enregistrées dans le runtime (vérifié par
`test_manifest_is_valid_and_every_operation_is_registered`). Elles sont accessibles à
l'identique par la CLI, JSONL, HTTP, MCP et l'interface, puisque toutes passent par le même
`Runtime`. L'onglet **Opérations avancées** fourni par la façade donne accès à chaque
opération et à chaque champ déclaré, y compris ceux que le formulaire simplifié ne montre
pas.

Parité vérifiée : une conversation créée par MCP est visible et continuable dans la fenêtre,
et réciproquement (`data/reports/mcp-acceptance.json`, champ
`conversationVisibleInListing`).

Configuration de génération : aller-retour exact vérifié — sauvegarde du formulaire, remise
à zéro de tous les champs, rechargement, comparaison des paramètres effectifs. Aucun job
n'est démarré par un chargement et aucun secret n'entre dans le fichier
(`data/reports/configuration-round-trip-result.json`).

## 5. Annulation et libération des ressources

| Comportement | État | Preuve |
|---|---|---|
| Annuler une inférence locale en cours de génération | **Testé** | `data/reports/cancellation.json` : arrêt en 0,03 s après 87 caractères |
| La réponse partielle est conservée et marquée `Cancelled` | **Testé** | Même rapport : 115 caractères gardés dans la transcription |
| La réservation du job est libérée | **Testé** | Même rapport |
| Le modèle résident garde sa réservation | **Testé, et voulu** | `keep_loaded` signifie que les poids restent en mémoire ; libérer le budget pendant que le processus tient encore le GPU serait faux |
| Le serveur survit à l'annulation et le tour suivant fonctionne | **Testé** | Même PID avant et après, tour suivant `Completed` |
| Annuler un téléchargement de modèle ou de moteur | **Implémenté, non validé** | Le jeton d'annulation est passé au `DownloadManager` ; aucune annulation n'a été déclenchée en cours de transfert |

## 6. Mises à jour

| Élément | État | Preuve |
|---|---|---|
| Préparation, vérification, activation, restauration | **Testé avec fixtures** | `data/reports/update-acceptance.json` |
| Refus d'une archive avec traversée de chemin | **Testé** | Même rapport ; le fichier n'est pas écrit |
| Refus d'une archive appartenant à un autre Tool | **Testé** | Même rapport |
| Refus d'un ABI d'exécution différent | **Testé** | Même rapport |
| Refus d'un code qui ne compile pas | **Testé** | Même rapport |
| `data/` préservé par l'activation et la restauration | **Testé** | Même rapport |
| Archive de release construite depuis les sources, sans les fichiers de travail (`AGENTS.md`, guides IA du SDK, caches, roue) | **Testé** | `app/scripts/build_release.py --check` : extraction par la garde de l'updater puis `verify_application_tree` ; `data/reports/release-build.json` |
| Découverte et téléchargement d'une vraie release GitHub | **Non validé** | Aucun dépôt de cette application n'est publié ; l'outil refuse d'en inventer un |
| Mise à jour du moteur | **Partiel** | L'installation depuis les assets épinglés est testée ; passer à une nouvelle balise llama.cpp exige d'épingler ses empreintes dans `app/engine-assets.json` |

## 7. Ce qui n'est pas dans cette version

- **Pièces jointes et images.** Non demandées pour cette livraison. Le serveur local est
  lancé avec `--no-mmproj-auto` et aucun champ d'entrée fichier n'est déclaré.
- **Outils / appels de fonctions.** Les CLI d'agent sont ouvertes en bac à sable lecture
  seule avec les demandes d'autorisation refusées : cet outil est un endroit pour parler au
  modèle, pas pour le laisser agir sur la machine.
- **Recherche dans les conversations.** Le filtre de la liste porte sur les titres.
- **macOS et Linux.** Déclarés `Unknown` et `Experimental`. Le lanceur Linux existe mais n'a
  jamais été exécuté, et le catalogue de moteurs ne contient que des binaires Windows.
