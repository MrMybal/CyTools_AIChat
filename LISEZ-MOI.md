# CyTools_AIChat

Maintenance : **Cyberalien**.

Un moteur de discussion : plusieurs conversations ouvertes en onglets, gardées sur le disque,
avec les modèles auxquels vous avez déjà accès — Codex, Claude Code, Antigravity, un point
d'accès OpenAI-compatible, Ollama — et avec des modèles GGUF locaux auxquels vous pouvez
appliquer des LoRA.

## Démarrer

Double-cliquez **`CyTools_AIChat.exe`**. Rien d'autre à configurer : pas de terminal, pas de
JSON à éditer.

La fenêtre a quatre onglets, plus ceux fournis par le socle CyTools (journal, bibliothèque de
modèles, opérations avancées, options) :

- **Discussion** — la liste de vos conversations à gauche, un onglet par conversation
  ouverte à droite. Choisissez un fournisseur, éventuellement un modèle, écrivez, envoyez.
- **Fournisseurs** — ce qui a été trouvé sur la machine, et où saisir une clé API ou une URL.
- **Modèles** — le moteur llama.cpp, les modèles et les LoRA téléchargeables, et ce qui est
  chargé en mémoire en ce moment.
- **Mises à jour** — application, moteur et poids, trois flux séparés.

L'interface est en anglais par défaut. **Options → Language → Français** la bascule sans
redémarrer, et le choix est conservé.

## Choisir un fournisseur

Deux familles, et la différence compte :

- **Fournisseurs à session** (Codex, Claude Code, Antigravity, OpenCode). Ils gardent
  l'historique de leur côté ; l'outil reprend leur session à chaque tour. Ils utilisent le
  compte auquel vous êtes déjà connecté dans leur propre programme : aucune clé à saisir
  ici. Le bouton **Nouvelle session fournisseur** repart de zéro chez eux sans effacer votre
  transcription.
- **Fournisseurs sans état** (point d'accès OpenAI-compatible, Claude API, Ollama, modèle
  local). L'outil leur renvoie toute la conversation à chaque tour : ce qui est enregistré
  *est* le contexte. Le réglage **Limite d'historique** permet de n'envoyer que les N
  derniers messages.

Une clé API saisie dans **Fournisseurs** est scellée avec DPAPI pour votre compte Windows.
Elle n'apparaît jamais dans un paramètre de job, dans une configuration enregistrée, dans un
évènement ni dans le journal. Vous pouvez aussi ne rien enregistrer et exporter la variable
d'environnement que l'onglet indique.

## Utiliser un modèle local

1. **Modèles → moteur llama.cpp → Installer.** Prenez CUDA si vous avez une carte NVIDIA,
   sinon CPU.
2. Dans la liste en dessous, cochez la licence puis **Télécharger** un modèle.
3. Dans la discussion, choisissez le fournisseur **Local model (llama.cpp)** et ce modèle.

Sont déjà installés et vérifiés sur cette machine : Qwen2.5 1.5B, Hermes 3 Llama 3.2 3B,
Qwen3 8B, Dolphin 3.0 Llama 3.1 8B, Self After Dark 8B, Gemma 4 E4B HauhauCS et GPT-OSS 20B
Heretic. Le catalogue propose en plus Qwen3 4B, Qwen3 14B, Llama 3.2 3B, Mistral 7B v0.3,
Qwen 3.6 12B Hightop et Qwen 3.8 27B Cold Fusion, à télécharger depuis l'onglet Modèles.

Un modèle de raisonnement (les hybrides Qwen3, GPT-OSS) réfléchit avant de répondre, et cette
réflexion consomme le budget de jetons. Le catalogue règle donc **Effort de raisonnement** par
modèle ; vous pouvez le changer par conversation. La réflexion s'affiche à part et n'est
jamais enregistrée comme réponse. Si un modèle épuise son budget à réfléchir, le message
d'erreur le dit et propose d'augmenter *Jetons maximum* ou de mettre l'effort à « none ».

Le modèle reste chargé entre les messages pour que le tour suivant démarre tout de suite.
**Modèles → Décharger le modèle** libère la mémoire.

Pour un **LoRA** : téléchargez-en un depuis la même liste, ou ajoutez un `.gguf` déjà présent
sur la machine par l'onglet *Modèles / calcul*. Il apparaît ensuite dans *Invite système et
réglages* de la conversation, avec un curseur d'intensité. Changer l'intensité agit
immédiatement ; changer la liste des adaptateurs chargés redémarre le serveur local.

## Vos conversations

Elles sont dans `data/conversations/`, un fichier JSON lisible par conversation. Fermer un
onglet ne supprime rien. Supprimer une conversation la déplace dans
`data/conversations/deleted/` : rien n'est effacé et rien n'est envoyé ailleurs. Une mise à
jour de l'application ne touche jamais `data/`.

Les boutons **Copier la conversation** et **Exporter en Markdown** sont sous la zone de
saisie ; les exports arrivent dans `data/exports/`.

## Quand quelque chose ne va pas

- **« Choisissez un fournisseur avant d'envoyer. »** — aucun fournisseur n'est sélectionné
  pour cet onglet.
- **Un fournisseur est en rouge dans Fournisseurs** — dépliez sa ligne : le message dit s'il
  manque l'exécutable, la connexion au compte, la clé ou le serveur.
- **`Journal de l'application`** garde le démarrage, les erreurs et les diagnostics ; le
  texte est sélectionnable et copiable. Les jetons y sont masqués.
- Le journal du serveur local est dans `data/logs/llama-server.log`.

## Ce qui a été réellement vérifié

Sur cette machine (Windows 10 x64, RTX 3090) : le lanceur depuis un autre dossier, la
fenêtre en anglais et en français, les sept modèles locaux installés chargés et interrogés un
par un sur le GPU, un tour local sur CUDA avec et sans LoRA, l'annulation
d'une génération en cours, Codex, Claude Code, Antigravity, Ollama, un point d'accès
OpenAI-compatible, la CLI, un appel MCP réel, l'aller-retour d'une configuration de
génération, et le mécanisme de mise à jour avec des archives de test.

N'ont **pas** été vérifiés : OpenCode (sa CLI est absente de cette machine), les API payantes
OpenAI / OpenRouter / Anthropic (aucune clé disponible), Linux et macOS, et le téléchargement
d'une vraie release GitHub de cette application (aucune n'est publiée). Le détail, capacité
par capacité, est dans `app/Docs/CapabilityCoverage.md`.

## Licence

Logiciel libre sous licence **GNU GPL v3.0 uniquement** (`LICENSE`), comme le SDK
CyToolsCore sur lequel il repose. Les moteurs, la bibliothèque de connecteurs embarquée et
les poids des modèles gardent leurs propres licences : `app/licenses.json`, le catalogue et
l'onglet Options.
