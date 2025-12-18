import discord
import io
import datetime
import aiohttp
from discord.ext import commands
from discord import app_commands

import sys
sys.path.append("..")
from config import EMBED_COLOR, LOGO_URL, CHANNELS, ROLES, create_embed, GUILD_ID



DEFAULT_REPRISE_PROJECTS = [
    {"name": "Fermier", "priority": False},
    {"name": "Agent Immobilier", "priority": False},
    {"name": "LSPD", "priority": False},
    {"name": "Ballas", "priority": False},
    {"name": "Vagos", "priority": True},
    {"name": "Families", "priority": True},
]


def get_next_rdv_timestamp(day_name: str, hour_str: str) -> int:
    """
    Calcule le timestamp UNIX du prochain créneau disponible.
    Ex: Si on est Mardi et qu'on demande Lundi, ça donne le Lundi de la semaine prochaine.
    """
    days_map = {
        "Lundi": 0, "Mardi": 1, "Mercredi": 2, "Jeudi": 3,
        "Vendredi": 4, "Samedi": 5, "Dimanche": 6
    }
    
    target_day_idx = days_map.get(day_name)
    if target_day_idx is None:
        return 0
        
    try:
        
        hour = int(hour_str.replace('h', '').replace(':', ''))
        if hour > 100: 
            hour = hour // 100
    except:
        hour = 18 
        
    now = datetime.datetime.now()
    current_day_idx = now.weekday()
    

    days_ahead = target_day_idx - current_day_idx
    

    if days_ahead < 0 or (days_ahead == 0 and now.hour >= hour):
        days_ahead += 7
        
    next_date = now + datetime.timedelta(days=days_ahead)
    

    final_date = next_date.replace(hour=hour, minute=0, second=0, microsecond=0)
    
    return int(final_date.timestamp())


