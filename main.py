import asyncio
import json
import time

from core import Core
from ge import GracefulExiter
from utils import round_up, format_currency

import discord
from discord.ext import commands


DISCORD_CHANNEL_ID = 819019902882414624
DISCORD_BOT_TOKEN = 'ODEwMDMxMDE5OTg0OTQ1MTUz.YCduLA.VloqC2vQgY_H7-eumDFKbQ8THCw'

bot = commands.Bot(command_prefix='!')


def generate_status(status):
    embed = discord.Embed(title='Status Report', color=0xff0000)
    for k, v in status.items():
        embed.add_field(name=k, value=F'```{v}```', inline=False)
    embed.set_footer(text=F'{time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(time.time()))}')
    return embed


def generate_core_alarm(result):
    order = result['order']
    if result['phase'] == 'CONFIRM_BUY':
        title_string = F'Purchased {order["market"]}'
    elif result['phase'] == 'CONFIRM_SELL':
        title_string = F'Sold {order["market"]}'
    embed = discord.Embed(title=title_string, color=0xff0000)
    embed.set_author(name='Upbit Balance', icon_url='https://miro.medium.com/fit/c/1360/1360/1*b7E3KUdA2dY2TP2P9Q8O-Q.png', url='https://upbit.com/investments/balance')
    price = order['price']
    volume = order['volume']
    embed.add_field(name='Price', value=F'```{format_currency(price)}```', inline=True)
    embed.add_field(name='Volume', value=F'```{volume}```', inline=True)
    embed.add_field(name='Total', value=F'```{format_currency(price * volume)}```', inline=True)
    if result['phase'] == 'CONFIRM_SELL':
        yield_percentage = round_up((result['yield_rate'] - 1), 2) * 100
        acc_yield_percentage = round_up((result['acc_yield_rate']), 2) * 100
        embed.add_field(name='Yield', value=F'```{acc_yield_percentage} ({yield_percentage} %)```', inline=False)
    embed.set_footer(text=F'{time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(time.time()))}')
    return embed


core = Core()

@bot.command()
async def alive(ctx):
    embed = generate_status(core.to_dict())
    await ctx.send(embed=embed)

async def main():
    await bot.wait_until_ready()
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    flag = GracefulExiter()
    
    while True:
        result = core.update()
        if result is not None:
            embed = generate_core_alarm(result)
            await channel.send(embed=embed)
        await asyncio.sleep(1)
        if flag.exit():
            break
    core.save()
    exit()

bot.loop.create_task(main())
bot.run(DISCORD_BOT_TOKEN)