# CyTools_AIChat — règles de développement

Lire `README.md`, `Docs/CapabilityCoverage.md` et, dans `Docs/`, `AgentGuide.md`,
`StandaloneDelivery.md`, `Localization.md`, `GenerationConfigurations.md`,
`StandaloneDiagnosticsAndModels.md` et `FullOperationAccess.md`.

## Ce que cet outil est

Un moteur de discussion. Un tour est un job soumis au `Runtime` de CyToolsCore ; l'interface,
la CLI et MCP passent tous par là. Il n'existe qu'un scheduler, qu'un registre de jobs et
qu'un modèle résident, dans le processus du runtime.

## Règles propres à ce Tool

- **Ne pas réimplémenter le Core.** Validation, jobs, sessions, workspaces, évènements,
  ordonnancement, téléchargements et transports viennent du SDK.
- **Un fournisseur déclare sa famille.** `STATELESS` signifie que la transcription stockée
  est le contexte ; `SESSION` signifie que le fournisseur garde l'historique et qu'on le
  reprend par identifiant natif. Cette distinction est écrite dans chaque message stocké :
  ne pas la gommer.
- **Aucun secret dans un job.** Une clé API se lit au moment de l'appel depuis
  `aichat/credentials.py` et se place dans un en-tête. Jamais dans `argv`, dans les
  paramètres d'une opération, dans une configuration de génération, dans un évènement ni
  dans le journal.
- **Copier des poids, jamais les lier.** `app/scripts/import_models.py` duplique en entier un
  fichier déjà téléchargé par un autre CyTool et vérifie la copie contre l'empreinte du
  catalogue. Un lien dur ou symbolique ferait dépendre deux Tools d'un même fichier :
  désinstaller le modèle d'un côté casserait l'autre.
- **Le worker réserve les poids, pas le job.** L'estimateur d'un tour ne compte que sa propre
  surcharge ; le modèle résident réserve le périphérique tant que son processus tourne.
  Compter les mêmes gigaoctets des deux côtés double le besoin et refuse un modèle de 20 Go
  sur une carte de 24 Go qui le contient.
- **Le paquet de release exclut les fichiers de travail.** `app/scripts/build_release.py`
  construit l'archive `app/` attendue par le flux de mise à jour sans `AGENTS.md`,
  `CyToolsGuide.md`, `Docs/AgentGuide.md`, `Docs/AgentPrompt.md` ni les caches. Ces fichiers restent dans le dépôt ; ils ne font pas partie du produit livré.
- **`data/` n'est jamais remplacé.** Ni par une mise à jour, ni par une réinstallation du
  moteur, ni pour « faire le ménage ». Supprimer une conversation la déplace dans
  `data/conversations/deleted/`.
- **La bibliothèque vendue reste telle quelle.** `aichat/vendor/cyai_connectors/` est une
  copie de sa source amont. Pour changer son comportement, l'étendre depuis
  `aichat/providers/agentcli.py` — comme le fait déjà l'ajout de `--append-system-prompt`
  et la normalisation de sa ponctuation typographique.
- **Résoudre les chemins à l'appel.** `catalog` et `maintenance` lisent `paths.X` au moment
  où ils en ont besoin, pas à l'import. Figer un chemin à l'import crée une dépendance à
  l'ordre des imports qui ne se voit que le jour où quelque chose redirige le répertoire de
  données.
- **Les CLI d'agent sont ouvertes en lecture seule**, demandes d'autorisation refusées. Cet
  outil sert à parler au modèle, pas à le laisser agir sur la machine.
- **Groupes d'exclusivité (CyToolsCore 0.10).** `build_manifest.py` déclare
  `exclusiveGroups` pour les opérations qui travaillent sur les mêmes fichiers :
  `model-files`, `engine-files`, `application-update`. C'est le scheduler du SDK qui les
  sérialise ; ne pas ajouter de file d'attente dans les handlers. `chat` n'appartient à
  aucun groupe : un groupe vaut pour l'opération entière et sérialiserait tous les
  onglets. Seuls les tours du modèle local sont sérialisés, par le fournisseur local, parce
  que le serveur llama.cpp n'a qu'un slot.
- **`LICENCES/` fait partie du produit livré.** `LICENCES/CyToolsCore-MIT.txt` est la copie
  inchangée de la licence du SDK installé, `LICENCES/SOURCES.txt` liste les sources ;
  l'archive de release les embarque avec `LICENSE`, l'updater refuse une archive qui ne les
  contient pas et les déploie à côté de `app/`. Textes de licence en anglais.

## Interface

Anglais par défaut, français sélectionnable. Écrire le texte anglais dans `tr(...)` ou
`label(...)`, ajouter la traduction dans `locales/aichat-fr.json`, puis exécuter
`app/scripts/merge_translations.py`. Son option `--check` sort en erreur s'il manque une
entrée. Ne jamais traduire un identifiant, un chemin, un nom de modèle, une invite ou le
texte saisi par l'utilisateur.

La police embarquée ne couvre pas le bloc des formes géométriques : rester en ASCII pour les
marqueurs d'état, sinon ils s'affichent en carrés vides.

Après toute modification d'un paramètre ou d'un fournisseur : régénérer le manifeste avec
`app/build_manifest.py`.

## Preuves

Une capacité n'est annoncée que si elle a été exécutée. `app/platform-tested.json` ne se
remplit qu'à partir de vraies exécutions, et `Docs/CapabilityCoverage.md` sépare
« implémenté et testé », « implémenté non validé » et « non exposé » avec la raison. Les
rapports vivent dans `data/reports/`.

```powershell
runtime\python\Scripts\python.exe -m pytest app\tests -q
runtime\python\Scripts\python.exe app\tests\acceptance_local.py --engine cuda
runtime\python\Scripts\python.exe app\tests\acceptance_http.py --engine cuda
runtime\python\Scripts\python.exe app\tests\acceptance_mcp.py
runtime\python\Scripts\python.exe app\tests\acceptance_update.py
```
