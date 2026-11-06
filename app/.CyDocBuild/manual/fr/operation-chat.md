---
id: operation-chat
title: chat
description: Envoyer un message et stocker la réponse dans une conversation.
section: Référence
order: 200
parent: operations
sourceRevision: 47de2068bbb2332c
---

Envoyer un message et stocker la réponse dans une conversation.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `message` | `string` | Oui | Le message à envoyer.  |
| `conversation` | `string` | Non | ID de la conversation pour continuer. Vide démarre une nouvelle conversation et retourne son ID. `default=""` |
| `provider` | `string` | Non | Fournisseur avec lequel communiquer. Vide réutilise celui stocké dans la conversation. `default=""`, `enum=["", "codex", "claude-code", "antigravity", "opencode", "codebuddy", "command-code", "devin", "openai", "openrouter", "openai-compatible", "anthropic", "ollama", "llamacpp"]` |
| `transport` | `string` | Non | Identifiant du modèle pour le fournisseur. Vide réutilise le modèle de la conversation. `default=""`, `enum=["", "app-server", "cli-jsonl", "chat-completions", "messages", "native", "local-server"]` |
| `model` | `string` | Non | Identifiant du modèle pour le fournisseur. Vide réutilise le modèle de la conversation. `default=""` |
| `system_prompt` | `string` | Non | Système de prompt pour cette conversation. Un fournisseur de session qui n'a pas de champ système le reçoit plié dans le premier message, et la réponse indique que c'est le cas. `default=""` |
| `preset` | `string` | Non | ID de préréglage dont le prompt système et les valeurs de préréglage remplissent tout ce qui n'est pas explicitement défini. `default=""` |
| `engine` | `string` | Non | Compilation llama.cpp pour le fournisseur local. auto préfère une compilation CUDA installée. `default="auto"`, `enum=["auto", "cpu", "cuda"]` |
| `threads` | `integer` | Non | Threads CPU pour le fournisseur local. 0 permet à llama.cpp de décider. `default=0`, `minimum=0`, `maximum=256` |
| `keep_loaded` | `boolean` | Non | Maintenir le modèle local résident après la réponse afin que le prochain tour commence immédiatement. `default=true` |
| `reasoning_effort` | `string` | Non | Combien un modèle de raisonnement doit réfléchir avant de répondre. Vide utilise la valeur enregistrée par le catalogue pour ce modèle. "none" éteint la réflexion par le biais du gabarit de chat ; les autres niveaux sont transmis à llama.cpp. Seulement pour le fournisseur local. `default=""`, `enum=["", "default", "none", "minimal", "low", "medium", "high", "xhigh", "max"]` |
| `settings` | `object` | Non | Champs supplémentaires du fournisseur fusionnés dans la requête, pour des options qui ne sont pas nommées dans ce schéma. `default={}` |
| `temperature` | `number` | Non | Température de préréglage. Plus elle est élevée, plus la réponse est variée. Laisser vide applique la valeur par défaut du fournisseur. `minimum=0`, `maximum=2` |
| `top_p` | `number` | Non | Seuil de prise en compte des noyaux. `minimum=0`, `maximum=1` |
| `top_k` | `integer` | Non | Conserver uniquement les K tokens les plus probables. Ignoré par les fournisseurs qui ne l'exposent pas. `minimum=0`, `maximum=1000` |
| `max_tokens` | `integer` | Non | Nombre maximum de tokens dans la réponse. `minimum=1`, `maximum=131072` |
| `repeat_penalty` | `number` | Non | Pénalité appliquée aux tokens répétés. Seulement les fournisseurs locaux et Ollama la prennent en compte. `minimum=0`, `maximum=4` |
| `seed` | `integer` | Non | Grain de la prise en compte lors du chargement d'un modèle local. Modification de ce paramètre redémarre le serveur local. `minimum=-1`, `maximum=2147483647` |
| `context_tokens` | `integer` | Non | Taille du contexte demandée lors du chargement d'un modèle local. Modification de ce paramètre redémarre le serveur local. `minimum=512`, `maximum=1048576` |
| `history_limit` | `integer` | Non | Envoyer uniquement les N derniers messages stockés à un fournisseur sans mémoire. 0 envoie toute la conversation. Un fournisseur de session conserve son propre historique et l'ignore. `minimum=0`, `maximum=1000` |
| `model_profile` | `string` | Non | ID de la bibliothèque de modèles locaux; une chaîne vide utilise le modèle intégré sélectionné. `default=""` |
| `loras` | `array` | Non | Voir les paramètres de l’opération. `default=[]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `conversationId` | `string` | Oui | Conversation dans laquelle la réponse a été stockée.  |
| `messageId` | `string` | Oui | Identifiant de la réponse d'assistant stockée.  |
| `text` | `string` | Oui | Texte de la réponse.  |
| `providerId` | `string` | Oui | Fournisseur qui a produit la réponse.  |
| `transport` | `string` | Oui | Transport utilisé.  |
| `model` | `string` | Oui | Modèle rapporté par le fournisseur.  |
| `kind` | `string` | Oui | stateless lorsque le transcript est le contexte, session lorsque le fournisseur conserve l'historique.  |
| `usage` | `object` | Oui | Compte de token comme rapporté par le fournisseur, lorsque le fournisseur en rapporte.  |
| `seconds` | `number` | Oui | Durée réelle du tour.  |
| `nativeSessionId` | `string` | Oui | Identifiant de session du fournisseur, lorsque le fournisseur en a un.  |
| `thinkingCharacters` | `integer` | Oui | Caractères du texte de raisonnement streamés mais non stockés dans la réponse.  |
| `file` | `string` | Oui | Fichier Markdown contenant la réponse dans l'espace de travail du job.  |
| `mimeType` | `string` | Oui | MIME type du fichier de réponse.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`, `processSpawn`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation chat
```
