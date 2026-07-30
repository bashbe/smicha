# Sauvegardes quotidiennes sur PythonAnywhere

Dans l’onglet **Tasks** de PythonAnywhere, ajouter une tâche quotidienne à
`00:00` (fuseau du compte PythonAnywhere) :

```bash
cd /home/VOTRE_UTILISATEUR/smiha-flask && /usr/bin/python3.10 -m scripts.run_backup
```

Adapter le chemin Python à la version disponible sur le compte. La commande crée
un export cohérent de la base, inscrit le fichier dans l’administration et supprime
automatiquement les sauvegardes ordinaires au-delà des sept dernières. Les
sauvegardes marquées « conserver » ne sont jamais supprimées automatiquement.

Pour PostgreSQL, installer/activer `pg_dump` et définir `DATABASE_URL`; la même
commande produit alors un export SQL. Définir `BACKUP_DIR` vers un répertoire non
public et sauvegardé par l’hébergeur si nécessaire.
