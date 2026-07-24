import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import os
import json
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

# Конфигурация
TOKEN = os.getenv('MTUyOTk5OTQyNjE5MjQwODgyNg.GhV6j5.dx3gWwAvBm2WyebZuP_Ys3Wgk9VX-Juih9uMj8')
GUILD_ID = int(os.getenv('1528337219612311633', 0))
CATEGORY_ID = int(os.getenv('1529240936356380672', 0))
STAFF_ROLE_ID = int(os.getenv('STAFF_ROLE_ID', 0))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))
TICKET_LIFETIME_HOURS = int(os.getenv('TICKET_LIFETIME_HOURS', 10))

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# Настройка интентов
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Хранилище тикетов
tickets = {}
ticket_history = {}

# ============ КНОПКИ ДЛЯ ТИКЕТОВ ============

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="📋 Общие вопросы", 
        style=discord.ButtonStyle.primary,  # Синяя кнопка
        custom_id="general", 
        emoji="📋"
    )
    async def general_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Общие вопросы")
    
    @discord.ui.button(
        label="🔄 Восстановление вещей", 
        style=discord.ButtonStyle.success,  # Зеленая кнопка
        custom_id="restore", 
        emoji="🔄"
    )
    async def restore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Восстановление вещей")
    
    @discord.ui.button(
        label="⚙️ Технические проблемы", 
        style=discord.ButtonStyle.secondary,  # Серая кнопка (исправлено)
        custom_id="tech", 
        emoji="⚙️"
    )
    async def tech_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Технические проблемы")
    
    @discord.ui.button(
        label="⚠️ Жалоба на игрока", 
        style=discord.ButtonStyle.danger,  # Красная кнопка
        custom_id="player_report", 
        emoji="⚠️"
    )
    async def player_report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Жалоба на игрока")
    
    @discord.ui.button(
        label="👑 Жалоба на Администрацию", 
        style=discord.ButtonStyle.danger,  # Красная кнопка
        custom_id="admin_report", 
        emoji="👑"
    )
    async def admin_report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Жалоба на Администрацию")
    
    async def create_ticket(self, interaction: discord.Interaction, topic: str):
        # Проверка на существующий тикет
        for ticket in tickets.values():
            if ticket['user_id'] == interaction.user.id and ticket['status'] == 'open':
                await interaction.response.send_message(
                    "❌ У вас уже есть открытый тикет!",
                    ephemeral=True
                )
                return
        
        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=CATEGORY_ID)
        
        if not category:
            await interaction.response.send_message(
                "❌ Категория для тикетов не найдена! Обратитесь к администратору.",
                ephemeral=True
            )
            return
        
        # Создание канала
        ticket_number = len([t for t in tickets.values() if t['status'] == 'open']) + 1
        channel_name = f"ticket-{interaction.user.name.lower()}-{ticket_number}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Тикет от {interaction.user.name} - {topic}"
        )
        
        # Сохранение тикета
        tickets[channel.id] = {
            'user_id': interaction.user.id,
            'user_name': interaction.user.name,
            'topic': topic,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'closing_time': (datetime.now() + timedelta(hours=TICKET_LIFETIME_HOURS)).isoformat()
        }
        
        # Отправка сообщения
        embed = discord.Embed(
            title="🎫 HS TICKET | Центр поддержки",
            description=f"Тикет создан по теме: **{topic}**",
            color=0x00ff00
        )
        embed.add_field(
            name="🆔 Укажите ваш SteamID64",
            value="Можно узнать тут: https://steamid.io",
            inline=False
        )
        embed.add_field(
            name="👤 Ваш ник в игре",
            value="Укажите игровой ник",
            inline=False
        )
        embed.add_field(
            name="📝 Кратко о проблеме",
            value="До 30 символов",
            inline=False
        )
        embed.add_field(
            name="⏰ Автоматическое закрытие",
            value=f"Через {TICKET_LIFETIME_HOURS} часов",
            inline=False
        )
        embed.set_footer(text=f"Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        
        view = TicketControlView()
        staff_role = guild.get_role(STAFF_ROLE_ID)
        await channel.send(
            f"{interaction.user.mention} {staff_role.mention if staff_role else ''}",
            embed=embed,
            view=view
        )
        
        # Запуск таймера
        bot.loop.create_task(auto_close_ticket(channel.id))
        
        # Логирование
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="📩 Создан новый тикет",
                description=(
                    f"👤 **Пользователь:** {interaction.user.mention}\n"
                    f"📂 **Тема:** {topic}\n"
                    f"📌 **Канал:** {channel.mention}"
                ),
                color=0x00ff00,
                timestamp=datetime.now()
            )
            await log_channel.send(embed=log_embed)
        
        await interaction.response.send_message(
            f"✅ Тикет создан! Перейдите в {channel.mention}",
            ephemeral=True
        )

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="❌ Закрыть тикет", 
        style=discord.ButtonStyle.danger,  # Красная кнопка
        custom_id="close_ticket", 
        emoji="❌"
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and not interaction.user.get_role(STAFF_ROLE_ID):
            await interaction.response.send_message(
                "❌ У вас нет прав для закрытия тикета!",
                ephemeral=True
            )
            return
        
        channel = interaction.channel
        if channel.id not in tickets:
            await interaction.response.send_message(
                "❌ Тикет не найден в системе!",
                ephemeral=True
            )
            return
        
        await close_ticket(channel, interaction.user, "Закрыт по запросу персонала")
        await interaction.response.send_message("🔄 Тикет закрывается...")
    
    @discord.ui.button(
        label="⏰ Продлить тикет", 
        style=discord.ButtonStyle.primary,  # Синяя кнопка
        custom_id="extend_ticket", 
        emoji="⏰"
    )
    async def extend_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and not interaction.user.get_role(STAFF_ROLE_ID):
            await interaction.response.send_message(
                "❌ У вас нет прав для продления тикета!",
                ephemeral=True
            )
            return
        
        channel = interaction.channel
        if channel.id not in tickets:
            await interaction.response.send_message(
                "❌ Тикет не найден в системе!",
                ephemeral=True
            )
            return
        
        tickets[channel.id]['closing_time'] = (datetime.now() + timedelta(hours=TICKET_LIFETIME_HOURS)).isoformat()
        
        embed = discord.Embed(
            title="⏰ Тикет продлен",
            description=f"Тикет продлен на **{TICKET_LIFETIME_HOURS}** часов",
            color=0x00ff00
        )
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Тикет продлен до {datetime.now() + timedelta(hours=TICKET_LIFETIME_HOURS)}",
            ephemeral=True
        )

