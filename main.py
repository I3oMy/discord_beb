import discord
import json
import os 
import pytz  
import re
import random
import asyncio
import sys
import logging
from discord.app_commands import CheckFailure
from myserver import server_on
from discord.ext import tasks, commands
from discord import app_commands
from discord import ui, Interaction
from datetime import datetime
from discord import ButtonStyle
from cogs.embed_command import EmbedCommand
from cogs.role_reaction import RoleReactionHandler
from discord.ui import Modal, TextInput, Button, View, Select
from discord import TextStyle
from playwright.async_api import async_playwright

CONFIG_FILE = "config.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

intents = discord.Intents.all()
intents.guilds = True
intents.members = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

TARGET_USER_ID = 397002650417233921
last_status = {}

sleep_messages = [
    "ตอนนี้เขานอนอยู่ครับ 😴",
    "กำลังฝันหวานอยู่เลย~ 🌙",
    "พักผ่อนอยู่ครับ อย่าเพิ่งกวน~ 😌"
]

busy_messages = [
    "ว่าไงสุดหล่อ รอแป๊บนะ 🍵",
    "เขาติดภารกิจอยู่ เดี๋ยวตอบนะ~ 💼",
    "ยังไม่ว่างคุยตอนนี้ รอสักครู่ 🕒"
]




@bot.command()
@commands.is_owner()
async def restart(ctx):
    await ctx.send("♻️ กำลังรีสตาร์ทบอท...")
    try:
        # ตรวจสอบว่ามี sys.executable และ sys.argv
        if sys.executable and sys.argv:
            os.execv(sys.executable, ['python'] + sys.argv)
        else:
            await ctx.send("❌ ไม่สามารถรีสตาร์ทได้: ขาด sys.executable หรือ sys.argv")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาดในการรีสตาร์ท: {e}")
        print(f"Error during restart: {e}")

@bot.command()
@commands.is_owner()
async def clearslash(ctx):
    """
    ลบ Global Slash Commands ทั้งหมด และ Sync ใหม่
    """
    try:
        print("🔄 Attempting to clear global commands...")

        # ดึงคำสั่ง Global ทั้งหมดจาก Discord
        global_commands = await bot.tree.fetch_commands()
        print(f"✅ Fetched {len(global_commands)} global commands.")

        # ลบคำสั่ง Global ทีละคำสั่งผ่าน HTTP API
        app_id = bot.user.id
        for command in global_commands:
            await bot.http.delete_global_command(app_id, command.id)
            print(f"🗑️ Deleted global command: {command.name}")

        # Sync ใหม่ (จะว่างเปล่าเพราะลบหมดแล้ว)
        synced = await bot.tree.sync()
        print(f"✅ Commands synced successfully. Synced {len(synced)} commands.")
        await ctx.send("✅ ลบคำสั่ง Global ทั้งหมดและ Sync ใหม่แล้ว!")
    except Exception as e:
        error_message = f"❌ เกิดข้อผิดพลาดขณะลบคำสั่ง: {e}"
        print(error_message)
        await ctx.send(error_message)



@bot.command()
async def send_image(ctx):
    # ถ้าผู้ใช้มีไฟล์แนบ
    if ctx.message.attachments:
        for attachment in ctx.message.attachments:
            if attachment.filename.endswith(('png', 'jpg', 'jpeg', 'gif')):
                # ส่งรูปภาพใน Embed
                embed = discord.Embed(
                    title="ส่งรูปภาพจากคำสั่ง!",
                    description=f"รูปภาพจาก {ctx.author.mention}",
                    color=discord.Color.green()
                )
                embed.set_image(url=attachment.url)
                await ctx.send(embed=embed)        


def is_valid_url(url: str) -> bool:
    return re.match(r'^https?://', url) is not None

def is_moderator_or_admin_slash(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    perms = interaction.user.guild_permissions
    return perms.manage_guild or perms.administrator

# ✅ Group error handler
async def handle_check_failure(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้งานคำสั่งนี้", ephemeral=True)
    else:
        await interaction.response.send_message(f"เกิดข้อผิดพลาด: {error}", ephemeral=True)



def has_any_role_name(role_names: list[str]):
    role_names_lower = [name.lower() for name in role_names]
    
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if not hasattr(interaction.user, "roles"):
            return False
        return any(role.name.lower() in role_names_lower for role in interaction.user.roles)

    return app_commands.check(predicate)




async def check_admin_permission(interaction):
    print(f"User {interaction.user} permissions: {interaction.user.guild_permissions}")
    return interaction.user.guild_permissions.administrator




class WelcomeModal(discord.ui.Modal):
    def __init__(self, title_val="", description_val="", image_val="", color_val=""):
        super().__init__(title="ตั้งค่าข้อความต้อนรับ")

        self.title_input = discord.ui.TextInput(
            label="หัวข้อ Embed (Title)",
            placeholder="เช่น ยินดีต้อนรับ {user}!",
            default=title_val,
            max_length=100,
            required=False
        )
        self.description_input = discord.ui.TextInput(
            label="เนื้อหา Embed",
            placeholder="เช่น อย่าลืมอ่านกฎใน <#1234567890>",
            default=description_val,
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        )
        self.image_input = discord.ui.TextInput(
            label="ลิงก์รูปภาพ (ถ้ามี)",
            placeholder="https://...",
            default=image_val,
            required=False
        )
        self.color_input = discord.ui.TextInput(
            label="สี Embed (เช่น #3498db)",
            placeholder="#3498db",
            default=color_val,
            required=False,
            max_length=7
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.image_input)
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        data = config.get(guild_id, {})

        # ใช้ key แยกเฉพาะสำหรับ welcome
        title = self.title_input.value or data.get("embedwelcome_title", "🎉 ยินดีต้อนรับ!")
        desc = self.description_input.value or data.get("message", "ขอให้สนุกกับการอยู่ที่นี่!")
        image = self.image_input.value or data.get("image_url", "")
        color = self.color_input.value or data.get("color", "#5865F2")

        try:
            embed_color = int(color.replace("#", ""), 16)
        except ValueError:
            await interaction.response.send_message("❌ Invalid color code. Please use a valid hex value (e.g., #3498db).", ephemeral=True)
            return

        # บันทึกด้วยชื่อเฉพาะ
        data["embedwelcome_title"] = title
        data["embedwelcome_message"] = desc
        data["embedwelcome_image_url"] = image
        data["embedwelcome_color"] = color
        data["embedwelcome_enabled"] = True

        config[guild_id] = data
        save_config(config)

        embed = discord.Embed(
            title=title.replace("{user}", interaction.user.mention),
            description=desc.replace("{user}", interaction.user.mention),
            color=embed_color
        )
        if image:
            embed.set_image(url=image)
        embed.set_footer(text=f"ตอนนี้เรามี {interaction.guild.member_count} คนในเซิร์ฟเวอร์ 💬")

        await interaction.response.send_message(
            content=f"✅ บันทึกข้อความต้อนรับแล้ว!",
            embed=embed,
            ephemeral=True
        )


class WelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)  # ❗ ให้ปุ่มคงอยู่ถาวร

    @discord.ui.button(label="ตั้งค่าข้อความต้อนรับ", style=discord.ButtonStyle.primary, custom_id="open_welcome_modal")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config().get(str(interaction.guild.id), {})
        await interaction.response.send_modal(WelcomeModal(
            title_val=config.get("title", ""),
            description_val=config.get("message", ""),
            image_val=config.get("image_url", ""),
            color_val=config.get("color", "")
        ))



class GoodbyeModal(discord.ui.Modal):
    def __init__(self, title_val="", description_val="", image_val="", color_val=""):
        super().__init__(title="ตั้งค่าข้อความออกจากเซิร์ฟเวอร์")

        self.title_input = discord.ui.TextInput(
            label="หัวข้อ Embed (Title)",
            placeholder="เช่น ลาก่อน {user}...",
            default=title_val,
            max_length=100,
            required=False
        )
        self.description_input = discord.ui.TextInput(
            label="เนื้อหา Embed (Description)",
            placeholder="พิมพ์ข้อความเช่น หวังว่าจะได้พบกันใหม่!",
            default=description_val,
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        )
        self.image_input = discord.ui.TextInput(
            label="ลิงก์รูปภาพ (ถ้ามี)",
            placeholder="https://...",
            default=image_val,
            required=False
        )
        self.color_input = discord.ui.TextInput(
            label="สี Embed (Hex เช่น #e74c3c หรือเว้นว่างไว้)",
            placeholder="#e74c3c",
            default=color_val,
            required=False,
            max_length=7
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.image_input)
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        data = config.get(guild_id, {})

        title = self.title_input.value or data.get("goodbye_title", "👋 ลาก่อน!")
        message = self.description_input.value or data.get("goodbye_message", "{user} ได้ออกจากเซิร์ฟเวอร์")
        image_url = self.image_input.value or data.get("goodbye_image_url", "")
        color_input = self.color_input.value or data.get("goodbye_color", "#e74c3c")  # แดง default

        try:
            # ใช้ตัวแปร color_input แทน color
            embed_color = int(color_input.replace("#", ""), 16)
        except ValueError:
            embed_color = 0x5865F2  # Default color (e.g., Discord's blurple)

        # บันทึกข้อมูลที่ปรับแต่งไว้ใน config
        data["goodbye_title"] = title
        data["goodbye_message"] = message
        data["goodbye_image_url"] = image_url
        data["goodbye_color"] = color_input
        data["enabled"] = True

        config[guild_id] = data
        save_config(config)

        # สร้าง Embed
        embed = discord.Embed(
            title=title.replace("{user}", interaction.user.mention),
            description=message.replace("{user}", interaction.user.mention),
            color=embed_color
        )
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"เหลือสมาชิก {interaction.guild.member_count} คนในเซิร์ฟเวอร์ 😢")

        await interaction.response.send_message(
            content=f"👋 ลาก่อน {interaction.user.mention} (แค่ทดสอบนะ!)",
            embed=embed,
            ephemeral=True
        )

