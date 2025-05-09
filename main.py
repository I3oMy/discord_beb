import discord
import json
import os 
import pytz  
from myserver import server_on
from discord.ext import commands
from discord import app_commands
from discord import ui, Interaction
from datetime import datetime


CONFIG_FILE = "config.json"




def has_any_role_id(role_ids: list[int]):
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user or not hasattr(interaction.user, "roles"):
            return False
        return any(role.id in role_ids for role in interaction.user.roles)
    return app_commands.check(predicate)

@app_commands.command(name="setwelcome", description="ตั้งค่าข้อความต้อนรับ")
@has_any_role_id([123456789012345678, 987654321098765432])  # แทนด้วย role IDs จริงของคุณ
async def setwelcome(interaction: discord.Interaction):
    await interaction.response.send_message("คุณมีสิทธิใช้คำสั่งนี้!", ephemeral=True)




class WelcomeModal(discord.ui.Modal):
    def __init__(self, title_val="", description_val="", image_val=""):
        super().__init__(title="ตั้งค่าข้อความต้อนรับ")

        self.title_input = discord.ui.TextInput(
            label="หัวข้อ Embed (Title)",
            placeholder="เช่น ยินดีต้อนรับ {user}!",
            default=title_val,  # ใช้ default
            max_length=100,
            required=False
        )
        self.description_input = discord.ui.TextInput(
            label="เนื้อหา Embed (Description)",
            placeholder="พิมพ์ข้อความต้อนรับ เช่น กฎอยู่ที่ <#1234567890>",
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

        # เพิ่ม inputs เข้ามาใน modal
        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.image_input)


    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)

        data = config.get(guild_id, {})

        # รับค่าที่กรอกจาก modal
        title_input = self.title_input.value or data.get("title", "🎉 ยินดีต้อนรับ!")
        description_input = self.description_input.value or data.get("message", "ขอให้สนุกกับการอยู่ที่นี่!")
        image_url = self.image_input.value or data.get("image_url", "")

        # บันทึกใหม่ใน config
        data["title"] = title_input
        data["message"] = description_input
        data["image_url"] = image_url
        data["enabled"] = True

        config[guild_id] = data
        save_config(config)

        # เตรียม embed
        embed = discord.Embed(
            title=title_input.replace("{user}", interaction.user.mention),
            description=description_input.replace("{user}", interaction.user.mention),
            color=discord.Color.blurple()
        )
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"ตอนนี้เรามี {interaction.guild.member_count} คนในเซิร์ฟเวอร์ 💬")

        # ส่งข้อความต้อนรับนอก embed พร้อมแท็ก user
        await interaction.response.send_message(
            content=f"🎉 ยินดีต้อนรับ {interaction.user.mention}!",
            embed=embed,
            ephemeral=True
        )


class GoodbyeModal(discord.ui.Modal):
    def __init__(self, title_val="", description_val="", image_val=""):
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

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        data = config.get(guild_id, {})

        title = self.title_input.value or data.get("goodbye_title", "👋 ลาก่อน!")
        message = self.description_input.value or data.get("goodbye_message", "{user} ได้ออกจากเซิร์ฟเวอร์")
        image_url = self.image_input.value or data.get("goodbye_image_url", "")

        data["goodbye_title"] = title
        data["goodbye_message"] = message
        data["goodbye_image_url"] = image_url
        data["enabled"] = True

        config[guild_id] = data
        save_config(config)

        embed = discord.Embed(
            title=title.replace("{user}", interaction.user.mention),
            description=message.replace("{user}", interaction.user.mention),
            color=discord.Color.red()
        )
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"เหลือสมาชิก {interaction.guild.member_count} คนในเซิร์ฟเวอร์ 😢")

        await interaction.response.send_message(
            content=f"👋 ลาก่อน {interaction.user.mention} (แค่ทดสอบนะ!)",
            embed=embed,
            ephemeral=True
        )




def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())






@bot.event
async def on_ready():
    print("Bot is ready!")
    # ซิงค์คำสั่งให้กับเซิร์ฟเวอร์ทั้งหมด
    for guild in bot.guilds:
        await bot.tree.sync(guild=guild)
    print(f"✅ Synced commands to all servers.")


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

    embed.set_footer(text=f"ตอนนี้เรามี {member.guild.member_count} คนในเซิร์ฟเวอร์ 💬")

    # ส่งข้อความข้างนอก embed
    await channel.send(
        content=f"🎉 ยินดีต้อนรับ {member.mention}!",
        embed=embed
    )


@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="goodbye")  # หรือใส่ ID แทน
    if channel:
        embed = discord.Embed(
            title="👋 ลาก่อน...",
            description=f"{member.name} ออกจากเซิร์ฟเวอร์แล้ว",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url="https://media.tenor.com/YmcBY9nlAwsAAAAC/cid-kagenou-eminence-in-shadow.gif")
        embed.set_footer(text=f"เหลือสมาชิก {member.guild.member_count} คนในเซิร์ฟเวอร์ 😢")

        await channel.send(embed=embed)

@bot.event
async def on_message(message):


    # อย่าลืมให้ bot process คำสั่งด้วย
    await bot.process_commands(message)



@bot.command()
async def test(ctx, arg):
    await ctx.send(arg)


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

@bot.tree.command(name="hi", description="Replies with hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("hello it's me bot discord")



@bot.tree.command(name="ชื่อ", description="ตอบกลับด้วยชื่อ")
async def namecommand(interaction: discord.Interaction, ชื่อ: str):
    await interaction.response.send_message(f"hello {ชื่อ}")


@bot.tree.command(name="setwelcome", description="ตั้งค่าระบบต้อนรับ")
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
    text = data["message"].replace("{user}", user.mention)

    title = f"{data.get('title', '🎉 ยินดีต้อนรับ!')}".replace("{user}", user.mention)

    embed = discord.Embed(
        title=title,
        description=text,
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    if data.get("image_url"):
        embed.set_image(url=data["image_url"])

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



@bot.tree.command(name="setout", description="ตั้งค่าระบบออกจากเซิร์ฟเวอร์")
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






from discord.ui import Button, View



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
async def embedwelcome(interaction: discord.Interaction):
    config = load_config()
    guild_id = str(interaction.guild.id)
    data = config.get(guild_id, {})

    # ส่งค่าที่มีอยู่ไปให้ modal
    modal = WelcomeModal(
        title_val=data.get("title", ""),
        description_val=data.get("message", ""),
        image_val=data.get("image_url", "")
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
                await interaction.response.send_message(embed=embed)

    # ผูกปุ่มเข้ากับ callback
    button.callback = button_callback
    view = View()
    view.add_item(button)

    # ส่งคำสั่งให้ผู้ใช้คลิกปุ่ม
    await interaction.response.send_message("กรุณาคลิกปุ่มเพื่ออัปโหลดรูปภาพ", view=view)  


server_on()    

bot.run(os.getenv('TOKEN'))
