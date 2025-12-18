import discord
import datetime
from discord.ext import commands
from discord import app_commands

import sys
sys.path.append("..")
from config import EMBED_COLOR, LOGO_URL, CHANNELS, ROLES, create_embed, GUILD_ID


def parse_date(date_str: str) -> datetime.date | None:
    """Parse une date au format JJ/MM/YYYY ou JJ/MM."""
    formats = ["%d/%m/%Y", "%d/%m"]
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(date_str.strip(), fmt)
            if fmt == "%d/%m":
                now = datetime.datetime.now()
                dt = dt.replace(year=now.year)
                if dt.date() < now.date():
                    dt = dt.replace(year=now.year + 1)
            return dt.date()
        except ValueError:
            continue
    return None


def format_date_french(dt: datetime.date) -> str:
    """Formate une date en français (ex: 23 décembre)."""
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{dt.day} {months_fr[dt.month - 1]}"


def format_date_full_french(dt: datetime.date) -> str:
    """Formate une date complète en français."""
    days_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{days_fr[dt.weekday()]} {dt.day} {months_fr[dt.month - 1]} {dt.year}"


async def update_absences_embed(bot):
    """Met à jour l'embed du tableau des absences."""
    print("[ABSENCES] Mise à jour de l'embed...")
    
    if not bot.pool:
        print("[ABSENCES] Erreur: pas de connexion BDD")
        return

    channel_id = CHANNELS.get("absences")
    if not channel_id:
        print("[ABSENCES] Erreur: channel ID non configuré")
        return
        
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"[ABSENCES] Erreur: channel {channel_id} introuvable")
        return

    today = datetime.date.today()
    today_str = today.isoformat()

    async with bot.pool.acquire() as conn:
       
        yesterday = (today - datetime.timedelta(days=1)).isoformat()
        await conn.execute("DELETE FROM staff_absences WHERE end_date < $1", yesterday)

      
        rows = await conn.fetch("""
            SELECT * FROM staff_absences 
            WHERE end_date >= $1 
            ORDER BY start_date ASC 
            LIMIT 20
        """, today_str)

        config = await conn.fetchrow("SELECT message_id FROM persistent_messages WHERE key = 'absences_panel'")
        message_id = config["message_id"] if config else None

    print(f"[ABSENCES] {len(rows)} absence(s) trouvée(s), message_id={message_id}")


    embed = discord.Embed(color=EMBED_COLOR)
    
   
    if LOGO_URL:
        embed.set_author(name="ABSENCES DU STAFF", icon_url=LOGO_URL)
    else:
        embed.set_author(name="ABSENCES DU STAFF")

    if not rows:
        embed.description = (
            "```\n"
            "      Aucune absence déclarée\n"
            "```"
        )
    else:
        absences_en_cours = []
        absences_a_venir = []

        for row in rows:
            start = datetime.date.fromisoformat(row['start_date'])
            end = datetime.date.fromisoformat(row['end_date'])

            if start <= today <= end:
                absences_en_cours.append(row)
            elif start > today:
                absences_a_venir.append(row)

        description_lines = []

        if absences_en_cours:
            description_lines.append("**🔴 En cours**")
            for row in absences_en_cours:
                user = bot.get_user(row['staff_id'])
                user_name = user.display_name if user else f"ID:{row['staff_id']}"
                start = datetime.date.fromisoformat(row['start_date'])
                end = datetime.date.fromisoformat(row['end_date'])
                reason = row['reason'] or "Non spécifiée"

                days_left = (end - today).days
                days_text = f"{days_left}j restant{'s' if days_left > 1 else ''}" if days_left > 0 else "Dernier jour"

                description_lines.append(
                    f"　**{user_name}**\n"
                    f"　　`{format_date_french(start)}` → `{format_date_french(end)}` ({days_text})\n"
                    f"　　_{reason}_"
                )
            description_lines.append("")

        if absences_a_venir:
            description_lines.append("**🟡 À venir**")
            for row in absences_a_venir:
                user = bot.get_user(row['staff_id'])
                user_name = user.display_name if user else f"ID:{row['staff_id']}"
                start = datetime.date.fromisoformat(row['start_date'])
                end = datetime.date.fromisoformat(row['end_date'])
                reason = row['reason'] or "Non spécifiée"

                days_until = (start - today).days
                days_text = f"dans {days_until}j" if days_until > 1 else "demain"

                description_lines.append(
                    f"　**{user_name}** ({days_text})\n"
                    f"　　`{format_date_french(start)}` → `{format_date_french(end)}`\n"
                    f"　　_{reason}_"
                )

        embed.description = "\n".join(description_lines)

    total_absent = len([r for r in rows if datetime.date.fromisoformat(r['start_date']) <= today <= datetime.date.fromisoformat(r['end_date'])])
    embed.set_footer(text=f"Mis à jour • {total_absent} absent{'s' if total_absent != 1 else ''} actuellement")

    view = AbsencesPanelView()

    try:
        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed, view=view)
                print("[ABSENCES] Embed mis à jour avec succès")
                return
            except discord.NotFound:
                print("[ABSENCES] Message introuvable, création d'un nouveau")

        msg = await channel.send(embed=embed, view=view)
        async with bot.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO persistent_messages (key, message_id, channel_id) 
                VALUES ('absences_panel', $1, $2)
                ON CONFLICT (key) DO UPDATE SET message_id = $1, channel_id = $2
            """, msg.id, channel.id)
        print(f"[ABSENCES] Nouveau message créé: {msg.id}")

    except Exception as e:
        print(f"[ABSENCES] Erreur: {e}")



async def notify_admins(bot, guild, staff_member, start_date, end_date, reason):
    """Envoie une notification au propriétaire et au super admin."""
    
    notif_embed = discord.Embed(color=EMBED_COLOR)
    
    if LOGO_URL:
        notif_embed.set_author(name="Nouvelle absence déclarée", icon_url=LOGO_URL)
    else:
        notif_embed.set_author(name="Nouvelle absence déclarée")
        
    notif_embed.description = (
        f"**{staff_member.display_name}** a déclaré une absence.\n\n"
        f"📅 **Période**\n"
        f"　Du **{format_date_full_french(start_date)}**\n"
        f"　Au **{format_date_full_french(end_date)}**\n\n"
        f"📝 **Raison**\n"
        f"　{reason or 'Non spécifiée'}"
    )
    notif_embed.set_footer(text="Remember RolePlay")
    
    recipients = []
    
    if guild.owner:
        recipients.append(guild.owner)
    
    super_admin_role = guild.get_role(ROLES.get("super_admin"))
    if super_admin_role:
        for member in super_admin_role.members:
            if member not in recipients and member.id != staff_member.id:
                recipients.append(member)
    
    for recipient in recipients:
        try:
            await recipient.send(embed=notif_embed)
            print(f"[ABSENCES] Notification envoyée à {recipient.name}")
        except discord.Forbidden:
            print(f"[ABSENCES] MP fermés pour {recipient.name}")
        except Exception as e:
            print(f"[ABSENCES] Erreur notification à {recipient}: {e}")


class AbsencesPanelView(discord.ui.View):
    """Vue principale avec le bouton pour déclarer une absence."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Déclarer une absence",
        style=discord.ButtonStyle.primary,
        custom_id="absence_declare",
        emoji="📅"
    )
    async def declare_absence(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(ROLES["support"])
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Seuls les membres du staff peuvent déclarer une absence.",
                ephemeral=True
            )

        await interaction.response.send_modal(AbsenceModal())

