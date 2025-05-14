from discord.ext import commands
import discord

class RoleReactionHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # พิมพ์ชื่ออีโมจิที่ถูกเพิ่ม
        print(f"Reaction added: {payload.emoji}")

        # ตรวจสอบว่าผู้ใช้ไม่ได้เป็นบอทเอง
        if payload.user_id == self.bot.user.id:
            return  # ถ้าเป็นบอทเองก็ไม่ต้องทำอะไร

        # หาช่องที่ผู้ใช้เพิ่ม reaction
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        # ระบุว่า reaction ใดจะมอบบทบาท (เช่น ถ้าเป็นอีโมจิ ✅)
        if str(payload.emoji) == "✅":
            role = discord.utils.get(channel.guild.roles, name="ExampleRole")  # แทนที่ "ExampleRole" ด้วยชื่อบทบาทที่ต้องการ
            if role:
                member = channel.guild.get_member(payload.user_id)
                if member:
                    await member.add_roles(role)
                    await channel.send(f"{member.mention} ได้รับบทบาท {role.name}", delete_after=5)  # ส่งข้อความยืนยันการมอบบทบาท
                else:
                    print(f"Member {payload.user_id} not found.")
            else:
                print("Role not found.")