def get_day_options() -> list[discord.SelectOption]:
    """
    Génère les options de jours avec les dates complètes.
    Ex: "Lundi 23 décembre", "Mardi 24 décembre", etc.
    """
    days_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    months_names = ["janvier", "février", "mars", "avril", "mai", "juin", 
                    "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    
    options = []
    now = datetime.datetime.now()
    current_day_idx = now.weekday()
    
    for i, day_name in enumerate(days_names):

        days_ahead = i - current_day_idx
        if days_ahead <= 0: 
            days_ahead += 7
            
        target_date = now + datetime.timedelta(days=days_ahead)
        
   
        date_str = f"{day_name} {target_date.day} {months_names[target_date.month - 1]}"
        
        options.append(discord.SelectOption(
            label=date_str,
            value=day_name  
        ))
    
    return options


def format_date_french(day_name: str, hour_str: str) -> str:
    """
    Formate une date complète en français à partir du jour et de l'heure.
    Ex: "Lundi 23 décembre à 18h00"
    """
    days_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    months_names = ["janvier", "février", "mars", "avril", "mai", "juin", 
                    "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    
    ts = get_next_rdv_timestamp(day_name, hour_str)
    dt = datetime.datetime.fromtimestamp(ts)
    
    day_name_fr = days_names[dt.weekday()]
    month_name = months_names[dt.month - 1]
    
    return f"{day_name_fr} {dt.day} {month_name} à {hour_str}"


async def generate_transcript(channel: discord.TextChannel) -> io.StringIO:
    """Génère un fichier texte contenant l'historique du salon."""
    lines = [
        f"TRANSCRIPT - {channel.name}",
        f"Date : {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "-" * 50, ""
    ]
    
    async for msg in channel.history(limit=None, oldest_first=True):
        timestamp = msg.created_at.strftime('%d/%m %H:%M')
        content = msg.content
        if msg.attachments:
            content += f" [Fichier: {msg.attachments[0].url}]"
        lines.append(f"[{timestamp}] {msg.author.name}: {content}")
    
    return io.StringIO("\n".join(lines))


async def create_reprise_ticket(interaction: discord.Interaction, project_name: str, is_priority: bool, motivation: str, details: str, doc: str = None):
    """Crée le salon de ticket pour une reprise de projet."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    user = interaction.user

    category = guild.get_channel(CHANNELS["tickets_category"])
    staff_role = guild.get_role(ROLES["support"])

    if not category or not staff_role:
        return await interaction.followup.send(
            "Erreur de configuration (catégorie ou rôle introuvable). Contactez un administrateur.",
            ephemeral=True
        )


    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
        staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
    }

    channel_name = f"reprise-{user.name.lower()[:20]}"

    try:
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Propriétaire: {user.id} | Type: reprise"
        )
    except Exception as e:
        return await interaction.followup.send(f"Erreur à la création du salon : {e}", ephemeral=True)

    priority_tag = " ⚡ PRIORITAIRE" if is_priority else ""
    
    embed = create_embed(
        title=f"Reprise de projet{priority_tag}",
        description=f"Ticket ouvert par {user.mention}\nUn membre du staff va prendre en charge votre demande."
    )
    
    embed.add_field(name="Projet à reprendre", value=project_name, inline=False)
    embed.add_field(name="Pourquoi cette reprise ?", value=motivation, inline=False)
    embed.add_field(name="Détails du projet", value=details, inline=False)
    if doc:
        embed.add_field(name="Document présentation", value=doc, inline=False)

    content = f"{staff_role.mention}"

    await channel.send(
        content=content,
        embed=embed,
        view=TicketManagementView()
    )

    await interaction.followup.send(f"Ticket créé : {channel.mention}", ephemeral=True)


async def update_planning_embed(bot):
    """Met à jour l'embed du planning des rendez-vous - Style PRO et organisé."""
    if not bot.pool:
        return

    channel = bot.get_channel(CHANNELS["rdv_planning"])
    if not channel:
        return

    current_ts = int(datetime.datetime.now().timestamp())
    

    days_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", 
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    async with bot.pool.acquire() as conn:

        await conn.execute("DELETE FROM rdv_planning WHERE rdv_timestamp < $1", current_ts - 7200)


        rows = await conn.fetch("""
            SELECT * FROM rdv_planning 
            WHERE rdv_timestamp > $1 
            ORDER BY rdv_timestamp ASC 
            LIMIT 15
        """, current_ts - 3600)
        
        config = await conn.fetchrow("SELECT message_id FROM persistent_messages WHERE key = 'rdv_planning'")
        message_id = config["message_id"] if config else None

    
    embed = discord.Embed(color=EMBED_COLOR)
    embed.set_author(name="PLANNING DES ENTRETIENS", icon_url=LOGO_URL)
    
    if not rows:
        embed.description = (
            "```\n"
            "      Aucun rendez-vous programmé\n"
            "```"
        )
    else:
        
        rdv_by_day = {}
        for row in rows:
            ts = row['rdv_timestamp']
            day_key = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            if day_key not in rdv_by_day:
                rdv_by_day[day_key] = []
            rdv_by_day[day_key].append(row)
        
        description_lines = []
        
        for day_key in sorted(rdv_by_day.keys()):
            day_rows = rdv_by_day[day_key]
            first_ts = day_rows[0]['rdv_timestamp']
            
            
            dt = datetime.datetime.fromtimestamp(first_ts)
            day_name = days_fr[dt.weekday()]
            month_name = months_fr[dt.month - 1]
            date_formatted = f"{day_name} {dt.day} {month_name}"
            
            
            description_lines.append(f"▸ **{date_formatted}**")
            
            for row in day_rows:
                user = bot.get_user(row['user_id'])
                staff = bot.get_user(row['staff_id'])
                ts = row['rdv_timestamp']
                
                user_name = user.display_name if user else "Inconnu"
                staff_name = staff.display_name if staff else "Staff"
                
                
                hour_dt = datetime.datetime.fromtimestamp(ts)
                hour_str = f"{hour_dt.hour:02d}h{hour_dt.minute:02d}"
                
                
                description_lines.append(
                    f"　`{hour_str}`  {user_name}  ›  {staff_name}"
                )
            
            description_lines.append("")
        
        embed.description = "\n".join(description_lines)
    
    embed.set_footer(text=f"Mis à jour • {len(rows)} entretien(s)")


    view = PlanningManagementView(bot) if rows else None

    try:
        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed, view=view)
                return
            except discord.NotFound:
                pass
        
        msg = await channel.send(embed=embed, view=view)
        async with bot.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO persistent_messages (key, message_id, channel_id) 
                VALUES ('rdv_planning', $1, $2)
                ON CONFLICT (key) DO UPDATE SET message_id = $1
            """, msg.id, channel.id)
            
    except Exception as e:
        print(f"Erreur update planning: {e}")



class PlanningManagementView(discord.ui.View):
    """Vue avec bouton pour annuler un RDV depuis le planning."""
    
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Annuler un RDV", style=discord.ButtonStyle.danger, custom_id="planning_cancel_rdv")
    async def cancel_rdv(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        staff_role = interaction.guild.get_role(ROLES["support"])
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("❌ Réservé au staff.", ephemeral=True)
        
        
        if not self.bot.pool:
            return await interaction.response.send_message("❌ BDD indisponible.", ephemeral=True)
        
        current_ts = int(datetime.datetime.now().timestamp())
        
        async with self.bot.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM rdv_planning 
                WHERE rdv_timestamp > $1 
                ORDER BY rdv_timestamp ASC 
                LIMIT 25
            """, current_ts - 3600)
        
        if not rows:
            return await interaction.response.send_message("❌ Aucun RDV à annuler.", ephemeral=True)
        
   
        options = []
        days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        months_fr = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]
        
        for row in rows:
            user = self.bot.get_user(row['user_id'])
            ts = row['rdv_timestamp']
            dt = datetime.datetime.fromtimestamp(ts)
            
            user_name = user.display_name if user else "Inconnu"
            day_name = days_fr[dt.weekday()]
            month_name = months_fr[dt.month - 1]
            hour_str = f"{dt.hour:02d}h{dt.minute:02d}"
            
            label = f"{day_name} {dt.day} {month_name} {hour_str} - {user_name}"
            
            options.append(discord.SelectOption(
                label=label[:100], 
                value=str(row['id'])
            ))
        
        await interaction.response.send_message(
            "**Sélectionnez le RDV à annuler :**",
            view=CancelRDVSelectView(self.bot, options),
            ephemeral=True
        )