class AbsenceModal(discord.ui.Modal):
    """Modal pour déclarer une nouvelle absence."""

    def __init__(self):
        super().__init__(title="Déclarer une absence")

        self.start_input = discord.ui.TextInput(
            label="Date de début",
            placeholder="Ex: 25/12 ou 25/12/2024",
            required=True,
            max_length=10
        )
        self.end_input = discord.ui.TextInput(
            label="Date de fin",
            placeholder="Ex: 02/01 ou 02/01/2025",
            required=True,
            max_length=10
        )
        self.reason_input = discord.ui.TextInput(
            label="Raison (optionnel)",
            style=discord.TextStyle.long,
            placeholder="Ex: Vacances, raisons personnelles, maladie...",
            required=False,
            max_length=200
        )
        
        self.add_item(self.start_input)
        self.add_item(self.end_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        start_date = parse_date(self.start_input.value)
        end_date = parse_date(self.end_input.value)
        reason = self.reason_input.value.strip() if self.reason_input.value else None

        if not start_date:
            return await interaction.followup.send(
                "❌ **Date de début invalide.**\nFormat attendu : JJ/MM ou JJ/MM/YYYY",
                ephemeral=True
            )

        if not end_date:
            return await interaction.followup.send(
                "❌ **Date de fin invalide.**\nFormat attendu : JJ/MM ou JJ/MM/YYYY",
                ephemeral=True
            )

        if end_date < start_date:
            return await interaction.followup.send(
                "❌ **La date de fin doit être après la date de début.**",
                ephemeral=True
            )

        today = datetime.date.today()
        if end_date < today:
            return await interaction.followup.send(
                "❌ **La période d'absence est déjà terminée.**",
                ephemeral=True
            )

        bot = interaction.client
        if bot.pool:
            async with bot.pool.acquire() as conn:
                existing = await conn.fetchval("""
                    SELECT COUNT(*) FROM staff_absences 
                    WHERE staff_id = $1 
                    AND NOT (end_date < $2 OR start_date > $3)
                """, interaction.user.id, start_date.isoformat(), end_date.isoformat())

                if existing > 0:
                    return await interaction.followup.send(
                        "❌ **Vous avez déjà une absence déclarée sur cette période.**",
                        ephemeral=True
                    )

                await conn.execute("""
                    INSERT INTO staff_absences (staff_id, start_date, end_date, reason)
                    VALUES ($1, $2, $3, $4)
                """, interaction.user.id, start_date.isoformat(), end_date.isoformat(), reason)
                
            print(f"[ABSENCES] Nouvelle absence enregistrée pour {interaction.user.name}")

     
        await update_absences_embed(bot)

     
        await notify_admins(bot, interaction.guild, interaction.user, start_date, end_date, reason)

      
        confirm_embed = discord.Embed(color=0x2ECC71)
        if LOGO_URL:
            confirm_embed.set_author(name="Absence enregistrée", icon_url=LOGO_URL)
        else:
            confirm_embed.set_author(name="Absence enregistrée")
        confirm_embed.description = (
            f"**Période :** {format_date_french(start_date)} → {format_date_french(end_date)}\n"
            f"**Raison :** {reason or 'Non spécifiée'}"
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)


class ManageAbsenceView(discord.ui.View):
    """Vue pour gérer/supprimer ses propres absences."""

    def __init__(self, bot, user_id: int, absences: list):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id

        if not absences:
            return

        options = []
        for absence in absences:
            start = datetime.date.fromisoformat(absence['start_date'])
            end = datetime.date.fromisoformat(absence['end_date'])
            label = f"{format_date_french(start)} → {format_date_french(end)}"
            reason = absence['reason'][:50] if absence['reason'] else "Sans raison"

            options.append(discord.SelectOption(
                label=label,
                description=reason,
                value=str(absence['id'])
            ))

        select = discord.ui.Select(
            placeholder="Sélectionnez l'absence à supprimer",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        absence_id = int(interaction.data["values"][0])

        if not self.bot.pool:
            return await interaction.response.send_message("❌ Erreur BDD.", ephemeral=True)

        async with self.bot.pool.acquire() as conn:
            absence = await conn.fetchrow(
                "SELECT * FROM staff_absences WHERE id = $1 AND staff_id = $2",
                absence_id, self.user_id
            )

            if not absence:
                return await interaction.response.send_message("❌ Absence introuvable.", ephemeral=True)

            await conn.execute("DELETE FROM staff_absences WHERE id = $1", absence_id)

        await update_absences_embed(self.bot)

        await interaction.response.edit_message(
            content="✅ **Absence supprimée avec succès.**",
            view=None
        )
        self.stop()


class AbsencesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(AbsencesPanelView())

        if self.bot.pool:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS staff_absences (
                        id SERIAL PRIMARY KEY,
                        staff_id BIGINT NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        reason TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)

        await update_absences_embed(self.bot)

    @app_commands.command(name="setup_absences", description="Installe le panneau des absences")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_absences(self, interaction: discord.Interaction):
        embed = discord.Embed(color=EMBED_COLOR)
        
        if LOGO_URL:
            embed.set_author(name="ABSENCES DU STAFF", icon_url=LOGO_URL)
        else:
            embed.set_author(name="ABSENCES DU STAFF")
            
        embed.description = (
            "```\n"
            "      Aucune absence déclarée\n"
            "```"
        )
        embed.set_footer(text="Mis à jour • 0 absent actuellement")

        msg = await interaction.channel.send(embed=embed, view=AbsencesPanelView())

        if self.bot.pool:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO persistent_messages (key, message_id, channel_id) 
                    VALUES ('absences_panel', $1, $2)
                    ON CONFLICT (key) DO UPDATE SET message_id = $1, channel_id = $2
                """, msg.id, interaction.channel.id)

        await interaction.response.send_message("✅ Panneau des absences installé.", ephemeral=True)

    @app_commands.command(name="mes_absences", description="Gérer mes absences déclarées")
    async def my_absences(self, interaction: discord.Interaction):
        staff_role = interaction.guild.get_role(ROLES["support"])
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Seuls les membres du staff peuvent utiliser cette commande.",
                ephemeral=True
            )

        if not self.bot.pool:
            return await interaction.response.send_message("❌ BDD indisponible.", ephemeral=True)

        today = datetime.date.today().isoformat()

        async with self.bot.pool.acquire() as conn:
            absences = await conn.fetch("""
                SELECT * FROM staff_absences 
                WHERE staff_id = $1 AND end_date >= $2
                ORDER BY start_date ASC
            """, interaction.user.id, today)

        if not absences:
            return await interaction.response.send_message(
                "📭 **Vous n'avez aucune absence déclarée.**",
                ephemeral=True
            )

        embed = discord.Embed(color=EMBED_COLOR)
        if LOGO_URL:
            embed.set_author(name="Mes absences", icon_url=LOGO_URL)
        else:
            embed.set_author(name="Mes absences")

        lines = []
        for absence in absences:
            start = datetime.date.fromisoformat(absence['start_date'])
            end = datetime.date.fromisoformat(absence['end_date'])
            reason = absence['reason'] or "Non spécifiée"
            lines.append(f"• `{format_date_french(start)}` → `{format_date_french(end)}`\n　_{reason}_")

        embed.description = "\n\n".join(lines)
        embed.set_footer(text="Sélectionnez ci-dessous pour supprimer")

        await interaction.response.send_message(
            embed=embed,
            view=ManageAbsenceView(self.bot, interaction.user.id, absences),
            ephemeral=True
        )

    @app_commands.command(name="clear_absences", description="Supprimer toutes les absences (admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_absences(self, interaction: discord.Interaction):
        if not self.bot.pool:
            return await interaction.response.send_message("❌ BDD indisponible.", ephemeral=True)

        async with self.bot.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM staff_absences")
            count = int(result.split(" ")[1]) if result else 0

        await update_absences_embed(self.bot)

        await interaction.response.send_message(
            f"✅ **{count}** absence(s) supprimée(s).",
            ephemeral=True
        )

    @app_commands.command(name="forcer_absence", description="Déclarer une absence pour un membre du staff (admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_absence(
        self,
        interaction: discord.Interaction,
        membre: discord.Member,
        debut: str,
        fin: str,
        raison: str = None
    ):
        staff_role = interaction.guild.get_role(ROLES["support"])
        if staff_role not in membre.roles:
            return await interaction.response.send_message(
                "❌ Ce membre n'est pas dans le staff.",
                ephemeral=True
            )

        start_date = parse_date(debut)
        end_date = parse_date(fin)

        if not start_date or not end_date:
            return await interaction.response.send_message(
                "❌ **Format de date invalide.**\nUtilisez JJ/MM ou JJ/MM/YYYY",
                ephemeral=True
            )

        if end_date < start_date:
            return await interaction.response.send_message(
                "❌ **La date de fin doit être après la date de début.**",
                ephemeral=True
            )

        if not self.bot.pool:
            return await interaction.response.send_message("❌ BDD indisponible.", ephemeral=True)

        async with self.bot.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO staff_absences (staff_id, start_date, end_date, reason)
                VALUES ($1, $2, $3, $4)
            """, membre.id, start_date.isoformat(), end_date.isoformat(), raison)

        await update_absences_embed(self.bot)

        await interaction.response.send_message(
            f"✅ Absence enregistrée pour **{membre.display_name}**\n"
            f"Du {format_date_french(start_date)} au {format_date_french(end_date)}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AbsencesCog(bot))
