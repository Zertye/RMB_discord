# Remember RolePlay Bot

Bot Discord de gestion pour le serveur Remember RolePlay. Il gère les tickets de support, le planning des entretiens et les absences du staff.

---

## 🎫 Système de Tickets

Le bot propose un panneau de tickets avec 4 catégories :

| Catégorie | Description |
|-----------|-------------|
| ⚠️ **Plainte** | Déposer une plainte contre un joueur |
| 🆕 **Nouveau projet** | Proposer un nouveau projet |
| 🔄 **Reprise de projet** | Reprendre un projet existant |
| 📝 **Autre demande** | Toute autre demande |

### Fonctionnement

1. Un membre clique sur le menu déroulant et choisit sa catégorie
2. Un formulaire s'ouvre pour remplir les détails
3. Un salon privé est créé automatiquement
4. Le staff est notifié et peut prendre en charge le ticket

### Boutons du staff dans les tickets

- **Prendre en charge** : Indique que vous gérez ce ticket
- **Fermer** : Ferme le ticket (avec ou sans transcript)
- **Ajouter** : Ajoute un membre au ticket
- **RDV** : Propose un rendez-vous vocal au membre

---

## 📅 Planning des Entretiens

Quand un membre du staff propose un RDV dans un ticket :

1. Le membre choisit un jour et une heure
2. Le staff reçoit un MP pour confirmer ou contre-proposer
3. Une fois confirmé, le RDV apparaît dans le planning public
4. Le propriétaire du serveur est notifié par MP

Le planning se met à jour automatiquement et supprime les RDV passés.

---

## 🏖️ Gestion des Absences

Le panneau des absences permet au staff de déclarer leurs indisponibilités.

### Pour le staff

- Cliquer sur **"Déclarer une absence"** dans le panneau
- Remplir les dates (format : `25/12` ou `25/12/2024`) et la raison
- L'absence apparaît dans le tableau

### Notifications automatiques

Quand une absence est déclarée, le propriétaire du serveur et les super admins reçoivent un MP de notification.

---

## ⚙️ Commandes

### Commandes Administrateur

| Commande | Description |
|----------|-------------|
| `/setup_tickets` | Installe le panneau de tickets dans le salon actuel |
| `/setup_absences` | Installe le panneau des absences dans le salon actuel |
| `/reprise_add [nom] [prioritaire]` | Ajoute un projet à la liste des reprises |
| `/reprise_remove [nom]` | Retire un projet de la liste des reprises |
| `/clear_rdv` | Supprime tous les rendez-vous du planning |
| `/clear_absences` | Supprime toutes les absences déclarées |
| `/forcer_absence [membre] [debut] [fin] [raison]` | Déclare une absence pour un membre du staff |
| `/sync_commands` | Resynchronise les commandes (en cas de problème) |

### Commandes Staff

| Commande | Description |
|----------|-------------|
| `/mes_absences` | Voir et supprimer mes absences déclarées |

---

## 🔧 Configuration (config.py)

Le fichier `config.py` contient tous les paramètres à personnaliser :

### Apparence

```python
EMBED_COLOR = 0x8B0000  # Couleur des embeds (format hexadécimal)
LOGO_URL = "https://..."  # URL du logo (doit être un lien permanent, pas Discord)
```

> ⚠️ **Important** : Les liens Discord CDN expirent ! Utilisez un hébergeur comme Imgur pour le logo.

### Salons (CHANNELS)

```python
CHANNELS = {
    "tickets_panel": 123456789,      # Salon où afficher le panneau tickets
    "tickets_category": 123456789,   # Catégorie où créer les tickets
    "tickets_logs": 123456789,       # Salon des logs de fermeture
    "rdv_planning": 123456789,       # Salon du planning des RDV
    "absences": 123456789            # Salon du panneau des absences
}
```

**Pour obtenir un ID** : Activez le mode développeur dans Discord (Paramètres > Avancé), puis clic droit sur un salon > "Copier l'identifiant".

### Rôles (ROLES)

```python
ROLES = {
    "support": 123456789,      # Rôle staff (accès aux tickets)
    "super_admin": 123456789   # Rôle super admin (notifications absences)
}
```

### Serveur

```python
GUILD_ID = 123456789  # ID de votre serveur Discord
```

---

## 🔐 Variables d'Environnement (.env)

Créez un fichier `.env` à la racine avec :

```
CLIENT_ID=123456789
DISCORD_TOKEN=votre_token_ici
DATABASE_URL=postgresql://user:password@host:port/database
```

| Variable | Description |
|----------|-------------|
| `CLIENT_ID` | ID du bot (pas le token) |
| `DISCORD_TOKEN` | Token secret du bot |
| `DATABASE_URL` | Lien de connexion PostgreSQL |

> La base de données est testée avec PostgreSQL. Compatibilité avec d'autres DB non garantie.

---

## 🚀 Installation Rapide

1. **Configurer les IDs** dans `config.py` (salons, rôles, serveur)

2. **Configurer le `.env`** (voir section ci-dessus)

3. **Installer les dépendances** :
   ```
   pip install -r requirements.txt
   ```

4. **Lancer le bot** :
   ```
   python main.py
   ```

5. **Installer les panneaux** :
   - Allez dans le salon des tickets et tapez `/setup_tickets`
   - Allez dans le salon des absences et tapez `/setup_absences`

---

## 📋 Projets de Reprise par Défaut

Le bot inclut ces projets de reprise par défaut :

- Fermier
- Agent Immobilier
- LSPD
- Ballas
- Vagos ⚡ (prioritaire)
- Families ⚡ (prioritaire)

Utilisez `/reprise_add` et `/reprise_remove` pour personnaliser cette liste.

---

## ❓ Résolution de Problèmes

| Problème | Solution |
|----------|----------|
| Commandes en double | Utilisez `/sync_commands` |
| Logo ne s'affiche pas | Vérifiez que l'URL est permanente (pas Discord) |
| "BDD indisponible" | Vérifiez `DATABASE_URL` dans le fichier `.env` |
| Boutons ne fonctionnent plus | Redémarrez le bot |
