import discord


EMBED_COLOR = 0x8B0000 #couleur principale (pour les embeds)


LOGO_URL = "https://media.discordapp.net/attachments/1446652392245559306/1450675570944774288/IMG_7305.png"  #logo du serv FORMAT CARRER, et aussi priviligiez imgur comme lien de l'image car discord ca expire


CHANNELS = {
    "tickets_panel": 1450667899785314425, #channel ou le pannel de ticket sera pris en compte et sera
    "tickets_category": 1450670358712680478, #categorie ou les tickets vont se crées
    "tickets_logs": 1450667943896809603, #channel ou les logs vont se mettre
    "rdv_planning": 1450960008601800910, #channel ou l'embed planning sera
    "absences": 1450980209808638073,   #channel ou l'embed absence sera
    
   
    "reglement_gen": 0,       # channel pour le règlement général ca s'envoie QUE si le channel est vide
    "reglement_discord": 0,   # channel pour le règlement discord ca s'envoie QUE si le channel est vide
    "liens_utiles": 0         # channel pour les liens utiles ca s'envoie QUE si le channel est vide
}

ROLES = {
    "support": 1450670481144549446, #id DU ROLE qui aura acces aux ticket et sera conciderer comme staff pour declarer des abscences
    "super_admin": 1450670481144549446  #id DU ROLE qui recevera les alertes d'abscences
}


GUILD_ID = 1443995814765793405 #id du serveur IMPORTANT POUR SYNCHRO COMMANDES


def create_embed(title: str, description: str = None, footer: str = None) -> discord.Embed:
    """Crée un embed avec le style Remember RolePlay."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR
    )
    if LOGO_URL:
        embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(text=footer or "Remember RolePlay")
    return embed
