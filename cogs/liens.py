import discord
from discord.ext import commands
from discord import app_commands
import sys
sys.path.append("..")
from config import EMBED_COLOR, LOGO_URL, CHANNELS, create_embed

class LiensCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def update_links_embed(self):
        """Met à jour ou crée l'embed des liens utiles."""
        channel_id = CHANNELS.get("liens_utiles")
        if not channel_id or channel_id == 0:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

     
        if not self.bot.pool:
            return
        
        async with self.bot.pool.acquire() as conn:
            links = await conn.fetch("SELECT label, url FROM useful_links ORDER BY label ASC")
            config = await conn.fetchrow("SELECT message_id FROM persistent_messages WHERE key = 'links_embed'")
            message_id = config["message_id"] if config else None


        embed = discord.Embed(color=EMBED_COLOR)
        if LOGO_URL:
            embed.set_author(name="LIENS UTILES", icon_url=LOGO_URL)
            embed.set_thumbnail(url=LOGO_URL)
        else:
            embed.set_author(name="LIENS UTILES")

        if not links:
            embed.description = "Aucun lien configuré pour le moment."
        else:
         
            description_lines = []
            for link in links:
          
                description_lines.append(f"🔗 **[{link['label']}]({link['url']})**")
            
            embed.description = "\n\n".join(description_lines)
            embed.set_footer(text="Remember RolePlay • Liens Officiels")

        try:
            if message_id:
                try:
                    msg = await channel.fetch_message(message_id)
                    await msg.edit(embed=embed)
                    return
                except discord.NotFound:
                    pass 


            is_empty = True
            async for _ in channel.history(limit=1):
                is_empty = False
                break
            
            if is_empty:
                msg = await channel.send(embed=embed)
                async with self.bot.pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO persistent_messages (key, message_id, channel_id) 
                        VALUES ('links_embed', $1, $2)
                        ON CONFLICT (key) DO UPDATE SET message_id = $1, channel_id = $2
                    """, msg.id, channel.id)
            else:
                print("[LIENS] Salon non vide et pas de message enregistré, envoi annulé.")

        except Exception as e:
            print(f"[LIENS] Erreur update: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_links_embed()

    @app_commands.command(name="addlien", description="Ajouter un lien utile (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_lien(self, interaction: discord.Interaction, nom: str, url: str):
        if not self.bot.pool:
            return await interaction.response.send_message("❌ Erreur BDD.", ephemeral=True)

        if not url.startswith("http"):
            return await interaction.response.send_message("❌ L'URL doit commencer par http:// ou https://", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        async with self.bot.pool.acquire() as conn:
    
            await conn.execute("""
                INSERT INTO useful_links (label, url) VALUES ($1, $2)
                ON CONFLICT (label) DO UPDATE SET url = $2
            """, nom, url)

        await self.update_links_embed()
        await interaction.followup.send(f"✅ Lien **{nom}** ajouté/mis à jour.")

    @app_commands.command(name="removelien", description="Supprimer un lien utile (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_lien(self, interaction: discord.Interaction, nom: str):
        if not self.bot.pool:
            return await interaction.response.send_message("❌ Erreur BDD.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        async with self.bot.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM useful_links WHERE label = $1", nom)
        
        if result == "DELETE 0":
            await interaction.followup.send(f"❌ Le lien **{nom}** n'existe pas.", ephemeral=True)
        else:
            await self.update_links_embed()
            await interaction.followup.send(f"✅ Lien **{nom}** supprimé.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(LiensCog(bot))
