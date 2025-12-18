import os
import discord
import asyncpg
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


class RememberBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.pool = None

    async def setup_hook(self):
        if DATABASE_URL:
            try:
                self.pool = await asyncpg.create_pool(dsn=DATABASE_URL)
                print("[DB] Connexion PostgreSQL établie.")

                async with self.pool.acquire() as conn:
                    
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS ticket_logs (
                            ticket_id BIGINT PRIMARY KEY,
                            user_id BIGINT,
                            transcript TEXT,
                            closed_at TIMESTAMP DEFAULT NOW()
                        );
                    """)
                    
                    
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS reprise_projects (
                            id SERIAL PRIMARY KEY,
                            name TEXT UNIQUE NOT NULL,
                            priority BOOLEAN DEFAULT FALSE
                        );
                    """)

                    
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS rdv_planning (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT,
                            staff_id BIGINT,
                            day TEXT,
                            hour TEXT,
                            rdv_timestamp BIGINT, 
                            channel_id BIGINT,
                            created_at TIMESTAMP DEFAULT NOW()
                        );
                    """)
                
                    
                    try:
                        await conn.execute("ALTER TABLE rdv_planning ADD COLUMN IF NOT EXISTS rdv_timestamp BIGINT;")
                    except Exception:
                        pass 
                    
                    
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS persistent_messages (
                            key TEXT PRIMARY KEY,
                            message_id BIGINT,
                            channel_id BIGINT
                        );
                    """)
                    
                    
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

                    
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS useful_links (
                            label TEXT PRIMARY KEY,
                            url TEXT NOT NULL
                        );
                    """)

            except Exception as e:
                print(f"[DB] Erreur : {e}")

        extensions = [
            "cogs.tickets",
            "cogs.absences",
            "cogs.reglement",  
            "cogs.liens"       
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"[COG] {ext} chargé.")
            except Exception as e:
                print(f"[COG] Erreur {ext} : {e}")

        
        from config import GUILD_ID
        guild = discord.Object(id=GUILD_ID)
        
        
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"[BOT] {len(synced)} commandes synchronisées sur le serveur.")
        
        
        self.tree.clear_commands(guild=None)
        await self.tree.sync()

    async def close(self):
        if self.pool:
            await self.pool.close()
        await super().close()

    async def on_ready(self):
        print(f"[BOT] Connecté : {self.user} (ID: {self.user.id})")
        if not self.update_status.is_running():
            self.update_status.start()

    @tasks.loop(minutes=5)
    async def update_status(self):
        total = sum(g.member_count for g in self.guilds)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{total} membres"
            )
        )

    @update_status.before_loop
    async def before_update_status(self):
        await self.wait_until_ready()


bot = RememberBot()

if __name__ == "__main__":
    if not TOKEN:
        print("[ERREUR] Token non configuré.")
    else:
        bot.run(TOKEN)
