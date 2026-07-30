# Sauvegardes quotidiennes sur PythonAnywhere

Dans l’onglet **Tasks** de PythonAnywhere, ajouter une tâche quotidienne à
`00:00` (fuseau du compte PythonAnywhere) :

```bash
cd /home/smicha/smicha && /usr/bin/python3.10 -m scripts.run_backup
```

Adapter le chemin Python à la version disponible sur le compte. La commande crée
un export cohérent de la base, inscrit le fichier dans l’administration et supprime
automatiquement les sauvegardes ordinaires âgées de plus de sept jours. Les
sauvegardes marquées « conserver » ne sont jamais supprimées automatiquement.

Pour PostgreSQL, installer/activer `pg_dump` et définir `DATABASE_URL`; la même
commande produit alors un export SQL. Définir `BACKUP_DIR` vers un répertoire non
public et sauvegardé par l’hébergeur si nécessaire.

## Déclenchement depuis un autre compte PythonAnywhere

Sur le compte qui héberge l’application, définir une clé aléatoire longue dans les
variables d’environnement du web app, puis recharger l’application :

```bash
BACKUP_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Conserver cette valeur secrète. Sur l’autre compte, copier
`scripts/request_remote_backup.py`, définir les deux variables puis l’exécuter :

```bash
export BACKUP_API_URL="https://smicha.pythonanywhere.com/api/backup-db"
export BACKUP_API_KEY="la-meme-cle-secrete"
python3 request_remote_backup.py
```

Cette requête ne télécharge pas la base : elle demande à l’application principale
de créer son fichier de sauvegarde privé. Sans `BACKUP_API_KEY`, l’endpoint est
entièrement désactivé.
