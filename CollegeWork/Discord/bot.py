from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import aiohttp
import io
import random
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN не найден. Проверь файл .env")
STAFF_ROLE_IDS = [1424204029919232090]
TICKET_CATEGORY_NAME = "🎫 Tickets"
LOG_CHANNEL_ID = 1461940592581021819

#  Настройки бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
    label="🎫 Создать тикет",
    style=discord.ButtonStyle.green,
    custom_id="ticket_create"
)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        channel_name = f"ticket-{user.id}"
        if discord.utils.get(category.channels, name=channel_name):
            return await interaction.followup.send(
                "❌ У тебя уже есть открытый тикет.", ephemeral=True
            )

        overwrites = {
    guild.default_role: discord.PermissionOverwrite(view_channel=False),
    user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
}

        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )

        await channel.send(
            f"🎫 {user.mention}, опиши свою проблему.\n"
            "Нажми кнопку ниже, чтобы закрыть тикет.",
            view=CloseTicketView()
        )

# Закрытие тикета

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
    label="🔒 Закрыть тикет",
    style=discord.ButtonStyle.red,
    custom_id="ticket_close"
)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message("❌ Это не тикет.", ephemeral=True)

        await interaction.response.send_message("🔒 Тикет будет закрыт через 5 секунд.")

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete()
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ У меня нет прав на удаление этого канала.",
                ephemeral=True
            )

class MyBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(TicketView())
        self.add_view(CloseTicketView())

bot = MyBot(command_prefix="!", intents=intents)

async def send_log(embed: discord.Embed):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

# Random

@bot.tree.command(name="random", description="Задай вопрос, и я дам случайный ответ!")
async def random_answer(interaction: discord.Interaction, question: str):
    answers = ["Да", "Нет", "Не уверен", "Возможно", "Может быть"]
    await interaction.response.send_message(f"Ты спросил: {question}\nОтвет: {random.choice(answers)}")

# Say

@bot.tree.command(name="say", description="Бот скажет то, что ты напишешь")
async def say_slash(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)

# вывод аватарки

@bot.tree.command(name="avatar", description="Показать аватарку выбранного пользователя")
async def avatar_slash(interaction: discord.Interaction, user: discord.User | None = None):
    user = user or interaction.user
    embed = discord.Embed(title=f"Аватар {user.name}", color=discord.Color.blurple())
    embed.set_image(url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# Clear

@bot.tree.command(name="clear", description="Удалить сообщения в канале")
@app_commands.describe(amount="Количество сообщений (1–100)")
async def clear_slash(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    if interaction.guild is None:
        return await interaction.response.send_message("Эта команда работает только на сервере.", ephemeral=True)

    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ Тебе нужны права **Управление сообщениями**.", ephemeral=True)

    bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member is None:
        bot_member = await interaction.guild.fetch_member(bot.user.id)

    perms = interaction.channel.permissions_for(bot_member)
    
    if not perms.manage_messages:
        return await interaction.response.send_message(
        "❌ У меня нет прав **Управление сообщениями**.", ephemeral=True
    )

    await interaction.response.send_message(f"🧹 Удаляю {amount} сообщений…", ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"✔ Удалено **{len(deleted)}** сообщений.", ephemeral=True)

# Тикеты

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"Слэш-команды синхронизированы как {bot.user}")
    except Exception as e:
        print(f"Ошибка синхронизации слэш-команд: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    embed = discord.Embed(
        title="🚪 Участник зашёл",
        color=discord.Color.green()
    )
    embed.add_field(name="Пользователь", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Аккаунт создан", value=member.created_at.strftime("%d.%m.%Y %H:%M"), inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)

    await send_log(embed)

@bot.event
async def on_member_remove(member: discord.Member):
    embed = discord.Embed(
        title="🚪 Участник вышел",
        color=discord.Color.red()
    )
    embed.add_field(
        name="Пользователь",
        value=f"{member} ({member.id})",
        inline=False
    )
    embed.add_field(
        name="Аккаунт создан",
        value=member.created_at.strftime("%d.%m.%Y %H:%M"),
        inline=False
    )
    embed.set_thumbnail(url=member.display_avatar.url)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot:
        return
    if before.content == after.content:
        return
    embed = discord.Embed(
        title="✏️ Сообщение отредактировано",
        color=discord.Color.orange()
    )
    embed.add_field(
        name="Автор",
        value=f"{before.author} ({before.author.id})",
        inline=False
    )
    embed.add_field(
        name="Канал",
        value=before.channel.mention,
        inline=False
    )
    embed.add_field(
        name="Было",
        value=before.content[:1000] if before.content else "*пусто*",
        inline=False
    )
    embed.add_field(
        name="Стало",
        value=after.content[:1000] if after.content else "*пусто*",
        inline=False
    )
    embed.add_field(
        name="Ссылка",
        value=f"[Перейти к сообщению]({after.jump_url})",
        inline=False
    )
    embed.set_thumbnail(url=before.author.display_avatar.url)

    await send_log(embed)

@bot.tree.command(name="ticket-panel", description="Панель создания тикетов")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    
    await interaction.response.send_message(
        "🎫 Нажми кнопку, чтобы создать тикет:",
        view=TicketView()
    )

# Запуск бота
bot.run(TOKEN)