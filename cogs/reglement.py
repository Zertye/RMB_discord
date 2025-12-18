import discord
from discord.ext import commands
import sys
sys.path.append("..")
from config import EMBED_COLOR, LOGO_URL, CHANNELS, create_embed

class ReglementView(discord.ui.View):
    def __init__(self, url, label):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=label, url=url, style=discord.ButtonStyle.link))

class ReglementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_and_send_reglement(self, channel_key, title, description, url, btn_label):
        """Vérifie si le salon est vide et envoie l'embed."""
        channel_id = CHANNELS.get(channel_key)
        if not channel_id or channel_id == 0:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

   
        is_empty = True
        async for _ in channel.history(limit=1):
            is_empty = False
            break

        if is_empty:
            embed = create_embed(title=title, description=description)
        
            if LOGO_URL:
                embed.set_thumbnail(url=LOGO_URL)
            
            view = ReglementView(url, btn_label)
            await channel.send(embed=embed, view=view)
            print(f"[REGLEMENT] Embed envoyé dans {channel.name}")

    @commands.Cog.listener()
    async def on_ready(self):

        await self.check_and_send_reglement(
            "reglement_gen",
            "Règlement Général",
            "Voici le règlement du serveur RolePlay Remember Roleplay !\n\nMerci de le lire attentivement avant de commencer votre aventure.",
            "https://docs.google.com/document/d/13tt57aQiBR5LJWAjs2MVXosruvxiZz68RI15v50cA1c/edit?usp=sharing",
            "Lire le Règlement"
        )


        await self.check_and_send_reglement(
            "reglement_discord",
            "Règlement Discord",
            "Voici le règlement Discord.\n\nLe respect de ces règles est obligatoire pour la bonne entente sur le serveur.",
            "https://docs.google.com/document/d/1WbnBq10SzKyZAD7euV154EF-8FVKuEyQfTsA112KIi4/edit?usp=sharing",
            "Lire le Règlement Discord"
        )

async def setup(bot):
    await bot.add_cog(ReglementCog(bot))