async def auto_close_ticket(channel_id):
    """Автоматическое закрытие тикета"""
    await asyncio.sleep(TICKET_LIFETIME_HOURS * 3600)
    
    if channel_id not in tickets or tickets[channel_id]['status'] != 'open':
        return
    
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    
    # Предупреждение о закрытии
    embed = discord.Embed(
        title="⏰ Автоматическое закрытие",
        description="Тикет будет закрыт через **60 секунд**",
        color=0xff0000
    )
    await channel.send(embed=embed)
    await asyncio.sleep(60)
    
    if channel_id not in tickets or tickets[channel_id]['status'] != 'open':
        return
    
    await close_ticket(channel, bot.user, "Автоматическое закрытие по истечении времени")

async def close_ticket(channel, closer, reason):
    """Закрытие тикета с логированием"""
    if channel.id not in tickets:
        return
    
    ticket_info = tickets[channel.id]
    
    # Сбор сообщений для лога
    messages = []
    async for msg in channel.history(limit=200, oldest_first=True):
        messages.append(
            f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{msg.author.name}: {msg.content[:100]}"
        )
    
    # Логирование
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="📪 Тикет закрыт",
            description=(
                f"👤 **Создатель:** {ticket_info['user_name']}\n"
                f"📂 **Тема:** {ticket_info['topic']}\n"
                f"🔒 **Закрыл:** {closer.name if hasattr(closer, 'name') else 'Auto'}\n"
                f"📝 **Причина:** {reason}\n"
                f"⏱ **Время жизни:** {((datetime.now() - datetime.fromisoformat(ticket_info['created_at'])).total_seconds() / 3600):.1f} ч"
            ),
            color=0xff0000,
            timestamp=datetime.now()
        )
        await log_channel.send(embed=embed)
        
        # Сохранение лога в файл
        log_text = f"""=== ЛОГ ТИКЕТА ===
ID: {channel.id}
Создан: {ticket_info['created_at']}
Закрыт: {datetime.now().isoformat()}
Пользователь: {ticket_info['user_name']} (ID: {ticket_info['user_id']})
Тема: {ticket_info['topic']}
Причина: {reason}
========================

=== ИСТОРИЯ СООБЩЕНИЙ ===
"""
        log_text += "\n".join(messages)
        
        filename = f"ticket_log_{channel.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(log_text)
        
        await log_channel.send(file=discord.File(filename))
        os.remove(filename)
    
    # Удаление тикета
    del tickets[channel.id]
    await channel.delete()

