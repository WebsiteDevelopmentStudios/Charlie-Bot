import os
import asyncio
import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class CharlieBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        commands_synced = await self.tree.sync()
        logging.info("Synced %d slash commands", len(commands_synced))


bot = CharlieBot()
linked_channel_id = None


@bot.event
async def on_ready():
    logging.info("Logged in as %s (%s)", bot.user, bot.user.id)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="your server"
        )
    )


def moderator():
    async def check(interaction):
        if not interaction.guild:
            raise app_commands.CheckFailure("This command only works in a server.")
        if not interaction.user.guild_permissions.manage_messages:
            raise app_commands.CheckFailure("You need the Manage Messages permission.")
        return True
    return app_commands.check(check)


@bot.tree.command(name="ping", description="Check Charlie's latency.")
async def ping(interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms")


@bot.tree.command(name="serverinfo", description="Show server information.")
async def serverinfo(interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message("This only works in a server.")
    embed = discord.Embed(title=guild.name, color=discord.Color.blurple())
    embed.add_field(name="Members", value=str(guild.member_count))
    embed.add_field(name="Channels", value=str(len(guild.channels)))
    embed.add_field(name="Roles", value=str(len(guild.roles)))
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Show information about a member.")
@app_commands.describe(member="The member to inspect.")
async def userinfo(interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=str(member), color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="User ID", value=str(member.id))
    embed.add_field(name="Created", value=discord.utils.format_dt(member.created_at, "F"))
    if member.joined_at:
        embed.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, "F"))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="avatar", description="Show a member's avatar.")
@app_commands.describe(member="The member whose avatar you want.")
async def avatar(interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member.display_name}'s Avatar")
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="clear", description="Delete messages from this channel.")
@app_commands.describe(amount="Number of messages to delete, from 1 to 100.")
@moderator()
async def clear(interaction, amount: app_commands.Range[int, 1, 100]):
    if not hasattr(interaction.channel, "purge"):
        return await interaction.response.send_message("I cannot clear messages here.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted {len(deleted)} message(s).", ephemeral=True)


@bot.tree.command(name="kick", description="Kick a member.")
@app_commands.describe(member="Member to kick.", reason="Reason.")
@moderator()
async def kick(interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user or member.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("You cannot moderate that member.", ephemeral=True)
    try:
        await member.kick(reason=f"{reason} | By {interaction.user}")
        await interaction.response.send_message(f"👢 Kicked {member}. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to kick that member.", ephemeral=True)


@bot.tree.command(name="ban", description="Ban a member.")
@app_commands.describe(member="Member to ban.", reason="Reason.")
@moderator()
async def ban(interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user or member.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("You cannot moderate that member.", ephemeral=True)
    try:
        await member.ban(reason=f"{reason} | By {interaction.user}", delete_message_seconds=0)
        await interaction.response.send_message(f"🔨 Banned {member}. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to ban that member.", ephemeral=True)


@bot.tree.command(name="timeout", description="Timeout a member.")
@app_commands.describe(member="Member to timeout.", minutes="Length in minutes.", reason="Reason.")
@moderator()
async def timeout(interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 40320], reason: str = "No reason provided"):
    if member == interaction.user or member.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("You cannot moderate that member.", ephemeral=True)
    try:
        await member.timeout(timedelta(minutes=minutes), reason=f"{reason} | By {interaction.user}")
        await interaction.response.send_message(f"⏱️ Timed out {member} for {minutes} minute(s).")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to timeout that member.", ephemeral=True)


@bot.tree.command(name="say", description="Make Charlie send a message.")
@app_commands.describe(message="Message to send.")
@moderator()
async def say(interaction, message: str):
    await interaction.response.send_message("Sent.", ephemeral=True)
    await interaction.channel.send(message)


@bot.tree.command(name="link", description="Link a Discord channel for terminal messages.")
@app_commands.describe(channel="The channel Charlie should use for terminal messages.")
@moderator()
async def link(interaction, channel: discord.TextChannel):
    global linked_channel_id
    linked_channel_id = channel.id
    await interaction.response.send_message(
        f"🔗 Linked terminal messages to {channel.mention}.",
        ephemeral=True
    )


@bot.tree.command(name="help", description="Show Charlie's commands.")
async def help_command(interaction):
    embed = discord.Embed(
        title="🤖 Charlie Bot",
        description=(
            "General: /ping, /serverinfo, /userinfo, /avatar, /help\n"
            "Moderation: /clear, /kick, /ban, /timeout, /say\n"
            "Setup: /link"
        ),
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.error
async def command_error(interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        message = str(error) or "You do not have permission to use that command."
    else:
        logging.error("Slash command error: %s", error, exc_info=error)
        message = "Something went wrong."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def terminal_loop():
    print("\nCharlie terminal ready.")
    print("Commands:")
    print("  /send <message>  - send a message to the linked channel")
    print("  /status           - show bot status")
    print("  /stop             - stop the bot")
    print()
    
    global linked_channel_id

    while not bot.is_closed():
        try:
            command = await asyncio.to_thread(input, "Terminal > ")
        except (EOFError, KeyboardInterrupt):
            await bot.close()
            return

        command = command.strip()
        if not command:
            continue

        if command.startswith("/send "):
            message = command[6:].strip()
            if not message:
                print("Usage: /send <message>")
                continue

            if linked_channel_id is None:
                print("No channel is linked. Run /link #channel in Discord first.")
                continue

            channel = bot.get_channel(linked_channel_id)
            if not isinstance(channel, discord.TextChannel):
                print("The linked channel could not be found. Run /link again.")
                continue

            try:
                await channel.send(message)
                print(f"Sent to #{channel.name}")
            except discord.Forbidden:
                print("Discord denied permission to send messages in that channel.")
            except discord.HTTPException as error:
                print(f"Discord error: {error}")
            continue

        if command == "/status":
            print(f"Logged in as: {bot.user}")
            print(f"Servers: {len(bot.guilds)}")
            print(f"Linked channel: {linked_channel_id or 'None'}")
            print(f"Latency: {round(bot.latency * 1000)}ms")
            continue

        if command == "/stop":
            print("Stopping Charlie-Bot...")
            await bot.close()
            return

        print("Unknown command. Use /send, /status, or /stop.")


async def main():
    terminal_task = asyncio.create_task(terminal_loop())
    try:
        await bot.start(TOKEN)
    finally:
        terminal_task.cancel()
        await asyncio.gather(terminal_task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
