from discord.ext import commands
import discord

class EmbedCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hello(self, ctx):
        await ctx.send("Hello from EmbedCommand!")