@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id is None:
        return

    config = load_config()
    guild_id = str(payload.guild_id)
    guild_config = config.get(guild_id, {})

    if payload.message_id != guild_config.get("message_id"):
        return

    emoji = str(payload.emoji)

    if emoji in guild_config:
        role_id = guild_config[emoji].get("role_id")
        if not role_id:
            return

        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)

        if role and member:
            try:
                await member.add_roles(role)
                print(f"✅ Gave role {role.name} to {member.display_name}")
            except discord.Forbidden:
                print(f"❌ Missing permission to add role {role.name} to {member.display_name}")
            except Exception as e:
                print(f"❌ Error: {e}")

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id is None:
        return

    config = load_config()
    guild_id = str(payload.guild_id)
    guild_config = config.get(guild_id, {})

    if payload.message_id != guild_config.get("message_id"):
        return

    emoji = str(payload.emoji)

    if emoji in guild_config:
        role_id = guild_config[emoji].get("role_id")
        if not role_id:
            return

        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)

        if role and member:
            try:
                await member.remove_roles(role)
                print(f"🔁 Removed role {role.name} from {member.display_name}")
            except Exception as e:
                print(f"❌ Error removing role: {e}")


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot:  # ข้ามบอท
        return

    # ตรวจสอบว่า reaction อยู่ใน embed ที่เราสร้างหรือไม่
    if not isinstance(reaction.message.embeds, list) or len(reaction.message.embeds) == 0:
        return

    embed = reaction.message.embeds[0]
    if "select your role" not in embed.title:  # ตรวจสอบว่าเป็น Embed สำหรับรับยศหรือไม่
        return

    # หา role ตามอิโมจิ
    emoji = reaction.emoji
    guild_config = load_config().get(str(reaction.message.guild.id))
    if not guild_config:
        return

    for role_id, data in guild_config.items():
        if isinstance(data, dict) and "emoji" in data and data["emoji"] == emoji:
            role = reaction.message.guild.get_role(int(role_id))
            if not role:  # ถ้าไม่ได้หา role
                return

            member = reaction.message.guild.get_member(user.id)
            if not member:  # ถ้าไม่ได้หา member
                return

            if role not in member.roles:  # ถ้ายังไม่มีบทบาท
                try:
                    await member.add_roles(role)  # เพิ่มบทบาท
                    await reaction.message.channel.send(f"✅ {user.name} ได้รับบทบาท {role.name} แล้ว")
                except discord.Forbidden:
                    await reaction.message.channel.send(f"❌ บอทไม่สามารถเพิ่มบทบาทให้ {user.name} ได้")
            else:  # ถ้ามีบทบาทแล้ว
                try:
                    await member.remove_roles(role)  # ลบบทบาท
                    await reaction.message.channel.send(f"❌ {user.name} ถูกลบบทบาท {role.name} แล้ว")
                except discord.Forbidden:
                    await reaction.message.channel.send(f"❌ บอทไม่สามารถลบบทบาทให้ {user.name} ได้")
            break