class CancelRDVSelectView(discord.ui.View):
    """Vue pour sélectionner et annuler un RDV."""
    
    def __init__(self, bot, options: list):
        super().__init__(timeout=60)
        self.bot = bot
        
        select = discord.ui.Select(
            placeholder="Choisir le RDV à annuler",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        rdv_id = int(interaction.data["values"][0])
        
        if not self.bot.pool:
            return await interaction.response.send_message("❌ Erreur BDD.", ephemeral=True)
        
        async with self.bot.pool.acquire() as conn:
            
            row = await conn.fetchrow("SELECT * FROM rdv_planning WHERE id = $1", rdv_id)
            
            if not row:
                return await interaction.response.send_message("❌ RDV introuvable.", ephemeral=True)
            
 
            await conn.execute("DELETE FROM rdv_planning WHERE id = $1", rdv_id)
        

        await update_planning_embed(self.bot)
        
  
        ticket_channel = self.bot.get_channel(row['channel_id'])
        if ticket_channel:
            user = self.bot.get_user(row['user_id'])
            
            cancel_embed = discord.Embed(color=0xE74C3C)
            cancel_embed.set_author(name="Rendez-vous annulé", icon_url=LOGO_URL)
            
            ts = row['rdv_timestamp']
            dt = datetime.datetime.fromtimestamp(ts)
            days_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", 
                         "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
            date_str = f"{days_fr[dt.weekday()]} {dt.day} {months_fr[dt.month - 1]} à {dt.hour:02d}h{dt.minute:02d}"
            
            cancel_embed.description = (
                f"Le RDV du **{date_str}** a été annulé par {interaction.user.mention}."
            )
            
            try:
                await ticket_channel.send(
                    content=user.mention if user else None,
                    embed=cancel_embed
                )
            except:
                pass
        
        await interaction.response.edit_message(
            content="✅ **RDV annulé avec succès.**",
            view=None
        )
        self.stop()


class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_type: str):
        titles = {
            "plainte": "Déposer une plainte",
            "projet": "Créer un projet",
            "autre": "Autre demande"
        }
        super().__init__(title=titles.get(ticket_type, "Nouveau Ticket"))
        self.ticket_type = ticket_type

        if ticket_type == "plainte":
            self.add_item(discord.ui.TextInput(
                label="Contre qui ? (Nom/ID)",
                placeholder="Ex: Jean Dupont - ID 12345",
                required=True
            ))
            self.add_item(discord.ui.TextInput(
                label="Détail de la plainte",
                style=discord.TextStyle.long,
                placeholder="Décrivez les faits en détail",
                required=True
            ))

        elif ticket_type == "projet":
            self.add_item(discord.ui.TextInput(
                label="Nom du projet",
                placeholder="Nom de votre projet",
                required=True
            ))
            self.add_item(discord.ui.TextInput(
                label="Nombre de joueurs",
                placeholder="Combien de joueurs ?",
                required=True
            ))
            self.add_item(discord.ui.TextInput(
                label="Détails rapides",
                style=discord.TextStyle.long,
                placeholder="Décrivez brièvement votre projet",
                required=True
            ))
            self.add_item(discord.ui.TextInput(
                label="Document présentation",
                placeholder="Lien vers un GDoc ou PDF (Optionnel)",
                required=False
            ))

        elif ticket_type == "autre":
            self.add_item(discord.ui.TextInput(
                label="Votre demande",
                style=discord.TextStyle.long,
                placeholder="Décrivez votre demande en détail",
                required=True
            ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        category = guild.get_channel(CHANNELS["tickets_category"])
        staff_role = guild.get_role(ROLES["support"])

        if not category or not staff_role:
            return await interaction.followup.send("Erreur de configuration.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
        }

        try:
            channel = await guild.create_text_channel(
                name=f"{self.ticket_type}-{user.name.lower()[:20]}",
                category=category,
                overwrites=overwrites,
                topic=f"Propriétaire: {user.id}"
            )
        except Exception as e:
            return await interaction.followup.send(f"Erreur : {e}", ephemeral=True)

        embed = create_embed(
            title=self.title,
            description=f"Ticket ouvert par {user.mention}\nUn membre du staff va prendre en charge votre demande."
        )
        
        for child in self.children:
            val = child.value if child.value else "Non spécifié"
            embed.add_field(name=child.label, value=val, inline=False)
        
        info_msg = ""
        if self.ticket_type == "plainte":
            info_msg = "\n\n📎 **Merci de fournir tous les screens, vidéos et preuves complémentaires.**"

        await channel.send(
            content=f"{staff_role.mention}{info_msg}",
            embed=embed,
            view=TicketManagementView()
        )
        await interaction.followup.send(f"Ticket créé : {channel.mention}", ephemeral=True)




async def check_slot_available(bot, timestamp: int) -> bool:
    """Vérifie si un créneau est disponible (pas déjà pris)."""
    if not bot.pool:
        return True
    
    async with bot.pool.acquire() as conn:

        existing = await conn.fetchval("""
            SELECT COUNT(*) FROM rdv_planning 
            WHERE ABS(rdv_timestamp - $1) < 1800
        """, timestamp)
        return existing == 0


async def finalize_rdv(bot, channel, user, staff_member, day: str, hour: str, ts: int, messages_to_delete: list = None):
    """Finalise et enregistre le RDV après confirmation du staff."""

    if messages_to_delete:
        for msg in messages_to_delete:
            try:
                await msg.delete()
            except:
                pass
    

    if bot.pool:
        async with bot.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO rdv_planning (user_id, staff_id, day, hour, rdv_timestamp, channel_id)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, user.id, staff_member.id, day, hour, ts, channel.id)

    await update_planning_embed(bot)
    

    date_formatted = format_date_french(day, hour)

    embed_confirm = discord.Embed(
        color=0x2ECC71  
    )
    embed_confirm.set_author(name="Rendez-vous confirmé", icon_url=LOGO_URL)
    embed_confirm.description = (
        f"**{date_formatted}**\n\n"
        f"👤 {user.mention}\n"
        f"🛡️ {staff_member.mention}"
    )
    await channel.send(embed=embed_confirm)


    guild = channel.guild
    owner = guild.owner
    if owner:
        try:
            owner_embed = discord.Embed(color=EMBED_COLOR)
            owner_embed.set_author(name="Nouveau RDV programmé", icon_url=LOGO_URL)
            owner_embed.description = (
                f"**{date_formatted}**\n\n"
                f"👤 **Client:** {user.name}\n"
                f"🛡️ **Staff:** {staff_member.name}\n"
                f"📍 **Salon:** {channel.name}"
            )
            await owner.send(embed=owner_embed)
        except:
            pass


class StaffRDVConfirmView(discord.ui.View):
    """Vue envoyée en MP au staff pour confirmer ou refuser un RDV."""
    
    def __init__(self, bot, user, channel, day: str, hour: str, ts: int, wait_message=None):
        super().__init__(timeout=3600)  
        self.bot = bot
        self.user = user
        self.channel = channel
        self.day = day
        self.hour = hour
        self.ts = ts
        self.wait_message = wait_message  
        self.staff_member = None

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success)
    async def accept_rdv(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.staff_member = interaction.user
        
    
        if not await check_slot_available(self.bot, self.ts):
            return await interaction.response.send_message(
                "❌ Ce créneau a été pris entre temps. Veuillez proposer un autre horaire.",
                ephemeral=True
            )
        
     
        messages_to_delete = [self.wait_message] if self.wait_message else []
        

        await finalize_rdv(self.bot, self.channel, self.user, self.staff_member, self.day, self.hour, self.ts, messages_to_delete)
        
 
        date_formatted = format_date_french(self.day, self.hour)
        
  
        for child in self.children:
            child.disabled = True
        
        confirm_embed = discord.Embed(color=0x2ECC71)
        confirm_embed.set_author(name="RDV Accepté", icon_url=LOGO_URL)
        confirm_embed.description = (
            f"**{self.user.name}**\n"
            f"{date_formatted}"
        )
        await interaction.response.edit_message(embed=confirm_embed, view=self)
        self.stop()

    @discord.ui.button(label="Contre-proposer", style=discord.ButtonStyle.secondary)
    async def refuse_rdv(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.staff_member = interaction.user
        

        if self.wait_message:
            try:
                await self.wait_message.delete()
            except:
                pass
        

        for child in self.children:
            child.disabled = True
        
        refused_embed = discord.Embed(color=0xE74C3C)
        refused_embed.set_author(name="RDV Refusé", icon_url=LOGO_URL)
        refused_embed.description = "Choisissez un nouveau créneau ci-dessous."
        await interaction.response.edit_message(embed=refused_embed, view=self)
        
    
        counter_embed = discord.Embed(color=EMBED_COLOR)
        counter_embed.set_author(name="Contre-proposition", icon_url=LOGO_URL)
        counter_embed.description = "Sélectionnez un nouveau créneau à proposer."
        
        await interaction.followup.send(
            embed=counter_embed,
            view=StaffCounterProposalView(self.bot, self.user, self.channel, interaction.user)
        )
        self.stop()



class StaffCounterProposalView(discord.ui.View):
    """Vue pour que le staff fasse une contre-proposition."""
    
    def __init__(self, bot, user, channel, staff_member):
        super().__init__(timeout=1800)  
        self.bot = bot
        self.user = user
        self.channel = channel
        self.staff_member = staff_member
        self.selected_day = None
        self.selected_hour = None
        

        day_select = discord.ui.Select(
            placeholder="Jour",
            options=get_day_options()
        )
        day_select.callback = self.select_day_callback
        self.add_item(day_select)
        
   
        hour_select = discord.ui.Select(
            placeholder="Heure",
            options=[
                discord.SelectOption(label="17h00", value="17h00"),
                discord.SelectOption(label="18h00", value="18h00"),
                discord.SelectOption(label="19h00", value="19h00"),
                discord.SelectOption(label="20h00", value="20h00"),
                discord.SelectOption(label="21h00", value="21h00"),
                discord.SelectOption(label="22h00", value="22h00"),
            ]
        )
        hour_select.callback = self.select_hour_callback
        self.add_item(hour_select)
    
    async def select_day_callback(self, interaction: discord.Interaction):
        self.selected_day = interaction.data["values"][0]
        await interaction.response.defer()
    
    async def select_hour_callback(self, interaction: discord.Interaction):
        self.selected_hour = interaction.data["values"][0]
        await interaction.response.defer()

    @discord.ui.button(label="Envoyer", style=discord.ButtonStyle.primary, row=2)
    async def send_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_day or not self.selected_hour:
            return await interaction.response.send_message("❌ Sélectionnez un jour ET une heure.", ephemeral=True)
        
        ts = get_next_rdv_timestamp(self.selected_day, self.selected_hour)
        

        if not await check_slot_available(self.bot, ts):
            return await interaction.response.send_message("❌ Ce créneau est déjà pris.", ephemeral=True)
        

        date_formatted = format_date_french(self.selected_day, self.selected_hour)
        

        for child in self.children:
            child.disabled = True
        
        sent_embed = discord.Embed(color=0x2ECC71)
        sent_embed.set_author(name="Proposition envoyée", icon_url=LOGO_URL)
        sent_embed.description = f"{date_formatted}"
        await interaction.response.edit_message(embed=sent_embed, view=self)
        
     
        embed = discord.Embed(color=EMBED_COLOR)
        embed.set_author(name="Nouvelle proposition", icon_url=LOGO_URL)
        embed.description = (
            f"{self.staff_member.mention} propose :\n\n"
            f"**{date_formatted}**"
        )
        
        counter_msg = await self.channel.send(
            content=self.user.mention,
            embed=embed,
            view=UserRDVResponseView(self.bot, self.user, self.channel, self.staff_member, self.selected_day, self.selected_hour, ts)
        )
        self.stop()



class UserRDVResponseView(discord.ui.View):
    """Vue pour que le client réponde à une contre-proposition."""
    
    def __init__(self, bot, user, channel, staff_member, day: str, hour: str, ts: int):
        super().__init__(timeout=None)  
        self.bot = bot
        self.user = user
        self.channel = channel
        self.staff_member = staff_member
        self.day = day
        self.hour = hour
        self.ts = ts

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, custom_id="user_rdv_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Seul le demandeur peut répondre.", ephemeral=True)
        

        if not await check_slot_available(self.bot, self.ts):
            return await interaction.response.send_message("❌ Ce créneau a été pris entre temps.", ephemeral=True)
        

        messages_to_delete = []
        try:
            messages_to_delete.append(interaction.message)
        except:
            pass
        
        await interaction.response.defer()
        

        await finalize_rdv(self.bot, self.channel, self.user, self.staff_member, self.day, self.hour, self.ts, messages_to_delete)
        self.stop()

    @discord.ui.button(label="Autre créneau", style=discord.ButtonStyle.secondary, custom_id="user_rdv_counter")
    async def counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Seul le demandeur peut répondre.", ephemeral=True)
        
 
        try:
            await interaction.message.delete()
        except:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
        

        embed = discord.Embed(color=EMBED_COLOR)
        embed.set_author(name="Choisissez un créneau", icon_url=LOGO_URL)
        embed.description = "Sélectionnez vos disponibilités :"
        
        await interaction.channel.send(
            embed=embed,
            view=RDVSelectorView(self.bot, self.staff_member, proposal_message=None)
        )
        self.stop()


class RDVSelectorView(discord.ui.View):
    """Vue permettant au membre de choisir son créneau."""
    
    def __init__(self, bot, staff_member, proposal_message=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.staff_member = staff_member
        self.proposal_message = proposal_message
        self.selected_day = None
        self.selected_hour = None
        
  
        day_select = discord.ui.Select(
            placeholder="Jour",
            options=get_day_options(),
            custom_id="rdv_day_select"
        )
        day_select.callback = self.select_day_callback
        self.add_item(day_select)
        

        hour_select = discord.ui.Select(
            placeholder="Heure",
            options=[
                discord.SelectOption(label="17h00", value="17h00"),
                discord.SelectOption(label="18h00", value="18h00"),
                discord.SelectOption(label="19h00", value="19h00"),
                discord.SelectOption(label="20h00", value="20h00"),
                discord.SelectOption(label="21h00", value="21h00"),
                discord.SelectOption(label="22h00", value="22h00"),
            ],
            custom_id="rdv_hour_select"
        )
        hour_select.callback = self.select_hour_callback
        self.add_item(hour_select)
    
    async def select_day_callback(self, interaction: discord.Interaction):
        self.selected_day = interaction.data["values"][0]
        await interaction.response.defer()
    
    async def select_hour_callback(self, interaction: discord.Interaction):
        self.selected_hour = interaction.data["values"][0]
        await interaction.response.defer()

    @discord.ui.button(label="Valider", style=discord.ButtonStyle.success, custom_id="rdv_confirm", row=2)
    async def confirm_rdv(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_day or not self.selected_hour:
            return await interaction.response.send_message("❌ Sélectionnez un jour ET une heure.", ephemeral=True)

        ts = get_next_rdv_timestamp(self.selected_day, self.selected_hour)


        if not await check_slot_available(self.bot, ts):
            date_formatted = format_date_french(self.selected_day, self.selected_hour)
            return await interaction.response.send_message(
                f"❌ **Créneau indisponible**\n{date_formatted} est déjà pris.",
                ephemeral=True
            )

 
        if self.proposal_message:
            try:
                await self.proposal_message.delete()
            except:
                pass


        try:
            await interaction.message.delete()
        except:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
            return

        await interaction.response.defer()


        date_formatted = format_date_french(self.selected_day, self.selected_hour)


        wait_embed = discord.Embed(color=EMBED_COLOR)
        wait_embed.set_author(name="En attente de confirmation", icon_url=LOGO_URL)
        wait_embed.description = (
            f"**{date_formatted}**\n\n"
            f"⏳ {self.staff_member.mention} doit confirmer..."
        )
        wait_message = await interaction.channel.send(embed=wait_embed)


        try:
            staff_embed = discord.Embed(color=EMBED_COLOR)
            staff_embed.set_author(name="Demande de RDV", icon_url=LOGO_URL)
            staff_embed.description = (
                f"**{interaction.user.name}** demande un entretien\n\n"
                f"📆  **{date_formatted}**\n\n"
                f"📍  `{interaction.channel.name}`"
            )
            staff_embed.set_footer(text="Remember RolePlay")
            
            await self.staff_member.send(
                embed=staff_embed,
                view=StaffRDVConfirmView(self.bot, interaction.user, interaction.channel, self.selected_day, self.selected_hour, ts, wait_message)
            )
        except discord.Forbidden:

            await finalize_rdv(self.bot, interaction.channel, interaction.user, self.staff_member, self.selected_day, self.selected_hour, ts, [wait_message])


class AddMemberView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Sélectionnez un membre à ajouter",
        min_values=1,
        max_values=1
    )
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        member = select.values[0]
        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
        await interaction.response.defer()
        

        embed = discord.Embed(
            description=f"✅ {member.mention} a été ajouté au ticket.",
            color=EMBED_COLOR
        )
        await interaction.channel.send(embed=embed)
        self.stop()




class TicketManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    def _check_perm(self, interaction):
        role = interaction.guild.get_role(ROLES["support"])
        return role in interaction.user.roles if role else False

    @discord.ui.button(label="Prendre en charge", style=discord.ButtonStyle.secondary, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction):
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text or ""
        
        if "Géré par" in footer_text:
            return await interaction.response.send_message("Ticket déjà pris en charge.", ephemeral=True)
        
        embed.set_footer(text=f"Géré par {interaction.user.display_name}")
        await interaction.response.defer()
        await interaction.message.edit(embed=embed)
        

        claim_embed = discord.Embed(
            description=f"🛡️ **{interaction.user.display_name}** a pris en charge le ticket.",
            color=EMBED_COLOR
        )
        await interaction.channel.send(embed=claim_embed)

    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction):
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        
        await interaction.response.send_message(
            "Confirmer fermeture ?",
            view=CloseConfirmView(),
            ephemeral=True
        )

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.primary, custom_id="ticket_add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction):
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        
        await interaction.response.send_message(
            "Qui souhaitez-vous ajouter ?",
            view=AddMemberView(),
            ephemeral=True
        )

    @discord.ui.button(label="RDV", style=discord.ButtonStyle.secondary, custom_id="ticket_rdv")
    async def rdv_proposal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction):
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        

        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(color=EMBED_COLOR)
        embed.set_author(name="Proposition d'entretien", icon_url=LOGO_URL)
        embed.description = (
            f"{interaction.user.mention} vous propose un rendez-vous vocal.\n\n"
            f"Sélectionnez vos disponibilités ci-dessous."
        )
        
        proposal_msg = await interaction.channel.send(embed=embed)
        

        selector_view = RDVSelectorView(interaction.client, interaction.user, proposal_message=proposal_msg)
        selector_msg = await interaction.channel.send(view=selector_view)


class CloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Avec transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_close_transcript")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._close(interaction, True)

    @discord.ui.button(label="Sans transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_close_direct")
    async def no_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._close(interaction, False)
    
    async def _close(self, interaction, transcript):
        await interaction.response.edit_message(content="Fermeture...", view=None)
        
        file = None
        if transcript:
            f = await generate_transcript(interaction.channel)
            file = discord.File(f, filename=f"{interaction.channel.name}.txt")
        
        log_channel = interaction.guild.get_channel(CHANNELS["tickets_logs"])
        if log_channel:
            log_embed = discord.Embed(
                title="Ticket fermé",
                description=f"Salon: {interaction.channel.name}\nPar: {interaction.user.mention}",
                color=EMBED_COLOR,
                timestamp=datetime.datetime.now()
            )
            await log_channel.send(embed=log_embed, file=file if transcript else None)
        
        await interaction.channel.delete()



class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Sélectionnez une catégorie",
        custom_id="ticket_panel_select",
        options=[
            discord.SelectOption(label="Plainte", value="plainte", emoji="⚠️"),
            discord.SelectOption(label="Nouveau projet", value="projet", emoji="🆕"),
            discord.SelectOption(label="Reprise de projet", value="reprise", emoji="🔄"),
            discord.SelectOption(label="Autre demande", value="autre", emoji="📝")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        ticket_type = select.values[0]
        
        if ticket_type == "reprise":
            cog = interaction.client.get_cog("TicketsCog")
            projects = await cog.get_reprise_projects() if cog else DEFAULT_REPRISE_PROJECTS
            
            if not projects:
                return await interaction.response.send_message("Aucun projet disponible à la reprise.", ephemeral=True)
            

            await interaction.response.send_message(
                "**Sélectionnez le projet que vous souhaitez reprendre :**",
                view=RepriseSelectFallback(projects),
                ephemeral=True
            )
        else:
            await interaction.response.send_modal(TicketModal(ticket_type))


class RepriseModalFallback(discord.ui.Modal):
    """Modal de reprise qui s'ouvre APRÈS avoir choisi le projet dans le menu."""
    def __init__(self, project_name: str, is_priority: bool):
        super().__init__(title="Reprise de projet")
        self.project_name = project_name
        self.is_priority = is_priority

        self.add_item(discord.ui.TextInput(
            label="Pourquoi cette reprise ?",
            style=discord.TextStyle.long,
            placeholder="Expliquez vos motivations",
            required=True
        ))
        self.add_item(discord.ui.TextInput(
            label="Détails du projet",
            style=discord.TextStyle.long,
            placeholder="Décrivez vos plans",
            required=True
        ))
        self.add_item(discord.ui.TextInput(
            label="Document présentation",
            placeholder="Lien GDoc/PDF (Optionnel)",
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await create_reprise_ticket(
            interaction,
            self.project_name,
            self.is_priority,
            self.children[0].value,
            self.children[1].value,
            self.children[2].value
        )

class RepriseSelectFallback(discord.ui.View):
    """Menu déroulant initial pour choisir le projet."""
    def __init__(self, projects: list):
        super().__init__(timeout=120)
        self.projects = projects
        
        options = []
        for project in projects:
            label = project["name"]
            if project["priority"]: label += " ⚡"
            options.append(discord.SelectOption(label=label, value=project["name"]))
        
        select = discord.ui.Select(
            placeholder="Choisissez le projet",
            options=options,
            custom_id="reprise_fallback_select"
        )
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]

        project = next((p for p in self.projects if p["name"] == selected), None)
        if project:
            await interaction.response.send_modal(RepriseModalFallback(project["name"], project["priority"]))


class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):

        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketManagementView())
        self.bot.add_view(CloseConfirmView())
        self.bot.add_view(PlanningManagementView(self.bot))
        

        if self.bot.pool:
            async with self.bot.pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM reprise_projects")
                if count == 0:
                    for project in DEFAULT_REPRISE_PROJECTS:
                        await conn.execute(
                            "INSERT INTO reprise_projects (name, priority) VALUES ($1, $2)",
                            project["name"], project["priority"]
                        )
        

        await update_planning_embed(self.bot)

    async def get_reprise_projects(self) -> list:
        if not self.bot.pool:
            return DEFAULT_REPRISE_PROJECTS
        
        async with self.bot.pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, priority FROM reprise_projects ORDER BY priority DESC, name ASC")
            return [{"name": row["name"], "priority": row["priority"]} for row in rows]



    @app_commands.command(name="setup_tickets", description="Installe le panneau de tickets")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        embed = create_embed(
            title="Support",
            description="Utilisez le menu ci-dessous pour ouvrir un ticket."
        )
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message("✅ Panneau installé.", ephemeral=True)

    @app_commands.command(name="reprise_add", description="Ajouter un projet à la liste")
    @app_commands.checks.has_permissions(administrator=True)
    async def reprise_add(self, interaction: discord.Interaction, nom: str, prioritaire: bool = False):
        if not self.bot.pool:
            return await interaction.response.send_message("❌ BDD indisponible.", ephemeral=True)
        
        async with self.bot.pool.acquire() as conn:
            try:
                await conn.execute("INSERT INTO reprise_projects (name, priority) VALUES ($1, $2)", nom, prioritaire)
                tag = "⚡" if prioritaire else ""
                await interaction.response.send_message(f"✅ Projet **{nom}** {tag} ajouté.", ephemeral=True)
            except:
                await interaction.response.send_message(f"❌ Erreur : Le projet **{nom}** existe probablement déjà.", ephemeral=True)

    @app_commands.command(name="reprise_remove", description="Retirer un projet de la liste")
    @app_commands.checks.has_permissions(administrator=True)
    async def reprise_remove(self, interaction: discord.Interaction, nom: str):
        if not self.bot.pool:
            return await interaction.response.send_message("❌ BDD indisponible.", ephemeral=True)
        
        async with self.bot.pool.acquire() as conn:
            res = await conn.execute("DELETE FROM reprise_projects WHERE LOWER(name) = LOWER($1)", nom)
            if res == "DELETE 1":
                await interaction.response.send_message(f"✅ Projet **{nom}** retiré.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Projet **{nom}** introuvable.", ephemeral=True)

    @app_commands.command(name="clear_rdv", description="Supprimer tous les rendez-vous du planning")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_rdv(self, interaction: discord.Interaction):
        if not self.bot.pool:
            return await interaction.response.send_message("❌ BDD indisponible.", ephemeral=True)
        
        async with self.bot.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM rdv_planning")

            count = int(result.split(" ")[1]) if result else 0
        

        await update_planning_embed(self.bot)
        
        await interaction.response.send_message(f"✅ **{count}** rendez-vous supprimé(s) du planning.", ephemeral=True)

    @app_commands.command(name="sync_commands", description="Nettoyer et resynchroniser les commandes")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_commands(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:

            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync()  
            

            extensions = list(self.bot.extensions.keys())
            for ext in extensions:
                await self.bot.reload_extension(ext)
            

            guild = interaction.guild
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            
            await interaction.followup.send(
                f"✅ **Commandes nettoyées !**\n"
                f"• Commandes globales supprimées\n"
                f"• **{len(synced)}** commandes actives sur ce serveur",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