# ============ СЛЕШ-КОМАНДЫ ============

@tree.command(
    name="setup",
    description="📌 Создать сообщение с кнопками для создания тикетов"
)
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    """Создает сообщение с кнопками для тикетов"""
    embed = discord.Embed(
        title="🎫 Добро пожаловать",
        description="Создайте тикет, нажав на кнопку ниже",
        color=0x3498db
    )
    embed.add_field(
        name="📌 Информация",
        value=(
            f"⏰ **Тикеты закрываются через {TICKET_LIFETIME_HOURS} часов**\n"
            f"👥 **Персонал:** <@&{STAFF_ROLE_ID}>\n"
            f"📋 **Выберите тему обращения:**"
        ),
        inline=False
    )
    embed.set_footer(text=f"Система тикетов v2.0")
    
    view = TicketView()
    await interaction.response.send_message(embed=embed, view=view)

@tree.command(
    name="stats",
    description="📊 Показать статистику по тикетам"
)
@app_commands.default_permissions(administrator=True)
async def slash_stats(interaction: discord.Interaction):
    """Показывает статистику по тикетам"""
    open_tickets = len([t for t in tickets.values() if t['status'] == 'open'])
    closed_tickets = len([t for t in tickets.values() if t['status'] == 'closed'])
    total = len(tickets)
    
    # Статистика по темам
    topics = {}
    for ticket in tickets.values():
        topic = ticket['topic']
        topics[topic] = topics.get(topic, 0) + 1
    
    embed = discord.Embed(
        title="📊 Статистика тикетов",
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.add_field(name="🟢 Открыто", value=open_tickets, inline=True)
    embed.add_field(name="🔴 Закрыто", value=closed_tickets, inline=True)
    embed.add_field(name="📋 Всего", value=total, inline=True)
    
    if topics:
        topic_list = "\n".join([f"• {topic}: {count}" for topic, count in topics.items()])
        embed.add_field(name="📈 По темам", value=topic_list, inline=False)
    
    await interaction.response.send_message(embed=embed)

@tree.command(
    name="logs",
    description="📋 Показать логи закрытых тикетов"
)
@app_commands.default_permissions(administrator=True)
async def slash_logs(interaction: discord.Interaction):
    """Показывает последние закрытые тикеты"""
    # Получаем закрытые тикеты
    closed_tickets = [t for t in tickets.values() if t['status'] == 'closed']
    
    if not closed_tickets:
        await interaction.response.send_message(
            "📭 Нет закрытых тикетов",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="📋 Последние закрытые тикеты",
        color=0x3498db
    )
    
    for ticket in closed_tickets[-5:]:
        created = datetime.fromisoformat(ticket['created_at'])
        embed.add_field(
            name=f"👤 {ticket['user_name']}",
            value=(
                f"📂 **Тема:** {ticket['topic']}\n"
                f"📅 **Создан:** {created.strftime('%d.%m.%Y %H:%M')}"
            ),
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@tree.command(
    name="set_lifetime",
    description="⏰ Установить время жизни тикетов в часах"
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(hours="Количество часов до автоматического закрытия")
async def slash_set_lifetime(interaction: discord.Interaction, hours: int):
    """Устанавливает время жизни тикетов"""
    global TICKET_LIFETIME_HOURS
    
    if hours < 1 or hours > 720:
        await interaction.response.send_message(
            "❌ Время должно быть от 1 до 720 часов (30 дней)!",
            ephemeral=True
        )
        return
    
    TICKET_LIFETIME_HOURS = hours
    
    embed = discord.Embed(
        title="✅ Время жизни обновлено",
        description=f"Тикеты теперь закрываются через **{hours}** часов",
        color=0x00ff00
    )
    await interaction.response.send_message(embed=embed)

@tree.command(
    name="close",
    description="❌ Закрыть текущий тикет"
)
@app_commands.default_permissions(administrator=True)
async def slash_close(interaction: discord.Interaction):
    """Закрывает текущий тикет"""
    channel = interaction.channel
    
    if channel.id not in tickets:
        await interaction.response.send_message(
            "❌ Это не тикет или тикет уже закрыт!",
            ephemeral=True
        )
        return
    
    if tickets[channel.id]['status'] != 'open':
        await interaction.response.send_message(
            "❌ Этот тикет уже закрыт!",
            ephemeral=True
        )
        return
    
    await close_ticket(channel, interaction.user, "Закрыт командой /close")
    await interaction.response.send_message("🔄 Тикет закрывается...")

@tree.command(
    name="extend",
    description="⏰ Продлить текущий тикет"
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(hours="На сколько часов продлить (по умолчанию - стандартное время)")
async def slash_extend(interaction: discord.Interaction, hours: int = None):
    """Продлевает время жизни тикета"""
    channel = interaction.channel
    
    if channel.id not in tickets:
        await interaction.response.send_message(
            "❌ Это не тикет!",
            ephemeral=True
        )
        return
    
    if tickets[channel.id]['status'] != 'open':
        await interaction.response.send_message(
            "❌ Этот тикет уже закрыт!",
            ephemeral=True
        )
        return
    
    if hours is None:
        hours = TICKET_LIFETIME_HOURS
    
    tickets[channel.id]['closing_time'] = (datetime.now() + timedelta(hours=hours)).isoformat()
    
    embed = discord.Embed(
        title="⏰ Тикет продлен",
        description=f"Тикет продлен на **{hours}** часов",
        color=0x00ff00
    )
    await channel.send(embed=embed)
    await interaction.response.send_message(
        f"✅ Тикет продлен до {datetime.now() + timedelta(hours=hours)}",
        ephemeral=True
    )

@tree.command(
    name="help",
    description="🆘 Показать список всех команд"
)
async def slash_help(interaction: discord.Interaction):
    """Показывает справку по командам"""
    embed = discord.Embed(
        title="🆘 Помощь по командам",
        description="Все доступные команды бота:",
        color=0x3498db
    )
    
    # Команды для всех
    embed.add_field(
        name="👤 Команды для всех",
        value=(
            "`/help` - Показать эту справку\n"
            "• Используйте кнопки для создания тикета"
        ),
        inline=False
    )
    
    # Команды для персонала
    embed.add_field(
        name="👥 Команды для персонала",
        value=(
            "`/close` - Закрыть текущий тикет\n"
            "`/extend [часы]` - Продлить тикет\n"
            "• Кнопки в тикете для управления"
        ),
        inline=False
    )
    
    # Команды для администраторов
    embed.add_field(
        name="🛠️ Команды для администраторов",
        value=(
            "`/setup` - Создать сообщение с кнопками\n"
            "`/stats` - Показать статистику\n"
            "`/logs` - Показать логи\n"
            "`/set_lifetime [часы]` - Изменить время жизни"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"Версия: 2.0 | Тикеты живут {TICKET_LIFETIME_HOURS} ч")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ ОБЫЧНЫЕ КОМАНДЫ (для совместимости) ============

@bot.command(name='setup')
@commands.has_permissions(administrator=True)
async def cmd_setup(ctx):
    """!setup - Создать сообщение с кнопками"""
    embed = discord.Embed(
        title="🎫 Добро пожаловать",
        description="Создайте тикет, нажав на кнопку ниже",
        color=0x3498db
    )
    embed.add_field(
        name="📌 Информация",
        value=f"⏰ **Тикеты закрываются через {TICKET_LIFETIME_HOURS} часов**",
        inline=False
    )
    
    view = TicketView()
    await ctx.send(embed=embed, view=view)
    await ctx.message.delete()

@bot.command(name='stats')
@commands.has_permissions(administrator=True)
async def cmd_stats(ctx):
    """!stats - Показать статистику"""
    open_tickets = len([t for t in tickets.values() if t['status'] == 'open'])
    closed_tickets = len([t for t in tickets.values() if t['status'] == 'closed'])
    total = len(tickets)
    
    embed = discord.Embed(
        title="📊 Статистика",
        color=0x3498db
    )
    embed.add_field(name="🟢 Открыто", value=open_tickets, inline=True)
    embed.add_field(name="🔴 Закрыто", value=closed_tickets, inline=True)
    embed.add_field(name="📋 Всего", value=total, inline=True)
    
    await ctx.send(embed=embed)

# ============ СОБЫТИЯ ============

@bot.event
async def on_ready():
    """Запуск бота"""
    print(f'✅ Бот запущен: {bot.user}')
    print(f'📊 На серверах: {len(bot.guilds)}')
    print(f'🆔 ID бота: {bot.user.id}')
    
    # Синхронизация слеш-команд
    try:
        synced = await tree.sync()
        print(f'✅ Синхронизировано {len(synced)} слеш-команд')
        for cmd in synced:
            print(f'   • /{cmd.name} - {cmd.description}')
    except Exception as e:
        print(f'❌ Ошибка синхронизации: {e}')
    
    # Создание основного сообщения
    guild = bot.get_guild(GUILD_ID)
    if guild:
        ticket_channel = discord.utils.get(guild.text_channels, name="tickets")
        if ticket_channel:
            # Очистка старых сообщений
            async for message in ticket_channel.history(limit=100):
                if message.author == bot.user:
                    await message.delete()
            
            embed = discord.Embed(
                title="🎫 Добро пожаловать",
                description="Создайте тикет, нажав на кнопку ниже",
                color=0x3498db
            )
            embed.add_field(
                name="📌 Информация",
                value=(
                    f"⏰ **Тикеты закрываются через {TICKET_LIFETIME_HOURS} часов**\n"
                    f"👥 **Персонал:** <@&{STAFF_ROLE_ID}>\n"
                    f"📋 **Выберите тему обращения:**"
                ),
                inline=False
            )
            
            view = TicketView()
            await ticket_channel.send(embed=embed, view=view)
            print('✅ Сообщение создано в #tickets')
        else:
            print('⚠️ Канал #tickets не найден!')

@bot.event
async def on_message(message):
    """Обработка сообщений"""
    if message.author.bot:
        return
    
    # Сохранение сообщений в тикетах
    if message.channel.id in tickets:
        tickets[message.channel.id]['last_message'] = datetime.now().isoformat()
    
    await bot.process_commands(message)

# ============ ЗАПУСК ============

if __name__ == '__main__':
    print("🚀 Запуск бота...")
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Ошибка: Неправильный токен!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