@bot.tree.command(name="setrole", description="ตั้งค่าระบบกดรับบทบาท")
@has_any_role_name(["Admin", "Moderator", "คนดูแล"])
@app_commands.describe(channel="ห้องที่จะให้บอทส่งข้อความกดรับบทบาท (หากต้องการเปลี่ยนห้อง)")
async def setrole(interaction: discord.Interaction, channel: discord.TextChannel = None):
    config = load_config()
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        await interaction.response.send_message("❌ ยังไม่มีข้อมูลบทบาทในเซิร์ฟเวอร์นี้", ephemeral=True)
        return

    if not any(isinstance(v, dict) and "role_id" in v for v in guild_config.values()):
        await interaction.response.send_message("❌ ยังไม่มีการเพิ่มบทบาทใดๆ", ephemeral=True)
        return

    if "channel_id" not in guild_config and not channel:
        await interaction.response.send_message("❌ กรุณาระบุห้องในครั้งแรกที่ใช้คำสั่ง", ephemeral=True)
        return

    if channel:
        guild_config["channel_id"] = channel.id
        config[guild_id] = guild_config
        save_config(config)

    title = guild_config.get("embedrole_title", "✦ select your role ✦")
    color_hex = guild_config.get("embedrole_color", "#2ecc71")
    try:
        color = int(color_hex.replace("#", ""), 16)
    except ValueError:
        color = 0x2ecc71

    description_lines = ["°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔:･°❀⋆.ೃ࿔:･"]
    for emoji, data in guild_config.items():
        if isinstance(data, dict) and "role_id" in data:
            role_id = data["role_id"]
            description = data.get("description", "")
            role = interaction.guild.get_role(role_id)

            if role:
                description_lines.append(f"{emoji} = {role.mention}` {description} ⋆｡°✩")

    description_lines.append("°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔:･°❀⋆.ೃ࿔:･")

    embed = discord.Embed(
        title=title,
        description="\n".join(description_lines),
        color=color
    )
    embed.set_image(url=guild_config.get("image_url", "https://media.tenor.com/J_BBejDgP1kAAAAC/ai-eyes.gif"))
    embed.set_footer(text=f"สร้างโดย {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

    target_channel_id = guild_config.get("channel_id")
    target_channel = interaction.guild.get_channel(target_channel_id)

    if target_channel:
        message = await target_channel.send(embed=embed)

        for emoji, data in guild_config.items():
            if isinstance(data, dict) and "role_id" in data:
                try:
                    await message.add_reaction(emoji)
                except discord.HTTPException:
                    pass

        guild_config["message_id"] = message.id
        config[guild_id] = guild_config
        save_config(config)

        await interaction.response.send_message(f"✅ ส่ง Embed ไปที่ {target_channel.mention} แล้ว", ephemeral=True)
    else:
        await interaction.response.send_message("❌ ไม่พบห้องที่ตั้งค่าไว้", ephemeral=True)


@bot.tree.command(name="resetrole", description="รีเซ็ตบทบาทที่ตั้งไว้")
async def resetrole(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        await interaction.response.send_message("❌ ยังไม่มีข้อมูลบทบาทในเซิร์ฟเวอร์นี้", ephemeral=True)
        return

    # ลบข้อความเดิมถ้ามี
    message_id = guild_config.get("message_id")
    channel_id = guild_config.get("channel_id")
    if message_id and channel_id:
        target_channel = interaction.guild.get_channel(channel_id)
        if target_channel:
            try:
                message = await target_channel.fetch_message(message_id)
                await message.delete()
            except discord.NotFound:
                pass

    # ล้างเฉพาะ key ที่เป็น role_id (int string) ที่มี dict ข้างใน
    keys_to_delete = [k for k, v in guild_config.items() if isinstance(v, dict) and "emoji" in v]
    for k in keys_to_delete:
        del guild_config[k]

    # รีเซ็ต message_id
    guild_config["message_id"] = None
    config[guild_id] = guild_config
    save_config(config)

    await interaction.response.send_message("✅ รีเซ็ตระบบเลือกบทบาทเรียบร้อยแล้ว", ephemeral=True)





# ใช้ Modal ในคำสั่ง embedrole
@bot.tree.command(name="embedrole", description="เปลี่ยนหัวข้อ Embed ของระบบรับยศ")
@has_any_role_name(["คนดูแล", "Moderator", "Admin"])
async def embedrole(interaction: discord.Interaction):
    modal = EmbedRoleModal()
    await interaction.response.send_modal(modal)



# คำสั่ง /editrole
@bot.tree.command(name="editrole", description="เพิ่มหรือแก้ไขบทบาทที่ใช้กับระบบกดรับยศ")
@has_any_role_name(["Admin", "Moderator", "คนดูแล"])
async def editrole(interaction: discord.Interaction, emoji: str, role: discord.Role, description: str = "ไม่มีคำอธิบาย"):
    """
    เพิ่มหรืออัปเดตข้อมูล emoji + บทบาท สำหรับระบบกดรับยศ
    """
    config = load_config()
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id, {})

    # อัปเดตหรือสร้างข้อมูลใหม่โดยใช้ emoji เป็น key
    guild_config[emoji] = {
        "role_id": role.id,
        "description": description
    }

    config[guild_id] = guild_config
    save_config(config)

    await interaction.response.send_message(
        f"✅ อัปเดตข้อมูลสำเร็จ!\n"
        f"Emoji: {emoji}\n"
        f"Role: {role.mention}\n"
        f"คำอธิบาย: {description}",
        ephemeral=True
    )

class EmbedRoleModal(Modal):
    def __init__(self):
        super().__init__(title="กรอกหัวข้อ Embed สำหรับระบบรับยศ")
        self.title_input = TextInput(
            label="หัวข้อ Embed",
            placeholder="กรุณากรอกหัวข้อที่ต้องการ",
            min_length=1,
            max_length=256,
            required=True
        )
        self.add_item(self.title_input)

    async def on_submit(self, interaction: discord.Interaction):
        title = self.title_input.value
        config = load_config()
        guild_id = str(interaction.guild.id)

        # ✅ ใช้ key แยกเฉพาะของ embedrole
        if guild_id not in config:
            config[guild_id] = {}

        config[guild_id]["embedrole_title"] = title
        save_config(config)

        await interaction.response.send_message(f"✅ เปลี่ยนหัวข้อ EmbedRole เป็น `{title}` แล้ว", ephemeral=True)


class EditRoleModal(discord.ui.Modal, title="แก้ไขข้อมูลบทบาท"):
    def __init__(self, emoji, role_name, role_id):
        super().__init__()
        self.emoji = emoji
        self.role_id = role_id
        self.role_name = role_name

        self.add_item(discord.ui.TextInput(
            label="คำอธิบายบทบาท",
            placeholder="พิมพ์คำอธิบายที่คุณต้องการสำหรับบทบาทนี้...",
            default=f"บทบาท: {role_name}",
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        description = self.children[0].value
        await interaction.response.send_message(
            f"✅ อัปเดตบทบาท **{self.role_name}** (ID: `{self.role_id}`) พร้อมคำอธิบายใหม่:\n{description}",
            ephemeral=True
        )

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sync", description="ซิงก์คำสั่ง Slash กับ Discord (global)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sync(self, interaction: discord.Interaction):
        # ซิงก์คำสั่งแบบ global
        await self.bot.tree.sync(guild=None)  # ไม่ระบุ guild จะทำการซิงก์แบบ global
        await interaction.response.send_message("✅ คำสั่ง Slash ได้รับการซิงก์ทั่วทั้งบอทแล้ว!", ephemeral=True)

    @sync.error
    async def sync_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
        else:
            await interaction.response.send_message("❌ เกิดข้อผิดพลาดขณะซิงก์คำสั่ง", ephemeral=True)


@bot.tree.command(name="embed", description="สร้างข้อความ Embed ที่สวยงาม")
@app_commands.describe(
    title="หัวข้อของ Embed",
    description="คำอธิบายของ Embed",
    color="สีของ Embed (ใช้ Hex หรือชื่อสี)"
)
async def embed(interaction: discord.Interaction, title: str, description: str, color: str = "#3498db"):
    try:
        embed_color = int(color.lstrip("#"), 16)
        embed = discord.Embed(title=title, description=description, color=embed_color)
        embed.set_footer(text=f"สร้างโดย {interaction.user}", icon_url=interaction.user.avatar.url)
        await interaction.response.send_message(embed=embed)
    except ValueError:
        await interaction.response.send_message(
            "❌ สีที่คุณใส่ไม่ถูกต้อง! กรุณาใช้ Hex (ตัวอย่าง: #3498db) หรือชื่อสีที่ถูกต้อง",
            ephemeral=True
        )



def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Config file not found. Creating a new one.")
        return {}
    except json.JSONDecodeError:
        print("Config file is corrupted. Starting with an empty config.")
        return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        print(f"Error saving config: {e}")

def create_embed(role_items, guild):
    """
    สร้าง Embed สำหรับการแสดงข้อมูลบทบาท
    """
    embed = discord.Embed(
        title="เลือกบทบาทของคุณ",
        description="กดที่อีโมจิด้านล่างเพื่อรับบทบาท",
        color=discord.Color.green()
    )
    for item in role_items:
        role = guild.get_role(item["role_id"])
        if role:
            embed.add_field(
                name=f"{item['emoji']} {role.name}",
                value=item['description'],
                inline=False
            )
    return embed

async def add_reactions(message, role_items):
    """
    เพิ่ม Reaction ในข้อความที่ส่ง
    """
    for item in role_items:
        try:
            await message.add_reaction(item["emoji"])
        except discord.HTTPException as e:
            logging.warning(f"❌ Failed to add reaction {item['emoji']} to message {message.id}: {e}")



@commands.command(name="create_roles_message")
@commands.has_permissions(manage_roles=True)
async def create_roles_message(ctx):
    """
    สร้างข้อความ Embed พร้อม Role Reaction โดยให้เลือกอีโมจิและชื่อบทบาทเอง
    """
    # สร้าง Embed
    embed = discord.Embed(
        title="★ Select Your Role ★",
        description="เลือก Emoji ด้านล่างเพื่อรับบทบาทที่คุณต้องการ",
        color=discord.Color.blue()
    )
    embed.set_footer(text="★ Select Your Role ★")

    # ตัวอย่าง: ให้ผู้ใช้กำหนดเอง
    emoji_role_map = {
        "🌸": "ruby",
        "💎": "sapphire",
        "🟨": "topaz",
        "💚": "emerald",
        "🔷": "diamond",
        "💜": "amethyst",
        "🌈": "opal"
    }

    # ตรวจสอบว่าไม่มี Emoji ซ้ำ
    if len(emoji_role_map.keys()) != len(set(emoji_role_map.keys())):
        await ctx.send("❌ มีอีโมจิซ้ำในรายการ กรุณาตรวจสอบและแก้ไข")
        return

    # เพิ่มข้อมูลใน Embed
    for emoji, role_name in emoji_role_map.items():
        embed.add_field(name=f"{emoji} {role_name}", value=f"รับบทบาท **{role_name}**", inline=False)

    # ตรวจสอบสิทธิ์ของบอท
    if not ctx.channel.permissions_for(ctx.guild.me).send_messages:
        await ctx.send("❌ บอทไม่มีสิทธิ์ส่งข้อความในช่องนี้")
        return

    if not ctx.channel.permissions_for(ctx.guild.me).add_reactions:
        await ctx.send("❌ บอทไม่มีสิทธิ์เพิ่ม Reaction ในช่องนี้")
        return

    # ส่ง Embed
    message = await ctx.send(embed=embed)

    # เพิ่ม Reaction ในข้อความ
    for emoji in emoji_role_map.keys():
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException as e:
            logging.warning(f"❌ Failed to add reaction {emoji}: {e}")

    # บันทึกข้อมูล Emoji และ Role ในไฟล์
    try:
        with open("reaction_roles.json", "w", encoding="utf-8") as file:
            import json
            data = {
                "message_id": message.id,
                "channel_id": message.channel.id,
                "emoji_role_map": emoji_role_map
            }
            json.dump(data, file, ensure_ascii=False, indent=4)
    except IOError as e:
        await ctx.send(f"❌ Failed to save reaction roles: {e}")
        return

    await ctx.send("✅ สร้างข้อความ Role Reaction สำเร็จ!")


@bot.event
async def on_application_command_error(interaction, error):
    print(f"Command error: {error}")
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ เกิดข้อผิดพลาดขณะประมวลผลคำสั่ง", ephemeral=True)  

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        # ค้นหาค่าที่เลือกจาก Select
        if isinstance(interaction.data, dict):
            if interaction.data.get("custom_id") == "editrole":
                emoji = interaction.data["values"][0]
                role_id = int(interaction.data["values"][1])
                role_name = discord.utils.get(interaction.guild.roles, id=role_id).name

                # เปิด modal สำหรับกรอกคำอธิบาย
                modal = EditRoleModal(emoji, role_name, role_id)
                await interaction.response.send_modal(modal)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        # ซิงก์คำสั่ง Slash
        synced_commands = await bot.tree.sync()
        
        # เพิ่ม Cog หลังจากซิงก์คำสั่งเสร็จ
        await bot.add_cog(Sync(bot))  # เพิ่ม Cog นี้เมื่อบอทพร้อมทำงาน
        
        print(f"✅ Synced {len(synced_commands)} commands.")
    except discord.Forbidden:
        logging.error("❌ บอทไม่มีสิทธิ์ Sync คำสั่งในเซิร์ฟเวอร์บางแห่ง")
    except Exception as e:
        logging.error(f"❌ Failed to sync commands: {e}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            embed=discord.Embed(
                title="❌ ไม่มีสิทธิ์",
                description="คุณไม่มีสิทธิ์ในการใช้คำสั่งนี้",
                color=discord.Color.red()
            )
        )
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(
            embed=discord.Embed(
                title="❌ คำสั่งไม่ถูกต้อง",
                description="ไม่พบคำสั่งดังกล่าว โปรดตรวจสอบอีกครั้ง",
                color=discord.Color.red()
            )
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            embed=discord.Embed(
                title="⚠️ ขาดอาร์กิวเมนต์",
                description="โปรดใส่ข้อมูลให้ครบถ้วน เช่น `/คำสั่ง <อาร์กิวเมนต์>`",
                color=discord.Color.orange()
            )
        )
    else:
        await ctx.send(
            embed=discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"รายละเอียด: `{error}`",
                color=discord.Color.red()
            )
        )

@bot.event
async def on_member_join(member):
    # ใช้ config.json หรือค่าอื่นๆ
    config = load_config()
    data = config.get(str(member.guild.id))

    if not data or not data.get("enabled", True):
        return

    channel = discord.utils.get(member.guild.text_channels, name="welcome")  # หรือใส่ ID แทน
    if not channel:
        return

    text = data["message"].replace("{user}", member.mention)

    embed = discord.Embed(
        title="🎉 ยินดีต้อนรับ!",
        description=text,
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    if data.get("image_url"):
        embed.set_image(url=data["image_url"])

    thailand_tz = pytz.timezone('Asia/Bangkok')
    current_time = datetime.now(thailand_tz).strftime('%H:%M:%S %Y-%m-%d')

    # 🧾 ใส่ footer ที่มีชื่อผู้ใช้ + เวลา + จำนวนสมาชิก
    embed.set_footer(text=f"สมาชิกใหม่: {member.name} | เวลา: {current_time} | ทั้งหมด {member.guild.member_count} คน")

    # ส่งข้อความข้างนอก embed
    await channel.send(
        content=f"🎉 ยินดีต้อนรับ {member.mention}!",
        embed=embed
    )



@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.lower()

    if "กินไรดี" in content or "กินอะไรดี" in content:
        menu_list = [
            "ข้าวกระเพรา", "ข้าวผัด", "ข้าวมันไก่", "ข้าวหมูแดง", "ข้าวหมูกรอบ",
            "ก๋วยเตี๋ยวเรือ", "ก๋วยเตี๋ยวต้มยำ", "เย็นตาโฟ", "ราดหน้า", "ผัดซีอิ๊ว",
            "ผัดไทย", "ข้าวไข่เจียว", "ข้าวไข่ข้น", "ข้าวหน้าหมูทอด", "ข้าวหน้าเนื้อ",
            "หมูกระทะ", "ชาบู", "ปิ้งย่างเกาหลี", "พิซซ่า", "เบอร์เกอร์",
            "สปาเก็ตตี้", "ข้าวซอย", "แกงเขียวหวาน", "แกงส้ม", "ต้มยำกุ้ง",
            "ต้มจืดเต้าหู้หมูสับ", "ข้าวคลุกกะปิ", "ส้มตำ", "ไก่ทอด", "ข้าวเหนียวหมูปิ้ง"
        ]

        emoji_list = ["🍛", "🍜", "🍲", "🥘", "🍝", "🍕", "🍔", "🌮", "🥗", "🍤", "🥓", "🍗", "🍚", "🍱", "🥟"]

        menu = random.choice(menu_list)
        emoji = random.choice(emoji_list)

        await message.channel.send(f"ลองกิน **{menu}** ดูไหม? {emoji}")

    if any(user.id == TARGET_USER_ID for user in message.mentions):
        thailand_tz = pytz.timezone('Asia/Bangkok')
        now = datetime.now(thailand_tz)
        hour = now.hour

        if 2 <= hour < 14:
            response = random.choice(sleep_messages)
        else:  # 14:00 - 01:59
            response = random.choice(busy_messages)
            
        await message.channel.send(response)
    
    await bot.process_commands(message)


@bot.tree.command(name="example", description="ตัวอย่างคำสั่ง")
async def example(interaction: discord.Interaction):
    try:
        # ตัวอย่างคำสั่งที่อาจเกิดข้อผิดพลาด
        raise ValueError("ตัวอย่างข้อผิดพลาด")
    except ValueError as e:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ ข้อผิดพลาด",
                description=f"เกิดปัญหา: `{e}`",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
    except Exception as e:
        # แจ้งเตือนข้อผิดพลาดอื่น ๆ
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ เกิดข้อผิดพลาดไม่ทราบสาเหตุ",
                description=f"รายละเอียด: `{e}`",
                color=discord.Color.red()
            ),
            ephemeral=True
        )


def get_guild_data(guild_id):
    config = load_config()
    return config.get(str(guild_id), {})

def set_channel(guild_id, channel_id):
    config = load_config()
    config[str(guild_id)] = config.get(str(guild_id), {})
    config[str(guild_id)]["channel_id"] = channel_id
    save_config(config)

def add_tiktok(guild_id, username):
    config = load_config()
    guild_data = config.setdefault(str(guild_id), {})
    users = guild_data.setdefault("tiktok_usernames", [])
    if username not in users:
        users.append(username)
    save_config(config)

def remove_tiktok(guild_id, username):
    config = load_config()
    users = config.get(str(guild_id), {}).get("tiktok_usernames", [])
    if username in users:
        users.remove(username)
    save_config(config)

# ---------- TikTok Live Checker ---------- #
async def is_live(username):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(f"https://www.tiktok.com/@{username}/live", timeout=15000)
                html = await page.content()
            except Exception as e:
                print(f"[ERROR] โหลด TikTok ไม่สำเร็จ: {e}")
                return False, None, None, None
            finally:
                await browser.close()

            # รูปพรีวิว
            match_img = re.search(r'<meta property="og:image" content="(.*?)"', html)
            image = match_img.group(1) if match_img else None

            # หัวข้อไลฟ์
            match_title = re.search(r'<meta property="og:title" content="(.*?)"', html)
            title = match_title.group(1) if match_title else "Live on TikTok"

            # คนดู
            match_viewers = re.search(r'{"viewerCount":(\d+)', html)
            viewers = int(match_viewers.group(1)) if match_viewers else 0

            # ตรวจว่าไลฟ์อยู่ไหม
            live = "LIVE" in html or "liveRoom" in html
            return live, image, title, viewers
    except Exception as e:
        print(f"[CRITICAL] เกิดข้อผิดพลาดใน is_live(): {e}")
        return False, None, None, None




class WatchButton(View):
    def __init__(self, url): super().__init__(); self.add_item(Button(label="Watch Stream", url=url))

async def send_embed(channel, username, preview, stream_title, viewers):
    url = f"https://www.tiktok.com/@{username}/live"
    embed = discord.Embed(title=f"{username} กำลังไลฟ์!", description=stream_title or "🎥 เข้ามาดูเลย!", color=0xff0050)
    embed.set_author(name=username, icon_url="https://www.tiktok.com/favicon.ico")
    if preview:
        embed.set_image(url=preview)
    if viewers is not None:
        embed.add_field(name="👁️ Viewers", value=str(viewers), inline=True)
    embed.add_field(name="🔗 ลิงก์ TikTok", value=f"[ชมสตรีม]({url})", inline=True)
    await channel.send(content="@everyone", embed=embed, view=WatchButton(url))




# ---------- Loop ---------- #
@tasks.loop(minutes=1)
async def check_tiktoks():
    config = load_config()
    for guild_id, data in config.items():
        guild_id = int(guild_id)
        channel = bot.get_channel(data.get("channel_id"))
        if not channel:
            continue

        usernames = data.get("tiktok_usernames", [])
        for username in usernames:
            is_on, preview, title, viewers = await is_live(username)
            if last_status.get(guild_id, {}).get(username) != is_on:
                last_status.setdefault(guild_id, {})[username] = is_on
                if is_on:
                    await send_embed(channel, username, preview, title, viewers)


# ---------- Slash Commands ---------- #
@bot.tree.command(name="setchannel", description="เลือกห้องให้บอทแจ้งไลฟ์ TikTok")
@app_commands.checks.has_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # ป้องกันหมดเวลา
    set_channel(interaction.guild.id, interaction.channel.id)
    await interaction.followup.send("✅ ตั้งค่าห้องสำเร็จ!", ephemeral=True)


@bot.tree.command(name="addtiktok", description="เพิ่มชื่อ TikTok ที่จะติดตาม")
@app_commands.describe(username="ชื่อผู้ใช้ TikTok (ไม่ต้องมี @)")
async def addtiktok(interaction: discord.Interaction, username: str):
    add_tiktok(interaction.guild.id, username)
    await interaction.response.send_message(f"✅ เพิ่ม `{username}` แล้ว", ephemeral=True)

@bot.tree.command(name="removetiktok", description="ลบชื่อ TikTok ที่ไม่ต้องติดตามแล้ว")
@app_commands.describe(username="ชื่อผู้ใช้ TikTok ที่จะลบ")
async def removetiktok(interaction: discord.Interaction, username: str):
    remove_tiktok(interaction.guild.id, username)
    await interaction.response.send_message(f"🗑️ ลบ `{username}` แล้ว", ephemeral=True)

@bot.tree.command(name="listtiktok", description="ดูรายชื่อ TikTok ที่กำลังติดตาม")
async def listtiktok(interaction: discord.Interaction):
    data = get_guild_data(interaction.guild.id)
    users = data.get("tiktok_usernames", [])
    if not users:
        await interaction.response.send_message("❌ ยังไม่มีชื่อ TikTok ในระบบ", ephemeral=True)
    else:
        await interaction.response.send_message("📺 TikTok ที่ติดตาม:\n• " + "\n• ".join(users), ephemeral=True)


@bot.tree.command(name="testtiktok", description="ทดสอบแจ้งเตือนไลฟ์ TikTok")
@app_commands.describe(username="ชื่อผู้ใช้ TikTok")
async def testtiktok(interaction: discord.Interaction, username: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        channel = interaction.channel
        is_on, preview_url, stream_title, viewers = await is_live(username)
        if is_on:
            await send_embed(channel, username, preview_url, stream_title, viewers)
            await interaction.followup.send("✅ ส่งข้อความเรียบร้อย")
        else:
            await interaction.followup.send("❌ ยังไม่ได้ไลฟ์")
    except Exception as e:
        await interaction.followup.send(f"⚠️ เกิดข้อผิดพลาด: `{e}`")






@bot.tree.command(name="setwelcome", description="ตั้งค่าระบบต้อนรับ")
@has_any_role_name(["คนดูแล", "Moderator", "Admin"])  # ✅ ใส่ชื่อบทบาทที่อนุญาต
@app_commands.describe(
    channel="ห้องที่จะให้บอทส่งข้อความต้อนรับ (หากต้องการเปลี่ยนช่อง)",
    message="ข้อความต้อนรับ (ใส่ {user} เพื่อแทนชื่อผู้เข้า) (ถ้าจะเปลี่ยน)",
    image_url="ลิงก์รูปหรือ GIF (หากต้องการเปลี่ยนรูป)"
)
async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel = None, message: str = None, image_url: str = None):
    

    config = load_config()
    data = config.get(str(interaction.guild.id), {})

    # ตรวจสอบว่ามีการตั้งค่าช่องไว้หรือไม่
    if "channel_id" not in data:
        # ถ้ายังไม่ตั้งค่าช่อง ให้บังคับเลือกช่องในครั้งแรก
        if not channel:
            await interaction.response.send_message("กรุณาตั้งค่าช่องต้อนรับก่อน ด้วยคำสั่ง `/setwelcome` ครั้งแรก", ephemeral=True)
            return
        data["channel_id"] = channel.id  # ถ้าไม่มีการตั้งค่าช่อง ให้ตั้งค่าใหม่

    # ถ้าผู้ใช้ต้องการเปลี่ยนห้อง, อัปเดต channel_id
    if channel:
        data["channel_id"] = channel.id  # เปลี่ยนห้องที่ตั้งค่า

    # อัพเดตแค่ข้อความต้อนรับ หรือรูปภาพ ถ้าได้รับ
    if message:
        data["message"] = message  # อัปเดตข้อความต้อนรับ
    if image_url:
        data["image_url"] = image_url  # อัปเดตรูปภาพ

    data["enabled"] = True  # เปิดใช้งานระบบต้อนรับ

    config[str(interaction.guild.id)] = data
    save_config(config)

    # แจ้งผลการตั้งค่า
    channel = interaction.guild.get_channel(data["channel_id"])  # ดึงช่องที่ตั้งค่าไว้
    if message and image_url and channel:
        await interaction.response.send_message(f"✅ ตั้งค่าต้อนรับเสร็จแล้ว จะส่งที่ {channel.mention} พร้อมข้อความใหม่และรูปภาพใหม่.", ephemeral=True)
    elif message and channel:
        await interaction.response.send_message(f"✅ ตั้งค่าต้อนรับเสร็จแล้ว จะส่งที่ {channel.mention} พร้อมข้อความใหม่.", ephemeral=True)
    elif image_url and channel:
        await interaction.response.send_message(f"✅ ตั้งค่าต้อนรับเสร็จแล้ว จะส่งที่ {channel.mention} พร้อมรูปภาพใหม่.", ephemeral=True)
    else:
        await interaction.response.send_message(f"✅ ตั้งค่าต้อนรับเสร็จแล้ว จะส่งที่ {channel.mention}.", ephemeral=True)





@bot.tree.command(name="previewwelcome", description="ทดสอบระบบต้อนรับโดยใช้ตัวอย่าง")
@has_any_role_name(["คนดูแล", "Admin"])  # ✅ ใส่ชื่อบทบาทที่อนุญาต
@app_commands.describe(user="ผู้ใช้ตัวอย่าง (ใส่ชื่อหรือ mention)")
async def previewwelcome(interaction: discord.Interaction, user: discord.User = None):
    if not user:
        user = interaction.user

    config = load_config()
    data = config.get(str(interaction.guild.id))
    if not data or not data.get("enabled", True):
        await interaction.response.send_message("❌ ระบบต้อนรับไม่ได้เปิดใช้งาน", ephemeral=True)
        return

    channel = interaction.guild.get_channel(data["channel_id"])
    if not channel:
        await interaction.response.send_message("❌ ไม่พบช่องที่ตั้งค่าไว้", ephemeral=True)
        return

    # แจ้งการดำเนินการ
    await interaction.response.defer(ephemeral=True)  # ให้ตอบกลับได้ทันที

    # เตรียมข้อความและ embed
    text = data["embedwelcome_message"].replace("{user}", user.mention)
    title = f"{data.get('embedwelcome_title', '🎉 ยินดีต้อนรับ!')}".replace("{user}", user.mention)

    embed = discord.Embed(
        title=title,
        description=text,
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    if data.get("image_url"):
        embed.set_image(url=data["embedwelcome_image_url"])

    # ใช้ pytz เพื่อแปลงเวลาเป็นเวลาไทย
    thailand_tz = pytz.timezone('Asia/Bangkok')
    current_time = datetime.now(thailand_tz).strftime('%H:%M:%S %Y-%m-%d')  # แสดงเวลาในรูปแบบของไทย

    embed.set_footer(text=f"ตอนนี้เรามี {interaction.guild.member_count} คนในเซิร์ฟเวอร์ 💬 | เวลา: {current_time}")

    # ส่งข้อความข้างนอก embed ด้วย content
    await interaction.followup.send(
        content=f"🎉 ยินดีต้อนรับ {user.mention}!",
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(name="previewout", description="ทดสอบระบบออกจากเซิร์ฟเวอร์โดยใช้ตัวอย่าง")
@has_any_role_name(["คนดูแล", "Admin"])  # ✅ ใส่ชื่อบทบาทที่อนุญาต
@app_commands.describe(user="ผู้ใช้ตัวอย่าง (ใส่ชื่อหรือ mention)")
async def previewout(interaction: discord.Interaction, user: discord.User = None):
    if not user:
        user = interaction.user

    config = load_config()
    data = config.get(str(interaction.guild.id))
    if not data or not data.get("enabled", True):
        await interaction.response.send_message("❌ ระบบออกจากเซิร์ฟเวอร์ไม่ได้เปิดใช้งาน", ephemeral=True)
        return

    # ตรวจสอบว่า channel_id มีการตั้งค่าไว้หรือไม่
    channel_id = data.get("channel_id")
    if not channel_id:
        await interaction.response.send_message("❌ ไม่พบช่องที่ตั้งค่าไว้สำหรับการออกจากเซิร์ฟเวอร์", ephemeral=True)
        return

    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message("❌ ไม่สามารถดึงช่องที่ตั้งค่าไว้ได้", ephemeral=True)
        return

    # แจ้งการดำเนินการ
    await interaction.response.defer(ephemeral=True)  # ให้ตอบกลับได้ทันที

    # เตรียมข้อความและ embed
    text = data.get("goodbye_message", "ขอโทษที่คุณต้องจากไป {user}").replace("{user}", user.mention)
    title = f"{data.get('goodbye_title', '👋 ลาก่อน!')}".replace("{user}", user.mention)

    embed = discord.Embed(
        title=title,
        description=text,
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    if data.get("goodbye_image_url"):
        embed.set_image(url=data["goodbye_image_url"])

    # ใช้ pytz เพื่อแปลงเวลาเป็นเวลาไทย
    thailand_tz = pytz.timezone('Asia/Bangkok')
    current_time = datetime.now(thailand_tz).strftime('%H:%M:%S %Y-%m-%d')  # แสดงเวลาในรูปแบบของไทย

    embed.set_footer(text=f"ตอนนี้เรามี {interaction.guild.member_count} คนในเซิร์ฟเวอร์ 💬 | เวลา: {current_time}")

    # ส่งข้อความข้างนอก embed ด้วย content ไปยังช่องที่กำหนด
    await channel.send(
        content=f"👋 ลาก่อน {user.mention}!",
        embed=embed
    )
    await interaction.followup.send(
        "✅ ทดสอบการออกจากเซิร์ฟเวอร์เสร็จสิ้นแล้ว", ephemeral=True
    )

@bot.tree.command(name="previewroles", description="แสดง Embed preview ของระบบกดรับบทบาท")
@has_any_role_name(["Admin", "Moderator", "คนดูแล"])
async def previewroles(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)

    if guild_id not in config:
        await interaction.response.send_message("❌ ยังไม่มีการตั้งค่าบทบาทสำหรับเซิร์ฟเวอร์นี้", ephemeral=True)
        return

    guild_config = config[guild_id]
    channel_id = guild_config.get("channel_id")
    if not channel_id:
        await interaction.response.send_message("❌ ยังไม่ได้ตั้งค่าห้องสำหรับระบบบทบาท", ephemeral=True)
        return

    title = guild_config.get("embedrole_title", "📌 กรุณาเลือกยศด้านล่าง")
    color_hex = guild_config.get("embedrole_color", "#2ecc71")

    try:
        color = int(color_hex.replace("#", ""), 16)
    except ValueError:
        color = 0x2ecc71  # fallback สีเขียว

    description_lines = ["°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･"]
    emojis_to_add = []
    seen_emojis = set()  # ใช้สำหรับเก็บอิโมจิที่เคยใช้แล้ว

    for emoji, data in guild_config.items():
        # ข้ามข้อมูลที่ไม่ใช่ dictionary เช่น channel_id, message, title
        if isinstance(data, dict):  # เช็กให้แน่ใจว่า `data` เป็น dict
            role_id = data.get("role_id")
            description = data.get("description", "")
            role = interaction.guild.get_role(role_id)

            if role:
                # เช็คว่าอิโมจิซ้ำหรือยัง
                if emoji not in seen_emojis:
                    line = f"{emoji} {role.mention} {description} ⋆｡°✩"
                    description_lines.append(line)
                    emojis_to_add.append(emoji)
                    seen_emojis.add(emoji)  # บันทึกอิโมจิที่ใช้แล้ว
                else:
                    continue  # ข้ามหากอิโมจิซ้ำ

    description_lines.append("°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･")

    embed = discord.Embed(
        title=title,
        description="\n".join(description_lines),
        color=color
    )
    embed.set_image(url="https://media.tenor.com/J_BBejDgP1kAAAAC/ai-eyes.gif")
    embed.set_footer(text=f"สร้างโดย {interaction.user.name}", icon_url=interaction.user.avatar.url)

    preview_msg = await interaction.channel.send(embed=embed)

    for emoji in emojis_to_add:
        try:
            await preview_msg.add_reaction(emoji)
        except discord.HTTPException:
            pass  # ข้าม emoji ที่ไม่ valid หรือ custom ที่บอทใช้ไม่ได้

    await interaction.response.send_message("✅ แสดง preview เรียบร้อย", ephemeral=True)





@bot.tree.command(name="setout", description="ตั้งค่าระบบออกจากเซิร์ฟเวอร์")
@has_any_role_name(["คนดูแล", "Moderator", "Admin"])  # ✅ ใส่ชื่อบทบาทที่อนุญาต
@app_commands.describe(
    channel="ห้องที่จะให้บอทส่งข้อความออกจากเซิร์ฟเวอร์ (หากต้องการเปลี่ยนช่อง)",
    message="ข้อความออกจากเซิร์ฟเวอร์ (ใส่ {user} เพื่อแทนชื่อผู้ที่ออก)",
    image_url="ลิงก์รูปหรือ GIF (หากต้องการเปลี่ยนรูป)"
)
async def setout(interaction: discord.Interaction, channel: discord.TextChannel = None, message: str = None, image_url: str = None):

    

    config = load_config()
    data = config.get(str(interaction.guild.id), {})

    # ตรวจสอบว่ามีการตั้งค่าช่องไว้หรือไม่
    if "goodbye_channel_id" not in data:
        # ถ้ายังไม่ตั้งค่าช่อง ให้บังคับเลือกช่องในครั้งแรก
        if not channel:
            await interaction.response.send_message("กรุณาตั้งค่าช่องออกจากเซิร์ฟเวอร์ก่อน ด้วยคำสั่ง `/setout` ครั้งแรก", ephemeral=True)
            return
        data["goodbye_channel_id"] = channel.id  # ถ้าไม่มีการตั้งค่าช่อง ให้ตั้งค่าใหม่

    # ถ้าผู้ใช้ต้องการเปลี่ยนห้อง, อัปเดต channel_id
    if channel:
        data["goodbye_channel_id"] = channel.id  # เปลี่ยนห้องที่ตั้งค่า

    # อัปเดตข้อความออกจากเซิร์ฟเวอร์ หรือรูปภาพ ถ้าได้รับ
    if message:
        data["goodbye_message"] = message  # อัปเดตข้อความออกจากเซิร์ฟเวอร์
    if image_url:
        data["goodbye_image_url"] = image_url  # อัปเดตรูปภาพ

    data["enabled"] = True  # เปิดใช้งานระบบออกจากเซิร์ฟเวอร์

    config[str(interaction.guild.id)] = data
    save_config(config)

    # แจ้งผลการตั้งค่า
    channel = interaction.guild.get_channel(data["goodbye_channel_id"])  # ดึงช่องที่ตั้งค่าไว้
    if message and image_url and channel:
        await interaction.response.send_message(f"✅ ตั้งค่าข้อความออกจากเซิร์ฟเวอร์เสร็จแล้ว จะส่งที่ {channel.mention} พร้อมข้อความใหม่และรูปภาพใหม่.", ephemeral=True)
    elif message and channel:
        await interaction.response.send_message(f"✅ ตั้งค่าข้อความออกจากเซิร์ฟเวอร์เสร็จแล้ว จะส่งที่ {channel.mention} พร้อมข้อความใหม่.", ephemeral=True)
    elif image_url and channel:
        await interaction.response.send_message(f"✅ ตั้งค่าข้อความออกจากเซิร์ฟเวอร์เสร็จแล้ว จะส่งที่ {channel.mention} พร้อมรูปภาพใหม่.", ephemeral=True)
    else:
        await interaction.response.send_message(f"✅ ตั้งค่าข้อความออกจากเซิร์ฟเวอร์เสร็จแล้ว จะส่งที่ {channel.mention}.", ephemeral=True)



@bot.tree.command(name="embedout", description="แก้ไขข้อความการออกจากเซิร์ฟเวอร์แบบ Embed")
@has_any_role_name(["คนดูแล", "Moderator", "Admin"])  # ✅ ใส่ชื่อบทบาทที่อนุญาต
async def embedout(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    data = config.get(guild_id, {})

    modal = GoodbyeModal(
        title_val=data.get("goodbye_title", ""),
        description_val=data.get("goodbye_message", ""),
        image_val=data.get("goodbye_image_url", "")
    )
    await interaction.response.send_modal(modal)



@bot.event
async def on_member_remove(member):
    # ตรวจสอบการตั้งค่าข้อความออกจากเซิร์ฟเวอร์
    config = load_config()
    data = config.get(str(member.guild.id), {})

    # เลือกช่องทางการส่งข้อความ
    channel = discord.utils.get(member.guild.text_channels, name="goodbye")  # หรือใส่ ID แทน
    if not channel:
        return

    # รับค่าข้อความออกจากเซิร์ฟเวอร์และแทนที่ {user} ด้วยชื่อผู้ใช้
    text = data.get("goodbye_message", "ขอโทษที่คุณต้องจากไป {user}").replace("{user}", member.mention)

    # สร้าง embed สำหรับข้อความการออกจากเซิร์ฟเวอร์
    embed = discord.Embed(
        title=data.get("goodbye_title", "👋 ลาก่อน..."),
        description=text,
        color=discord.Color.red()
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    # เช็คว่ามี URL รูปภาพหรือไม่
    if data.get("goodbye_image_url"):
        embed.set_image(url=data["goodbye_image_url"])

    # เพิ่มเวลาใน footer
    thailand_tz = pytz.timezone('Asia/Bangkok')
    current_time = datetime.now(thailand_tz).strftime('%Y-%m-%d %H:%M:%S')

    embed.set_footer(text=f"เหลือสมาชิก {member.guild.member_count} คนในเซิร์ฟเวอร์ 😢 | เวลา: {current_time}")

    # ส่ง Embed ไปยังช่องที่ตั้งค่าไว้
    await channel.send(embed=embed)



@bot.tree.command(name="upload_image", description="Upload an image to the server")
async def upload_image(interaction: discord.Interaction):
    # สร้างปุ่มให้ผู้ใช้กดเพื่อเลือกไฟล์
    button = Button(label="ส่งรูปภาพ", style=discord.ButtonStyle.primary)

    async def button_callback(interaction: discord.Interaction):
        await interaction.response.send_message("กรุณาอัปโหลดรูปภาพ!", ephemeral=True)
        # ถ้าต้องการให้บอทรับไฟล์ที่ผู้ใช้แนบมา
        # สามารถคูณโค้ดจาก on_message ด้านบน

    button.callback = button_callback

    view = View()
    view.add_item(button)

    await interaction.response.send_message("กดปุ่มเพื่อส่งรูปภาพ", view=view)



@bot.tree.command(name="embedwelcome", description="แก้ไขข้อความต้อนรับแบบ Embed")
@has_any_role_name(["คนดูแล", "Moderator", "Admin"])
async def embedwelcome(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    data = config.get(guild_id, {})

    modal = WelcomeModal(
        title_val=data.get("embedwelcome_title", ""),
        description_val=data.get("embedwelcome_message", ""),
        image_val=data.get("embedwelcome_image_url", ""),
        color_val=data.get("embedwelcome_color", "#5865F2")
    )
    await interaction.response.send_modal(modal)


@bot.tree.command(name="upload_picture", description="Upload an image to the server")
async def upload_picture(interaction: discord.Interaction):
    # โค้ดสำหรับอัปโหลดภาพ
    button = Button(label="อัปโหลดภาพ", style=discord.ButtonStyle.primary)

    # เมื่อคลิกปุ่ม
    async def button_callback(interaction: discord.Interaction):
        # ตรวจสอบว่าใช้งานได้หรือไม่ (ผู้ใช้ต้องส่งไฟล์)
        if not interaction.message.attachments:
            await interaction.response.send_message("กรุณาส่งไฟล์ภาพก่อน", ephemeral=True)
            return
        
        # ดึงข้อมูลจากไฟล์ที่แนบมา
        for attachment in interaction.message.attachments:
            if attachment.filename.endswith(('png', 'jpg', 'jpeg', 'gif')):
                # สร้าง Embed สำหรับการแสดงภาพที่อัปโหลด
                embed = discord.Embed(
                    title="คุณอัปโหลดรูปภาพมา",
                    description=f"รูปภาพจาก {interaction.user.mention}",
                    color=discord.Color.green()
                )
                embed.set_image(url=attachment.url)  # ใช้ URL ของไฟล์ที่แนบมา
                thailand_tz = pytz.timezone('Asia/Bangkok')
                current_time = datetime.now(thailand_tz).strftime('%H:%M:%S %Y-%m-%d')  # เวลาในรูปแบบของไทย

                # เพิ่ม footer ลงใน Embed พร้อมแสดงเวลาปัจจุบัน
                embed.set_footer(text=f"เวลาที่อัปโหลด: {current_time} | เซิร์ฟเวอร์: {interaction.guild.name}")

                await interaction.response.send_message(embed=embed)

    # ผูกปุ่มเข้ากับ callback
    button.callback = button_callback
    view = View()
    view.add_item(button)

    # ส่งคำสั่งให้ผู้ใช้คลิกปุ่ม
    await interaction.response.send_message("กรุณาคลิกปุ่มเพื่ออัปโหลดรูปภาพ", view=view)

def is_admin(interaction: discord.Interaction) -> bool:
    print(f"Checking admin for {interaction.user}")
    return interaction.user.guild_permissions.administrator


@bot.tree.command(name="some_admin_command")
@app_commands.check(is_admin)
async def some_admin_command(interaction: discord.Interaction):
    await interaction.response.send_message("✅ This is an admin-only command.", ephemeral=True)

@some_admin_command.error
async def some_admin_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์สำหรับคำสั่งนี้", ephemeral=True)


server_on()   

bot.run(os.getenv('TOKEN'))
